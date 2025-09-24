# Code Style and Conventions

## Core Development Rules (from CLAUDE.md)

### Package Management
- **ONLY use uv, NEVER pip**
- Installation: `uv add package`
- Running tools: `uv run tool`
- Running Examples: `uv run python3 examples/*`
- Running Verification Scripts: `uv run python3 verification/*`
- Upgrading: `uv add --dev package --upgrade-package package`
- **FORBIDDEN**: `uv pip install`, `@latest` syntax

### Code Quality Standards
- **Type hints required** for all code
- **Public APIs must have docstrings**
- Functions must be **focused and small**
- **Follow existing patterns exactly**
- **Line length**: 120 chars maximum
- Every module should have files ending with `Core` and `internal` folder
- **MAKE ALL properties in class private** by prepending `_` to variable name
- **AVOID MAGIC NUMBERS** - Instead create STATIC fields in class
- **Avoid `Any` type** - Prefer typed classes inheriting from Pydantic `BaseModel`
- **IF property should be public** then hide it using `_` and create a property function
- **Every test file should end in `Test` postfix** - In test files always use classes
- **Using `hasattr` is forbidden** by default and same as `getattr`
- Use static type instead of dictionary whenever possible

### Testing Requirements
- Framework: `poe test`  
- **Async testing**: use `anyio` over `asyncio`
- Coverage: test edge cases and errors
- New features require tests
- Bug fixes require regression tests
- Every implementation file **MUST HAVE ONLY ONE TEST FILE**
- **NO WEAK TESTS** - Tests should:
  - Not have any `if` statements
  - Should test real values and not only shape
  - Should not have `try`/`catch` like testing to prevent false positives
  - MUST have hardcoded values mostly and not ranges like `len(expression) > than_magic_number`
  - NO MAGIC NUMBERS - Instead put these numbers in class

### Exception Handling
- **Always use `logger.exception()`** instead of `logger.error()` when catching exceptions
- Don't include exception in message: `logger.exception("Failed")` not `logger.exception(f"Failed: {e}")`
- **Catch specific exceptions** where possible:
  - File ops: `except (OSError, PermissionError):`
  - JSON: `except json.JSONDecodeError:`
  - Network: `except (ConnectionError, TimeoutError):`
- **Only catch `Exception` for**:
  - Top-level handlers that must not crash
  - Cleanup blocks (log at debug level)

## Formatting Configuration

### Black (line-length: 120)
- Target version: py312
- Configured in pyproject.toml

### Isort
- Profile: black
- Line length: 120
- Known first party: blockether_peekle

### Ruff
- Ignores: E501 (line too long), F401 (imported but unused)

### MyPy
- Disallow untyped defs: true
- Warn return any: true
- Explicit package bases: true

## Pytest Configuration
- Test patterns: `test_*.py`, `*Test.py`, `*_test.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Markers: integration, slow, anyio
- Timeout: 600 seconds (thread method)

## Important Instructions
- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- NEVER proactively create documentation files unless explicitly requested