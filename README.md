# `init.py`

Initialize a Python project for development.


## *This project is not longer maintained*


## Getting started

Download `init.py`:

```console
$ wget https://raw.githubusercontent.com/bachew/init.py/master/init.py
```

Check Python version:

```console
$ python --version
Python 2.7.9
$ python3 --version
Python 3.4.2
```

`init.py` requires [Pipenv](https://docs.pipenv.org/), make sure that it's installed before proceeding.

Choose the Python version you want and initialize:

```console
$ python3 init.py
```

Notice that `init.py` uses Pipenv to create virtualenv, you can locate the directory by running:

```console
$ pipenv --venv
```

To spawn a new shell with activated the virtualenv, just run:

```console
$ pipenv shell
```

`init.py` also installs [Invoke](www.pyinvoke.org) and creates a very basic init task in `tasks/__init__.py`. Init task is run by `init.py` everytime you initilize a project, so it's the good place for you to put system installation commands there. You can invoke the init task **after** activating the virtualenv:

```console
$ inv init
```

Outside of virtualenv you can run:

```console
$ pipenv run inv init
```

But it's easier to work within activated virtualenv because you often need to run many commands:

```
$ pipenv shell
(venv-u0VWRkUS)$ inv -l
Available tasks:

  init

(venv-u0VWRkUS)$ inv init
echo tasks.py says hi
tasks.py says hi
```

## `init_config.py`

`init_config.py` contains configuration for initialization.

Right now there's only one config item, which is `check_python_version()`, it's used to restrict the Python version. For example to restrict to only Python 3.4 and above:

```python
def check_python_version(version):
    if version < (3, 4):
        raise ValueError('requires >=3.4')
```

## `invoke.py`

`init.py` generates useful `invoke.py` for normal usage of Invoke, [read the docs](http://docs.pyinvoke.org) for advanced configuration.
