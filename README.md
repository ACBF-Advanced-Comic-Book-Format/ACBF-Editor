# ACBF-Editor
Editor for comic books in ACBF format written using GTK4 toolkit (WIP)

# Installtion (via pip)

It's recommended to create a new python environment via `python -m venv venv` or similar method.

A GTK4.10+ environment is required, see [PyGObject](https://pygobject.gnome.org/getting_started.html#getting-started) for installation on your OS.

Currently `kumiko` is used for panel detection but has no PyPi upload. You'll need to `git clone` [kumiko](https://github.com/njean42/kumiko) into the `src` directory.

`pip install .`

`python src/acbfe.py`

# Development

`pip install .[dev]` to install the development dependencies.

`pre-commit run -a` for formatting and linting.
