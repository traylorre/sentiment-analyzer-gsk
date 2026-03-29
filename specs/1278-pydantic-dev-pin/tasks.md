# Tasks: 1278-pydantic-dev-pin

## Task 1: Add pydantic override pin to requirements-dev.txt
- **File**: `requirements-dev.txt`
- **Action**: Insert 2 lines after `-r requirements.txt` include (after current line 18 blank)
- **Lines to add**:
  ```
  # Override pydantic version from requirements.txt for moto compatibility
  pydantic==2.12.4  # pinned: moto[all]==5.1.22 requires pydantic<=2.12.4
  ```
- **Followed by**: blank line (before `# Testing Framework`)
- **Status**: NOT STARTED
- **Dependencies**: None

## Task 2: Verify pip resolution (dev)
- **Action**: Run `pip install --dry-run -r requirements-dev.txt` in clean venv
- **Expected**: Resolves successfully with pydantic 2.12.4
- **Status**: NOT STARTED
- **Dependencies**: Task 1

## Task 3: Verify pip resolution (ci — regression check)
- **Action**: Run `pip install --dry-run -r requirements-ci.txt`
- **Expected**: Continues to resolve with pydantic 2.12.4
- **Status**: NOT STARTED
- **Dependencies**: Task 1

## Task 4: Verify pip resolution (prod — regression check)
- **Action**: Run `pip install --dry-run -r requirements.txt`
- **Expected**: Resolves with pydantic 2.12.5
- **Status**: NOT STARTED
- **Dependencies**: Task 1
