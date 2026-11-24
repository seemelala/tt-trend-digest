# Contributing

Thanks for helping.

- Python 3.11 or newer, standard library only. Please do not add dependencies.
- Run the tests before you open a pull request. They do not use the network:

  ```
  python -m unittest discover -s tests -v
  ```

- New source? Add a normalizer in `trend_digest/sources.py`, a saved response in
  `tests/fixtures/`, and a test that builds a digest from it.
- Keep functions short and names plain. Each module starts with a short note on what it does.
- Never put keys or webhook addresses in code, tests or issues.
