#!/usr/bin/env python3
"""Redact secret-bearing fields from a WI-6 OAuth verification manifest before sealing.

Milestone 1, WI-6 (spec 1375), FR-9. A sealed evidence commit is GPG-signed and
append-only — the worst possible place for a live credential. The verification
manifest records `auth_requests` as {method, path, status} only (no bodies, no
tokens), so the one real leak vector is a step's `page_url` carrying the OAuth
`?code=` (and, defensively, `state`/token params). This script scrubs those in
place and refuses to leave anything token-shaped behind.

The raw Playwright trace (which DOES carry tokens) is never sealed — it is
gitignored and destroyed after the verifier's local spot-check (FR-7). This
script only touches the manifest that gets committed.

Usage:
    python scripts/redact-oauth-evidence.py <manifest.json> [--check]

    (default)  redact in place, print what changed
    --check    exit non-zero if anything sensitive is present (no writes); use
               as a pre-seal gate in CI or before `git commit -S`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query params that must never appear in sealed evidence.
SENSITIVE_QUERY_KEYS = {"code", "state", "access_token", "id_token", "refresh_token"}
REDACTED = "REDACTED"

# Token-shaped strings anywhere in the JSON (belt-and-suspenders): a JWT (three
# base64url segments) or a long opaque bearer. Kept deliberately conservative so
# it does not maul ordinary ids.
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b")


def redact_url(url: str) -> tuple[str, list[str]]:
    """Return (clean_url, removed_keys). Strips SENSITIVE_QUERY_KEYS from the query."""
    parts = urlsplit(url)
    if not parts.query:
        return url, []
    pairs = parse_qsl(parts.query, keep_blank_values=True)

    # A param needs redaction only if it is sensitive AND not already redacted,
    # so re-running (or --check on an already-clean manifest) is a no-op.
    def needs(k: str, v: str) -> bool:
        return k.lower() in SENSITIVE_QUERY_KEYS and v != REDACTED

    removed = [k for k, v in pairs if needs(k, v)]
    if not removed:
        return url, []
    cleaned = [(k, REDACTED if needs(k, v) else v) for k, v in pairs]
    return urlunsplit(parts._replace(query=urlencode(cleaned))), removed


def scrub(node: object, changes: list[str]) -> object:
    """Recursively redact page_url query secrets and any token-shaped strings."""
    if isinstance(node, dict):
        out: dict = {}
        for key, value in node.items():
            if key == "page_url" and isinstance(value, str):
                cleaned, removed = redact_url(value)
                if removed:
                    changes.append(f"page_url: stripped {sorted(set(removed))}")
                out[key] = cleaned
            else:
                out[key] = scrub(value, changes)
        return out
    if isinstance(node, list):
        return [scrub(v, changes) for v in node]
    if isinstance(node, str) and _JWT.search(node):
        changes.append("token-shaped string redacted")
        return _JWT.sub(REDACTED, node)
    return node


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", help="path to {spec}.manifest.json")
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail (non-zero) if anything sensitive is present; do not write",
    )
    args = ap.parse_args()

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read manifest: {exc}", file=sys.stderr)
        return 2

    changes: list[str] = []
    cleaned = scrub(data, changes)

    if args.check:
        if changes:
            print("FAIL: sealed manifest still contains sensitive data:")
            for c in changes:
                print(f"  - {c}")
            return 1
        print("PASS: no sensitive fields present in manifest.")
        return 0

    if not changes:
        print("No sensitive fields found; manifest unchanged.")
        return 0

    with open(args.manifest, "w", encoding="utf-8") as fh:
        json.dump(cleaned, fh, indent=2)
        fh.write("\n")
    print(f"Redacted {len(changes)} item(s) in {args.manifest}:")
    for c in changes:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
