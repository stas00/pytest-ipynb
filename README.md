# pytest-ipynb

Plugin for `pytest` to run ipython/jupyter notebooks as unit and integration tests.

**This is a fork that has been fixed to work, since the original is no longer being maintained**

It allows you to put both `.py` and `.ipynb` test files inside your normal test suite.

It currently relies on `runipy` to interface with the Notebook.

Define unit tests in IPython notebook cells ([see example on
nbviewer](http://nbviewer.ipython.org/github/stas00/pytest-ipynb/blob/master/examples/test_series_plots.ipynb)):

![](https://github.com/stas00/pytest-ipynb/raw/master/img/pytest-ipynb_notebook.png)

Run `py.test` to execute them:

![](https://github.com/stas00/pytest-ipynb/raw/master/img/pytest-ipynb_output.png)

## Example

See the `examples/` folder or [a preview on
nbviewer](http://nbviewer.ipython.org/github/stas00/pytest-ipynb/blob/master/examples/test_series_plots.ipynb).

## Features

-   Discover files named `test*.ipynb`
-   Run each cell of the notebook as a unit test (just use `assert`)
-   First line of each cell is the test name, either as docstring,
    comment or function name
-   A cell named `fixture*` or `setup*` is run before each of the
    following unit tests as a fixture
-   Add SKIPCI to a cell description to skip the test on Travis-CI
    (checks if the CI environment variable is defined)
-   Each notebook is executed in the folder where the `.ipynb` file is
    located

## Requirements

-   Python 3.6+
-   `pytest`
-   ipython-notebook 4.0+

## Install

```
pip install git+https://github.com/stas00/pytest-ipynb.git
```

## Author

[Stas Bekman](https://github.com/stas00/)


## Credits

- This work is a fork of a no-longer maintained original  [pytest-ipynb](https://github.com/zonca/pytest-ipynb), by Andrea Zonca.
