# Project assembly notes

This folder combines the four uploaded ZIP archives into the expected project layout.

- `app/`: Flask application, templates, static assets, and service modules
- `scripts/create_aws_tables.py`: creates the two DynamoDB tables and resource indexes
- `tests/`: automated tests
- `.env.example`: configuration template
- `pytest.ini`: test configuration (at project root)

Before running:
1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` for local development and set a strong `SECRET_KEY`.
4. Run `python -m pytest -q`.
5. Start locally with `python -m app.run` (or the command documented in `app/run.py`).

The Python source files passed syntax compilation during review. Full tests could not be executed in the review environment because Flask and the other dependencies were not installed and package download access was unavailable. AWS integration has not been tested against a real AWS account.
