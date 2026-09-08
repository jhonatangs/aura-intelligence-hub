# 🐍 Python Standards & Testing Protocols

- Packaging & Dependencies: Strictly adhere to PEP 621 conventions using `pyproject.toml` managed by `uv`. Never manually manipulate virtualenvs or rely on `requirements.txt`.
- Standard: Strict, deterministic type hints are mandatory (`mypy` compliant, targeting Python 3.11+ syntax, avoiding untyped `Any`).
- Linter & Formatting: Use `ruff` for all linting and formatting with line-length 100 and rulesets `E`, `F`, `I`, `UP`, `B`. Ensure 100% compliance before handoff.
- Paradigms: Prefer pure functions. Do not use classes unless state management (e.g., context managers, settings models) is strictly necessary.
- Testing Protocols: Enforce isolated mock-testing using `pytest`. Never invoke live Snowflake connections or external APIs in unit tests; use `unittest.mock`, `monkeypatch`, and `tmp_path` fixtures to ensure 100% deterministic, offline execution.
- Documentation: Use Google-style docstrings for all public functions, classes, and methods.

