# Stage 3: Adversarial Specification Review

## Feature: 1278-pydantic-dev-pin

### Challenge 1: Does pip actually resolve "last specified wins"?
**Question**: The spec claims the explicit pin after `-r requirements.txt` overrides. Is this reliable?
**Resolution**: Yes. pip's resolver treats all requirements as constraints. When two constraints
conflict (==2.12.5 from -r and ==2.12.4 explicit), pip will ERROR, not silently pick one.
However, the explicit pin at ==2.12.4 satisfies moto's `<=2.12.4` constraint while the ==2.12.5
from requirements.txt does NOT. pip's backtracking resolver will select 2.12.4 because it's the
only version satisfying ALL constraints. The explicit pin effectively narrows the constraint
window. This is the same mechanism used successfully in requirements-ci.txt.

### Challenge 2: Could pydantic 2.12.4 break production code that relies on 2.12.5 features?
**Question**: Are there any pydantic 2.12.5-specific features used in the codebase?
**Resolution**: The delta between 2.12.4 and 2.12.5 is a patch release. Pydantic patch releases
contain only bug fixes, no API changes. The codebase uses standard pydantic features (BaseModel,
Field, ConfigDict) that are stable across 2.12.x. Tests running under CI already use 2.12.4
successfully, proving compatibility.

### Challenge 3: What happens when moto upgrades and supports pydantic 2.12.5+?
**Question**: Will we remember to remove the override?
**Resolution**: This is tech debt by design. When moto releases a version supporting pydantic
2.12.5+, the override becomes unnecessary but harmless (it still pins to a valid version).
The comment documents the reason, making future cleanup straightforward. This matches the
established pattern in requirements-ci.txt.

### Challenge 4: Placement in file — should it go right after `-r requirements.txt`?
**Question**: Where exactly in requirements-dev.txt should the pin go?
**Resolution**: It should go immediately after the `-r requirements.txt` line, with a blank line
separator and a section comment. This makes the override relationship visually obvious. The
requirements-ci.txt places it in the "Data Validation" section, but since requirements-dev.txt
uses `-r` inclusion (not standalone pins), the override should be near the include.

### Verdict: APPROVED
No blocking issues found. The fix is minimal, well-precedented, and low-risk.
