"""
SSE Same-Origin Configuration Tests for Dashboard JavaScript.

Feature 1068: Tests that verify the SSE URL handling logic correctly
treats empty strings as valid same-origin configuration.

These tests use static analysis of JavaScript source code to verify:
1. The connectSSE function uses explicit null/undefined checks
2. Empty string '' is NOT treated as "unconfigured"
3. Nullish coalescing (??) is used instead of logical OR (||)

Run: pytest tests/unit/dashboard/test_sse_same_origin.py -v
"""

import re
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parents[3]


def read_timeseries_js() -> str:
    """Read the timeseries.js file content."""
    repo_root = get_repo_root()
    timeseries_path = repo_root / "src" / "dashboard" / "timeseries.js"
    assert timeseries_path.exists(), f"timeseries.js not found at {timeseries_path}"
    return timeseries_path.read_text()


class TestSSEURLHandling:
    """Test SSE URL handling logic in timeseries.js."""

    def test_file_exists(self) -> None:
        """Verify timeseries.js exists."""
        repo_root = get_repo_root()
        timeseries_path = repo_root / "src" / "dashboard" / "timeseries.js"
        assert timeseries_path.exists(), "timeseries.js not found"

    def test_connect_sse_method_exists(self) -> None:
        """Verify connectSSE method exists."""
        content = read_timeseries_js()
        assert "connectSSE()" in content, "connectSSE method not found"

    def test_no_truthy_check_for_baseurl(self) -> None:
        """
        Verify the code does NOT use truthy check (!baseUrl) for URL validation.

        The bug was: if (!baseUrl) - treats empty string as falsy (invalid)
        The fix uses explicit null/undefined checks instead.
        """
        content = read_timeseries_js()

        # Find the connectSSE function
        connect_sse_match = re.search(
            r"connectSSE\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert connect_sse_match, "Could not find connectSSE method body"

        method_body = connect_sse_match.group(1)

        # The bug pattern: using truthy check on baseUrl
        # This incorrectly treats empty string as "not configured"
        bug_pattern = r"if\s*\(\s*!baseUrl\s*\)"

        # Should NOT find the bug pattern
        assert not re.search(bug_pattern, method_body), (
            "Found truthy check (!baseUrl) in connectSSE - this treats empty string "
            "as unconfigured. Use explicit null/undefined check instead.\n"
            f"Method body:\n{method_body[:500]}..."
        )

    def test_uses_nullish_coalescing_or_explicit_checks(self) -> None:
        """
        Verify the code uses nullish coalescing (??) or explicit null checks.

        Correct patterns:
        - sseUrl ?? apiUrl ?? ''
        - sseUrl === null || sseUrl === undefined
        """
        content = read_timeseries_js()

        # Find the connectSSE function
        connect_sse_match = re.search(
            r"connectSSE\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert connect_sse_match, "Could not find connectSSE method body"

        method_body = connect_sse_match.group(1)

        # Should use nullish coalescing (??) instead of logical OR (||)
        # for baseUrl assignment
        has_nullish_coalescing = "??" in method_body

        # Or should have explicit null/undefined checks
        has_explicit_null_check = (
            "=== null" in method_body or "=== undefined" in method_body
        )

        assert has_nullish_coalescing or has_explicit_null_check, (
            "connectSSE should use nullish coalescing (??) or explicit null checks "
            "to handle empty string same-origin configuration correctly.\n"
            f"Method body:\n{method_body[:500]}..."
        )

    def test_has_feature_1068_comment(self) -> None:
        """Verify the Feature 1068 fix has a comment for traceability."""
        content = read_timeseries_js()

        # Look for Feature 1068 reference
        assert "Feature 1068" in content or "1068" in content, (
            "Missing Feature 1068 reference in timeseries.js. "
            "The fix should have a comment for traceability."
        )

    def test_baseurl_fallback_allows_empty_string(self) -> None:
        """
        Verify the baseUrl assignment allows empty string through.

        The bug was: const baseUrl = this.sseBaseUrl || this.apiBaseUrl;
        This treats '' as falsy and skips to the next option.

        The fix should use: const baseUrl = sseUrl ?? apiUrl ?? '';
        This allows empty string through as a valid value.
        """
        content = read_timeseries_js()

        # Find the connectSSE function
        connect_sse_match = re.search(
            r"connectSSE\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert connect_sse_match, "Could not find connectSSE method body"

        method_body = connect_sse_match.group(1)

        # Bug pattern: using || which treats empty string as falsy
        bug_pattern = (
            r"const\s+baseUrl\s*=\s*this\.sseBaseUrl\s*\|\|\s*this\.apiBaseUrl"
        )

        assert not re.search(bug_pattern, method_body), (
            "Found logical OR (||) for baseUrl assignment. This treats empty string "
            "as falsy. Use nullish coalescing (??) instead:\n"
            "  Bad:  const baseUrl = this.sseBaseUrl || this.apiBaseUrl\n"
            "  Good: const baseUrl = sseUrl ?? apiUrl ?? ''\n"
        )


class TestSSEURLEdgeCases:
    """Test edge case handling documentation in the code."""

    def test_same_origin_comment_exists(self) -> None:
        """Verify there's a comment explaining same-origin handling."""
        content = read_timeseries_js()

        # Should have documentation about same-origin behavior
        same_origin_patterns = [
            r"same.?origin",
            r"empty string",
            r"'' is valid",
        ]

        has_documentation = any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in same_origin_patterns
        )

        assert has_documentation, (
            "Missing documentation about same-origin URL handling. "
            "Add a comment explaining that empty string is valid for same-origin requests."
        )

    def test_warning_only_for_null_undefined(self) -> None:
        """
        Verify warning is only logged for actual null/undefined values.

        The warning should NOT trigger for empty string (same-origin).
        """
        content = read_timeseries_js()

        # Find the connectSSE function
        connect_sse_match = re.search(
            r"connectSSE\(\)\s*\{([\s\S]*?)\n\s{4}\}",
            content,
            re.MULTILINE,
        )
        assert connect_sse_match, "Could not find connectSSE method body"

        method_body = connect_sse_match.group(1)

        # The warning should be preceded by explicit null/undefined check
        # Look for pattern like:
        #   if (... === null ... === undefined ...)
        #   console.warn('No SSE base URL configured')
        has_warning = "console.warn" in method_body

        if has_warning:
            # If there's a warning, verify it's guarded by explicit checks
            has_proper_guard = (
                "=== null" in method_body and "=== undefined" in method_body
            )
            assert has_proper_guard, (
                "Warning found but without explicit null/undefined checks. "
                "The warning should only trigger for actually unconfigured URLs, "
                "not for empty string (same-origin)."
            )
