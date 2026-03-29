"""Unit tests for CORS production origin validation (Feature 1269).

Validates that tfvars files have correct CORS configuration:
- prod.tfvars has non-empty cors_allowed_origins
- All production origins use HTTPS
- No wildcard origins in production
- preprod.tfvars also has non-empty cors_allowed_origins
"""

import re
from pathlib import Path

import pytest

# Path to terraform directory
TERRAFORM_DIR = Path(__file__).parent.parent.parent / "infrastructure" / "terraform"


def _parse_cors_origins(tfvars_path: Path) -> list[str]:
    """Parse cors_allowed_origins from a tfvars file.

    Handles multi-line lists with comments.

    Returns:
        List of origin strings, or empty list if not found.
    """
    content = tfvars_path.read_text()
    match = re.search(r"cors_allowed_origins\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not match:
        return []
    list_content = match.group(1)
    return re.findall(r'"([^"]+)"', list_content)


class TestCorsProdTfvars:
    """Validate prod.tfvars CORS configuration."""

    @pytest.fixture
    def prod_tfvars(self) -> Path:
        """Path to prod.tfvars."""
        return TERRAFORM_DIR / "prod.tfvars"

    @pytest.fixture
    def prod_origins(self, prod_tfvars: Path) -> list[str]:
        """Parse origins from prod.tfvars."""
        return _parse_cors_origins(prod_tfvars)

    def test_prod_tfvars_exists(self, prod_tfvars: Path) -> None:
        """prod.tfvars must exist."""
        assert prod_tfvars.exists(), f"Missing: {prod_tfvars}"

    def test_prod_cors_origins_non_empty(self, prod_origins: list[str]) -> None:
        """prod.tfvars must have at least one CORS origin (Feature 1269)."""
        assert len(prod_origins) > 0, (
            "cors_allowed_origins is empty in prod.tfvars. "
            "Production requires explicit origins for frontend requests."
        )

    def test_prod_cors_origins_all_https(self, prod_origins: list[str]) -> None:
        """All production CORS origins must use HTTPS."""
        for origin in prod_origins:
            assert origin.startswith("https://"), (
                f"Non-HTTPS origin in prod.tfvars: {origin}. "
                "Production CORS origins must use HTTPS."
            )

    def test_prod_cors_origins_no_wildcard(self, prod_origins: list[str]) -> None:
        """No production CORS origin should contain wildcard '*'."""
        for origin in prod_origins:
            assert "*" not in origin, (
                f"Wildcard origin in prod.tfvars: {origin}. "
                "Production CORS origins must be explicit, not wildcards."
            )

    def test_prod_cors_origins_no_localhost(self, prod_origins: list[str]) -> None:
        """No production CORS origin should be localhost."""
        for origin in prod_origins:
            assert "localhost" not in origin and "127.0.0.1" not in origin, (
                f"Localhost origin in prod.tfvars: {origin}. "
                "Production CORS origins must not include localhost."
            )


class TestCorsPreprodTfvars:
    """Validate preprod.tfvars CORS configuration."""

    @pytest.fixture
    def preprod_tfvars(self) -> Path:
        """Path to preprod.tfvars."""
        return TERRAFORM_DIR / "preprod.tfvars"

    @pytest.fixture
    def preprod_origins(self, preprod_tfvars: Path) -> list[str]:
        """Parse origins from preprod.tfvars."""
        return _parse_cors_origins(preprod_tfvars)

    def test_preprod_tfvars_exists(self, preprod_tfvars: Path) -> None:
        """preprod.tfvars must exist."""
        assert preprod_tfvars.exists(), f"Missing: {preprod_tfvars}"

    def test_preprod_cors_origins_non_empty(self, preprod_origins: list[str]) -> None:
        """preprod.tfvars must have at least one CORS origin."""
        assert len(preprod_origins) > 0, (
            "cors_allowed_origins is empty in preprod.tfvars. "
            "Preprod requires configured origins for integration testing."
        )

    def test_preprod_cors_origins_no_wildcard(self, preprod_origins: list[str]) -> None:
        """No preprod CORS origin should contain wildcard '*'."""
        for origin in preprod_origins:
            assert "*" not in origin, (
                f"Wildcard origin in preprod.tfvars: {origin}. "
                "Preprod CORS origins must be explicit, not wildcards."
            )
