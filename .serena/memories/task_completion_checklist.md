# Task Completion Checklist

When completing any development task in this project, follow these steps:

## 1. Code Formatting (MUST RUN)
```bash
poe format
```
This runs all formatters (ruff, black, isort) to ensure consistent code style.

## 2. Verification (MUST RUN)
```bash
poe verify
```
This runs:
- Linting with ruff
- Type checking with mypy

Fix any errors before proceeding.

## 3. Run Tests (MUST RUN)
```bash
poe test
```
Ensure all tests pass. For coverage verification:
```bash
poe test-cov-check
```
This ensures test coverage is at least 85%.

## 4. Error Resolution Order
If CI or checks fail, fix in this order:
1. **Formatting errors** - Run `poe format`
2. **Type errors** - Fix with full line context, check Optional types, add type narrowing
3. **Linting errors** - Address ruff warnings
4. **Test failures** - Fix broken tests, add missing tests

## 5. Common Issues and Fixes

### Line Length Errors
- Break strings with parentheses
- Use multi-line function calls
- Split long imports

### Type Errors
- Add None checks for Optional types
- Use type narrowing (isinstance, assert)
- Match existing type patterns
- Avoid `Any` type - use specific types

### Test Issues
- For async test discovery issues, try:
  ```bash
  PYTEST_DISABLE_PLUGIN_AUTOLOAD="" uv run --frozen pytest
  ```
- Ensure test classes start with `Test`
- Ensure test functions start with `test_`
- Use `anyio` for async tests, not `asyncio`

## 6. Pre-Commit Checklist
- [ ] Run `poe format`
- [ ] Run `poe verify` and fix all issues
- [ ] Run `poe test` and ensure all pass
- [ ] Check `git status` to review changes
- [ ] Verify no secrets or sensitive data in code

## 7. Complete Workflow Command
For a full check before committing:
```bash
poe check
```
This runs format + verify + test-cov-check + docs check.

## Important Reminders
- **NO MAGIC NUMBERS** - Use class constants
- **Private properties** - Prefix with `_`
- **Type hints required** for all functions
- **Docstrings required** for public APIs
- **Test new features** - One test file per implementation file
- **Follow existing patterns** exactly