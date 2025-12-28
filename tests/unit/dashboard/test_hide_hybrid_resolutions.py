"""
Hide Hybrid Resolutions Tests for Dashboard JavaScript.

Feature 1084: Tests that verify only exact-match resolutions are rendered
in the unified resolution selector (hides hybrid buckets).

These tests use static analysis of JavaScript source code to verify:
1. Resolution filter uses exact property
2. Saved resolution validation checks exact property
3. Feature 1084 comment exists for traceability

Run: pytest tests/unit/dashboard/test_hide_hybrid_resolutions.py -v
"""

import re
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parents[3]


def read_unified_resolution_js() -> str:
    """Read the unified-resolution.js file content."""
    repo_root = get_repo_root()
    file_path = repo_root / "src" / "dashboard" / "unified-resolution.js"
    assert file_path.exists(), f"unified-resolution.js not found at {file_path}"
    return file_path.read_text()


class TestHideHybridResolutions:
    """Test that hybrid resolutions are hidden from the selector."""

    def test_has_feature_1084_comment(self) -> None:
        """Verify Feature 1084 comment exists for traceability."""
        content = read_unified_resolution_js()

        assert "Feature 1084" in content, (
            "Missing Feature 1084 reference in unified-resolution.js. "
            "Add a comment for traceability."
        )

    def test_render_filters_by_exact_property(self) -> None:
        """Verify render() filters UNIFIED_RESOLUTIONS by exact property."""
        content = read_unified_resolution_js()

        # Look for filter with exact property
        pattern = r"filter\s*\(\s*r\s*=>\s*r\.exact\s*!==\s*false\s*\)"
        assert re.search(pattern, content), (
            "render() not filtering by exact property. "
            "Use .filter(r => r.exact !== false) to hide hybrid buckets (Feature 1084)."
        )

    def test_load_resolution_validates_exact(self) -> None:
        """Verify loadResolution() validates saved resolution is exact."""
        content = read_unified_resolution_js()

        # Look for exact check in loadResolution
        pattern = r"r\.key\s*===\s*saved\s*&&\s*r\.exact\s*!==\s*false"
        assert re.search(pattern, content), (
            "loadResolution() not validating exact property. "
            "Add r.exact !== false check to fallback hybrid saved preferences (Feature 1084)."
        )


class TestExactResolutionsConfig:
    """Test that config.js has correct exact property values."""

    def test_config_has_exact_resolutions(self) -> None:
        """Verify config.js defines exact:true for 1m, 5m, 1h, Day."""
        repo_root = get_repo_root()
        config_path = repo_root / "src" / "dashboard" / "config.js"
        assert config_path.exists(), f"config.js not found at {config_path}"
        content = config_path.read_text()

        # Verify exact:true resolutions
        exact_resolutions = ["'1m'", "'5m'", "'1h'", "'D'"]
        for res in exact_resolutions:
            pattern = rf"key:\s*{res}.*?exact:\s*true"
            assert re.search(
                pattern, content, re.DOTALL
            ), f"Resolution {res} should have exact: true in config.js"

    def test_config_has_hybrid_resolutions_marked(self) -> None:
        """Verify config.js has exact:false for hybrid resolutions."""
        repo_root = get_repo_root()
        config_path = repo_root / "src" / "dashboard" / "config.js"
        content = config_path.read_text()

        # Verify at least some exact:false resolutions exist
        pattern = r"exact:\s*false"
        matches = re.findall(pattern, content)
        assert len(matches) >= 4, (
            "Expected at least 4 hybrid resolutions with exact: false. "
            "Found: {len(matches)}"
        )
