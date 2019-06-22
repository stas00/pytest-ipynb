import pytest, os, sys, nbformat
from queue import Empty
from nbformat import NotebookNode
import IPython
from pprint import pprint

# XXX: runipy is no longer being maintained! https://github.com/paulgb/runipy
# but it works perfectly fine.
# In the future need to figure out how to move to new api
# https://nbconvert.readthedocs.io/en/latest/execute_api.html
# this implementation seems to do it in a modern way:
# https://github.com/ldiary/pytest-testbook
from runipy.notebook_runner import NotebookRunner

wrapped_stdin = sys.stdin
sys.stdin = sys.__stdin__
sys.stdin = wrapped_stdin

class IPyNbException(Exception):
    """ custom exception for error reporting. """

def pytest_collect_file(path, parent):
    if path.fnmatch("test*.ipynb"): return IPyNbFile(path, parent)

def get_cell_description(cell_input):
    """Gets cell description

    Cell description is the first line of a cell, in one of this formats:

    * single line docstring
    * single line comment
    * function definition
    * %magick

    """
    try:
        first_line = cell_input.split("\n")[0]
        if first_line.startswith(('"', '#', 'def', '%')):
            return first_line.replace('"','').replace("#",'').replace('def ', '').replace("_", " ").strip()
    except:
        pass
    return ""

class IPyNbFile(pytest.File):
    def collect(self):
        with self.fspath.open() as f: payload = f.read()
        self.nb = nbformat.reads(payload, 3)

        # kernel needs to start from the same dir the ipynb is in
        notebook_dir = self.fspath.dirname
        cwd = os.getcwd()
        if cwd != notebook_dir: os.chdir(notebook_dir)
        self.runner = NotebookRunner(self.nb)
        os.chdir(cwd)

        cell_num = 1

        for cell in self.runner.iter_code_cells():
            yield IPyNbCell(self.name, self, cell_num, cell)
            cell_num += 1

    def setup(self):
        self.fixture_cell = None

    def teardown(self):
        self.runner.shutdown_kernel()

class IPyNbCell(pytest.Item):

    MIME_MAP = {
        'image/jpeg': 'jpeg',
        'image/png': 'png',
        'text/plain': 'text',
        'text/html': 'html',
        'text/latex': 'latex',
        'application/javascript': 'html',
        'application/json': 'json',
        'image/svg+xml': 'svg',
    }

    def __init__(self, name, parent, cell_num, cell):
        cell_description = get_cell_description(cell.input)
        nodeid = parent.nodeid + "::" + f"cell {cell_num:2d}"
        if cell_description:
            # If the cell has a valid cell description, it to the node id.
            nodeid += " " + cell_description[0:40]
        else:
            # Otherwise append the raw code to the node id;
            # replace newlines "\n" with "\\n " to avoid line breaks.
            nodeid += "  " + cell.input.replace("\n", "\\n ")[0:40]
        super(IPyNbCell, self).__init__(name, parent, nodeid=nodeid)

        self.cell_num = cell_num
        self.cell = cell
        self.cell_description = cell_description


    # use run_cell from runipy/notebook_runner.py as a base for a better runtest
    # implementation than the original pytest-ipynb, to include reporting output streams
    def runtest(self):
        kc = self.parent.runner.kc
        cell = self.cell

        if ("SKIPCI" in self.cell_description) and ("CI" in os.environ):
            return

        if self.parent.fixture_cell:
            kc.execute(self.parent.fixture_cell.input, allow_stdin=False)

        if self.cell_description.lower().startswith("fixture") or self.cell_description.lower().startswith("setup"):
            self.parent.fixture_cell = self.cell

        kc.execute(cell.input, allow_stdin=False)
        # XXX: the way it's currently implemented there doesn't seem to be a
        # point in handling a timeout situation here, since raising an exception
        # on timeout breaks the rest of the tests. The correct way to do it is to
        # send interrupt to the kernel, and then report timeout, so that the
        # rest of the tests can continue.
        reply = kc.get_shell_msg()

        status = reply['content']['status']
        traceback_text = ''
        if status == 'error':
            traceback_text = 'Cell raised uncaught exception: \n' + \
                '\n'.join(reply['content']['traceback'])

        # extract various outputs and streams
        outs = list()
        timeout = 20
        while True:
            try:
                msg = kc.get_iopub_msg(timeout=timeout)
                if msg['msg_type'] == 'status':
                    if msg['content']['execution_state'] == 'idle':
                        break
            except Empty:
                # execution state should return to idle
                # before the queue becomes empty,
                # if it doesn't, something bad has happened
                raise

            content = msg['content']
            msg_type = msg['msg_type']

            out = NotebookNode(output_type=msg_type)

            if 'execution_count' in content:
                out.prompt_number = content['execution_count']

            if msg_type in ('status', 'pyin', 'execute_input'):
                continue
            elif msg_type == 'stream':
                out.stream = content['name']
                if 'text' in content: out.text = content['text']
            # execute_result == Out[] (_)
            elif msg_type in ('display_data', 'execute_result'):
                for mime, data in content['data'].items():
                    try:
                        attr = self.MIME_MAP[mime]
                    except KeyError:
                        raise NotImplementedError(f'unhandled mime type: {mime}')

                    json_encode = (mime == "application/json")
                    data_out = data if not json_encode else json.dumps(data)
                    setattr(out, "data_type", attr)
                    setattr(out, "data", data_out)
            elif msg_type == 'error':
                out.ename = content['ename']
                out.evalue = content['evalue']
                out.traceback = content['traceback']
            elif msg_type == 'clear_output': pass
                # ignore
                #outs = list()
                #continue
            else:
                raise NotImplementedError(f'unhandled iopub message: {msg_type}')
            outs.append(out)
        #pprint(outs)

        if status == 'error':
            # Get all output streams, so that we can display them in the exception
            pyout = []
            stdout_data = ''
            stderr_data = ''
            for out in outs:
                if out.output_type == 'execute_result':
                    # text, html, json (others are binary)
                    if out.data_type in ["text", "html", "json"]:
                        pyout.append(out.data)
                    else:
                        pyout.append(f"[{out.data_type} object]")
                elif 'stream' in out:
                    if out.stream == 'stdout':
                        stdout_data = out.text
                    elif out.stream == 'stderr':
                        stderr_data = out.text

            raise IPyNbException(self.cell_num, self.cell.input, "\n".join(pyout),
                                 stdout_data, stderr_data, traceback_text)

    def repr_failure(self, excinfo):
        """ called when self.runtest() raises an exception. """
        if isinstance(excinfo.value, IPyNbException):
            return "\n".join([
                "====== Failed cell %d ======\n\n"
                "====== input ======\n%s\n\n"
                "====== output ======\n%s\n\n"
                "====== stdout ======\n%s\n\n"
                "====== stderr ======\n%s\n\n"
                "====== traceback ======\n%s\n\n\n\n" % excinfo.value.args,
            ])
        else:
            return "pytest plugin exception: %s" % str(excinfo.value)
