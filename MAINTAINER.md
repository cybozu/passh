How to maintain this project
============================

Bump version
------------

1. Modify version string in `setup.py`.
2. Commit.
3. Add the tag for the new version.
4. Push them to GitHub.
5. Write release notes on GitHub.

Publish to PyPI
---------------
In order to release a new version to [PyPI][], do:

1. Read [Python packaging user guide][guide].
2. As recommended in the guide, install `setuptools` and `twine`.
3. Create sdist by `python3 setup.py sdist`.
4. Upload sdit by `$HOME/.local/bin/twine upload dist/*`.

[PyPI]: https://pypi.python.org/pypi/passh/
[guide]: https://python-packaging-user-guide.readthedocs.org/en/latest/current/
