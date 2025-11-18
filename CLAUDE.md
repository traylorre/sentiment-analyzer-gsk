# sentiment-analyzer-gsk Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-16

## Active Technologies

- Python 3.11 (001-interactive-dashboard-demo)

## Project Structure

```text
src/
tests/
```

## Commands

```bash
# Run tests
pytest

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
```

## Code Style

- Python 3.11: Follow PEP 8, use black for formatting
- Linting: ruff (replaces flake8, isort, bandit)
- Line length: 88 characters
- Configuration: pyproject.toml (single source of truth)

## Recent Changes

- 001-interactive-dashboard-demo: Added Python 3.11

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
