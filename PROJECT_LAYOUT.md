# Simple project layout

**Run `main.py` in PyCharm.**

- `app_code/`: the app itself, with files named for their function.
- `automated_checks/`: checks for the app; not another copy of the app.
- `Release/`: future downloadable version, not built yet.

`requirements.txt` lists dependencies. `EDITING_GUIDE.md` explains which module to edit.

Run checks from this project folder: `python -m unittest discover -s automated_checks -v`.
