# Suggested Commands for Development

## Package Management (uv only!)
```bash
# Install dependencies
uv sync

# Add a new dependency
uv add package_name

# Add a dev dependency  
uv add --dev package_name

# Upgrade a specific package
uv add --dev package_name --upgrade-package package_name

# Run the application
uv run blockether_peekle data.pkl

# Run Python scripts
uv run python3 script.py
```

## Development Commands (using poethepoet)

### Formatting
```bash
# Format all code (ruff + black + isort)
poe format

# Individual formatters
poe format-ruff    # Run ruff formatter
poe format-black   # Run black formatter
poe format-isort   # Run isort formatter
```

### Linting and Type Checking
```bash
# Run both lint and typecheck
poe verify

# Run individually
poe lint       # Run ruff linter
poe typecheck  # Run mypy type checking
```

### Testing
```bash
# Run tests
poe test

# Run tests with coverage
poe test-cov

# Run tests with coverage and fail if under 85%
poe test-cov-check

# Run pytest directly with custom args
uv run python3 -m pytest [args]
```

### Documentation
```bash
# Serve documentation locally
poe docs-serve

# Build documentation
poe docs-build

# Check documentation structure
poe check-docs
```

### Cleaning
```bash
# Clean everything
poe clean

# Clean Python cache files
poe clean-pyc

# Clean uv cache
poe clean-cache
```

### Complete Workflow
```bash
# Run full check (format + verify + test + docs check)
poe check
```

## Git Commands (Darwin/macOS)
```bash
# Common git operations
git status
git diff
git add .
git commit -m "message"
git push
git pull
git log --oneline -10
```

## File System Commands (Darwin/macOS)
```bash
# List files
ls -la

# Find files
find . -name "*.py"

# Search in files (use ripgrep if available)
grep -r "pattern" .
rg "pattern"  # ripgrep (faster)

# Directory navigation
cd path/to/directory
pwd  # print working directory

# File operations
cp source dest     # copy
mv source dest     # move/rename  
rm file           # remove file
rm -rf directory  # remove directory
```

## Project Entry Points
```bash
# Run the main application
uv run blockether_peekle pickle_file.pkl

# Run from Python module
uv run python3 -m blockether_peekle.main pickle_file.pkl
```

## Important Reminders
- **NEVER use pip** - Always use uv
- **NEVER use `@latest`** syntax with uv
- Run `poe verify` before committing changes
- Run `poe test` after making changes
- Use `poe format` to auto-format code