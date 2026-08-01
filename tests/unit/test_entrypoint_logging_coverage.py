"""Contract C-7 coverage guard (feature 001-lambda-log-visibility).

Every DEPLOYED non-SSE Lambda entrypoint must call configure_lambda_logging()
at module import top-level, before any function definition. The entrypoint
set is DERIVED by glob, never hardcoded (AR#2 F4): a new src/lambdas/<name>/
handler.py enters the walked set automatically and fails here until wired.

Exclusions (documented, exact):
- sse_streaming: owner-deferred function with its own basicConfig(INFO)
  startup path and no awslambdaric (FR-006 forbids touching it).
- chaos_restore: code exists but the function is NOT deployed
  (see the TODO in infrastructure/terraform/main.tf). If it ever deploys, remove
  it from this set — the guard will then enforce the call.
"""

import re
from pathlib import Path

EXCLUDED_DIRS = {"sse_streaming", "chaos_restore"}
CALL_TOKEN = "configure_lambda_logging("
REPO_ROOT = Path(__file__).resolve().parents[2]
LAMBDAS_DIR = REPO_ROOT / "src" / "lambdas"


def _deployed_entrypoints() -> list[Path]:
    return sorted(
        p
        for p in LAMBDAS_DIR.glob("*/handler.py")
        if p.parent.name not in EXCLUDED_DIRS
    )


def test_glob_finds_expected_entrypoint_set():
    names = {p.parent.name for p in _deployed_entrypoints()}
    assert names, "no entrypoints found — src/lambdas layout changed?"
    # The six known functions must be present; superset allowed (a new
    # Lambda joins the guard automatically — that is the point).
    assert {
        "dashboard",
        "ingestion",
        "analysis",
        "metrics",
        "notification",
        "canary",
    } <= names


def test_every_deployed_entrypoint_calls_configure_lambda_logging():
    failures = []
    for handler in _deployed_entrypoints():
        source = handler.read_text()
        call_idx = source.find(CALL_TOKEN)
        if call_idx == -1:
            failures.append(f"{handler.relative_to(REPO_ROOT)}: no {CALL_TOKEN} call")
            continue
        # AR#3 criterion: call index must precede the first top-level def —
        # anchored line match, so docstrings/nested defs can't fool it.
        first_def = re.search(r"^def ", source, flags=re.MULTILINE)
        if first_def is not None and call_idx > first_def.start():
            failures.append(
                f"{handler.relative_to(REPO_ROOT)}: {CALL_TOKEN} appears after "
                "the first top-level def — must run at import, before handlers"
            )
    assert not failures, (
        "entrypoints missing import-time logging config:\n" + "\n".join(failures)
    )
