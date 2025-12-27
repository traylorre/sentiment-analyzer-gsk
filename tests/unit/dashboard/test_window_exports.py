"""
Window Export Validation Tests for Dashboard JavaScript Files.

These tests verify that all required window exports exist in vanilla JS dashboard files
via static analysis (regex parsing). No browser required.

This test module prevents regressions like Feature 1066 where functions were defined
but not exported to the window object, causing silent failures in app.js.

Run: pytest tests/unit/dashboard/test_window_exports.py -v
"""

import re
from pathlib import Path

import pytest

from tests.unit.dashboard.window_export_registry import WINDOW_EXPORT_REGISTRY


def find_window_exports(js_content: str) -> set[str]:
    """
    Parse JavaScript file content to find window.X = X export patterns.

    Matches patterns like:
        window.functionName = functionName;
        window.ClassName = ClassName;
        window.varName = varName

    Args:
        js_content: JavaScript source code as string

    Returns:
        Set of exported function/variable names
    """
    # Pattern: window.<name> = <name> with optional semicolon/comma and comments
    # Handles:
    #   window.foo = foo;
    #   window.foo = foo  // comment
    #   window.foo = foo,
    pattern = r"window\.(\w+)\s*=\s*\1\s*[;,]?\s*(?://.*)?$"
    return set(re.findall(pattern, js_content, re.MULTILINE))


def get_repo_root() -> Path:
    """Get the repository root directory."""
    # Navigate up from tests/unit/dashboard/ to repo root
    return Path(__file__).parents[3]


class TestWindowExportsExist:
    """Test that all required window exports exist in dashboard JS files."""

    @pytest.mark.parametrize(
        "js_file,expected_exports",
        list(WINDOW_EXPORT_REGISTRY.items()),
        ids=lambda x: x if isinstance(x, str) else None,
    )
    def test_window_exports_exist(
        self, js_file: str, expected_exports: list[str]
    ) -> None:
        """
        Verify all required window exports exist in the specified JS file.

        Args:
            js_file: Relative path to JavaScript file from repo root
            expected_exports: List of function names that must be exported
        """
        repo_root = get_repo_root()
        js_path = repo_root / js_file

        # Verify file exists
        assert js_path.exists(), (
            f"JavaScript file not found: {js_file}\n"
            f"Expected at: {js_path}\n"
            f"Repo root: {repo_root}"
        )

        # Parse file content
        content = js_path.read_text()
        actual_exports = find_window_exports(content)

        # Find missing exports
        missing = set(expected_exports) - actual_exports

        # Provide clear error message
        assert not missing, (
            f"\nMissing window exports in {js_file}:\n"
            f"  Missing: {', '.join(sorted(missing))}\n"
            f"  Expected pattern: window.<name> = <name>;\n"
            f"\n"
            f"  Found exports: {', '.join(sorted(actual_exports)) or '(none)'}\n"
            f"\n"
            f"  Fix: Add the following lines to {js_file}:\n"
            + "\n".join(f"    window.{name} = {name};" for name in sorted(missing))
        )

    def test_registry_has_entries(self) -> None:
        """Verify the registry is not empty."""
        assert WINDOW_EXPORT_REGISTRY, "Window export registry is empty"
        assert (
            len(WINDOW_EXPORT_REGISTRY) >= 3
        ), f"Expected at least 3 files in registry, found {len(WINDOW_EXPORT_REGISTRY)}"


class TestWindowExportPattern:
    """Test the window export pattern matching logic."""

    def test_finds_simple_export(self) -> None:
        """Test finding a simple window.foo = foo; pattern."""
        js = "window.myFunc = myFunc;"
        exports = find_window_exports(js)
        assert "myFunc" in exports

    def test_finds_export_without_semicolon(self) -> None:
        """Test finding export without trailing semicolon."""
        js = "window.myFunc = myFunc"
        exports = find_window_exports(js)
        assert "myFunc" in exports

    def test_finds_export_with_comment(self) -> None:
        """Test finding export with trailing comment."""
        js = "window.myFunc = myFunc;  // Feature 1065"
        exports = find_window_exports(js)
        assert "myFunc" in exports

    def test_ignores_different_assignment(self) -> None:
        """Test that window.foo = bar (different names) is not matched."""
        js = "window.myFunc = otherFunc;"
        exports = find_window_exports(js)
        assert "myFunc" not in exports

    def test_finds_multiple_exports(self) -> None:
        """Test finding multiple exports."""
        js = """
window.func1 = func1;
window.func2 = func2;
window.func3 = func3;
"""
        exports = find_window_exports(js)
        assert exports == {"func1", "func2", "func3"}

    def test_handles_empty_file(self) -> None:
        """Test handling empty file content."""
        exports = find_window_exports("")
        assert exports == set()

    def test_handles_no_exports(self) -> None:
        """Test handling file with no window exports."""
        js = """
function myFunc() {
    console.log("hello");
}
const x = 5;
"""
        exports = find_window_exports(js)
        assert exports == set()
