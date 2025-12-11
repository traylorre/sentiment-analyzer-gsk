"""Unit tests for SRI validator.

Feature: 090-security-first-burndown
"""

from pathlib import Path

from src.validators.sri import (
    SRIFinding,
    SRISeverity,
    SRIValidationResult,
    is_cdn_url,
    is_jit_cdn,
    validate_html_file,
    validate_sri,
)


class TestIsCdnUrl:
    """Tests for is_cdn_url function."""

    def test_jsdelivr_detected(self) -> None:
        """CDN jsdelivr.net should be detected."""
        assert is_cdn_url("https://cdn.jsdelivr.net/npm/chart.js")

    def test_cdnjs_detected(self) -> None:
        """CDN cdnjs.cloudflare.com should be detected."""
        assert is_cdn_url(
            "https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"
        )

    def test_tailwind_detected(self) -> None:
        """CDN tailwindcss.com should be detected."""
        assert is_cdn_url("https://cdn.tailwindcss.com")

    def test_local_not_detected(self) -> None:
        """Local paths should not be detected as CDN."""
        assert not is_cdn_url("/static/app.js")
        assert not is_cdn_url("./vendor/chart.js")

    def test_self_hosted_not_detected(self) -> None:
        """Self-hosted URLs should not be detected as CDN."""
        assert not is_cdn_url("https://example.com/scripts/app.js")


class TestIsJitCdn:
    """Tests for is_jit_cdn function."""

    def test_tailwind_is_jit(self) -> None:
        """Tailwind CDN is a JIT compiler."""
        assert is_jit_cdn("https://cdn.tailwindcss.com")

    def test_jsdelivr_not_jit(self) -> None:
        """jsDelivr is not a JIT compiler."""
        assert not is_jit_cdn("https://cdn.jsdelivr.net/npm/chart.js")


class TestValidateHtmlFile:
    """Tests for validate_html_file function."""

    def test_script_without_integrity_detected(self, tmp_path: Path) -> None:
        """CDN script without integrity should be detected as CRITICAL."""
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )

        findings = validate_html_file(html_file)

        assert len(findings) == 1
        assert findings[0].severity == SRISeverity.CRITICAL
        assert "missing integrity" in findings[0].message.lower()

    def test_script_with_integrity_passes(self, tmp_path: Path) -> None:
        """CDN script with integrity and crossorigin should pass."""
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js" '
            'integrity="sha384-abc123" crossorigin="anonymous"></script>'
        )

        findings = validate_html_file(html_file)

        # Should have no critical/high findings
        assert not any(
            f.severity in (SRISeverity.CRITICAL, SRISeverity.HIGH) for f in findings
        )

    def test_stylesheet_without_integrity_detected(self, tmp_path: Path) -> None:
        """CDN stylesheet without integrity should be detected as HIGH."""
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<link href="https://cdn.jsdelivr.net/npm/daisyui/dist/full.css" rel="stylesheet">'
        )

        findings = validate_html_file(html_file)

        assert len(findings) == 1
        assert findings[0].severity == SRISeverity.HIGH
        assert findings[0].resource_type == "link"

    def test_local_script_not_flagged(self, tmp_path: Path) -> None:
        """Local scripts should not require SRI."""
        html_file = tmp_path / "test.html"
        html_file.write_text('<script src="/static/app.js"></script>')

        findings = validate_html_file(html_file)

        assert len(findings) == 0

    def test_jit_cdn_info_only(self, tmp_path: Path) -> None:
        """JIT CDN (Tailwind) should only generate INFO finding."""
        html_file = tmp_path / "test.html"
        html_file.write_text('<script src="https://cdn.tailwindcss.com"></script>')

        findings = validate_html_file(html_file)

        assert len(findings) == 1
        assert findings[0].severity == SRISeverity.INFO
        assert "JIT compiler" in findings[0].message

    def test_missing_crossorigin_medium_severity(self, tmp_path: Path) -> None:
        """CDN resource with integrity but missing crossorigin should be MEDIUM."""
        html_file = tmp_path / "test.html"
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js" integrity="sha384-abc123"></script>'
        )

        findings = validate_html_file(html_file)

        assert len(findings) == 1
        assert findings[0].severity == SRISeverity.MEDIUM
        assert "crossorigin" in findings[0].message.lower()


class TestValidateSri:
    """Tests for validate_sri function."""

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        """Files in node_modules should be excluded."""
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        html_file = node_modules / "package" / "test.html"
        html_file.parent.mkdir(parents=True)
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )

        result = validate_sri(tmp_path)

        assert result.files_scanned == 0
        assert len(result.findings) == 0

    def test_excludes_test_fixtures(self, tmp_path: Path) -> None:
        """Files in tests/fixtures should be excluded."""
        fixtures = tmp_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        html_file = fixtures / "test.html"
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )

        result = validate_sri(tmp_path)

        assert result.files_scanned == 0

    def test_scans_src_directory(self, tmp_path: Path) -> None:
        """Files in src should be scanned."""
        src = tmp_path / "src"
        src.mkdir()
        html_file = src / "index.html"
        html_file.write_text(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        )

        result = validate_sri(tmp_path)

        assert result.files_scanned == 1
        assert len(result.findings) == 1

    def test_pass_rate_calculation(self, tmp_path: Path) -> None:
        """Pass rate should be calculated correctly for resources with issues."""
        html_file = tmp_path / "test.html"
        # Only resources that generate findings are counted
        html_file.write_text(
            """
            <script src="https://cdn.jsdelivr.net/npm/lodash"></script>
            <script src="https://cdn.jsdelivr.net/npm/jquery"></script>
            """
        )

        result = validate_sri(tmp_path)

        # Both CDN scripts lack integrity - both generate findings
        assert result.cdn_resources_found == 2
        assert result.cdn_resources_with_sri == 0
        assert result.pass_rate == 0.0


class TestSRIValidationResult:
    """Tests for SRIValidationResult class."""

    def test_is_passing_with_no_findings(self) -> None:
        """Should pass with no findings."""
        result = SRIValidationResult()
        assert result.is_passing

    def test_is_passing_with_info_only(self) -> None:
        """Should pass with only INFO findings."""
        result = SRIValidationResult(
            findings=[
                SRIFinding(
                    file_path="test.html",
                    line_number=1,
                    resource_type="script",
                    url="https://cdn.tailwindcss.com",
                    severity=SRISeverity.INFO,
                    message="JIT compiler",
                )
            ]
        )
        assert result.is_passing

    def test_is_failing_with_critical(self) -> None:
        """Should fail with CRITICAL findings."""
        result = SRIValidationResult(
            findings=[
                SRIFinding(
                    file_path="test.html",
                    line_number=1,
                    resource_type="script",
                    url="https://cdn.jsdelivr.net/npm/chart.js",
                    severity=SRISeverity.CRITICAL,
                    message="Missing integrity",
                )
            ]
        )
        assert not result.is_passing

    def test_is_failing_with_high(self) -> None:
        """Should fail with HIGH findings."""
        result = SRIValidationResult(
            findings=[
                SRIFinding(
                    file_path="test.html",
                    line_number=1,
                    resource_type="link",
                    url="https://cdn.jsdelivr.net/npm/daisyui",
                    severity=SRISeverity.HIGH,
                    message="Missing integrity",
                )
            ]
        )
        assert not result.is_passing

    def test_pass_rate_empty(self) -> None:
        """Pass rate should be 1.0 with no CDN resources."""
        result = SRIValidationResult()
        assert result.pass_rate == 1.0
