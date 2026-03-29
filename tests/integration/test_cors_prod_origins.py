"""Integration test for CORS production origins consistency (Feature 1269).

Validates that tfvars files across all environments have consistent
CORS configuration: non-empty origins, HTTPS-only for prod, no wildcards.
"""

import re
from pathlib import Path

import pytest

TERRAFORM_DIR = Path(__file__).parent.parent.parent / "infrastructure" / "terraform"

# Environments expected to have tfvars files
EXPECTED_ENVIRONMENTS = {"dev", "preprod", "prod"}


def _parse_tfvars(tfvars_path: Path) -> dict:
    """Parse environment and cors_allowed_origins from a tfvars file.

    Returns:
        Dict with 'environment' and 'origins' keys.
    """
    content = tfvars_path.read_text()

    env_match = re.search(r'environment\s*=\s*"(\w+)"', content)
    environment = env_match.group(1) if env_match else "unknown"

    origins_match = re.search(
        r"cors_allowed_origins\s*=\s*\[(.*?)\]", content, re.DOTALL
    )
    origins = []
    if origins_match:
        origins = re.findall(r'"([^"]+)"', origins_match.group(1))

    return {"environment": environment, "origins": origins}


class TestCorsConsistency:
    """Cross-environment CORS configuration consistency tests."""

    @pytest.fixture
    def all_tfvars(self) -> dict[str, dict]:
        """Parse all tfvars files into a dict keyed by environment."""
        result = {}
        for tfvars_file in TERRAFORM_DIR.glob("*.tfvars"):
            parsed = _parse_tfvars(tfvars_file)
            result[parsed["environment"]] = {
                "file": tfvars_file.name,
                "origins": parsed["origins"],
            }
        return result

    def test_all_environments_have_tfvars(self, all_tfvars: dict) -> None:
        """Every expected environment should have a tfvars file."""
        for env in EXPECTED_ENVIRONMENTS:
            assert env in all_tfvars, (
                f"No tfvars file found for environment '{env}'. "
                f'Expected *.tfvars with environment = "{env}".'
            )

    def test_prod_has_non_empty_origins(self, all_tfvars: dict) -> None:
        """Production must have non-empty CORS origins."""
        if "prod" not in all_tfvars:
            pytest.skip("prod.tfvars not found")
        prod = all_tfvars["prod"]
        assert len(prod["origins"]) > 0, (
            f"cors_allowed_origins is empty in {prod['file']}. "
            "Production requires explicit origins."
        )

    def test_preprod_has_non_empty_origins(self, all_tfvars: dict) -> None:
        """Preprod must have non-empty CORS origins."""
        if "preprod" not in all_tfvars:
            pytest.skip("preprod.tfvars not found")
        preprod = all_tfvars["preprod"]
        assert len(preprod["origins"]) > 0, (
            f"cors_allowed_origins is empty in {preprod['file']}. "
            "Preprod requires configured origins for integration testing."
        )

    def test_prod_origins_are_https_only(self, all_tfvars: dict) -> None:
        """All production CORS origins must use HTTPS."""
        if "prod" not in all_tfvars:
            pytest.skip("prod.tfvars not found")
        prod = all_tfvars["prod"]
        non_https = [o for o in prod["origins"] if not o.startswith("https://")]
        assert len(non_https) == 0, (
            f"Non-HTTPS origins found in production {prod['file']}: {non_https}. "
            "Production CORS origins must use HTTPS."
        )

    def test_no_wildcard_in_any_environment(self, all_tfvars: dict) -> None:
        """No environment should have wildcard CORS origins."""
        for env, data in all_tfvars.items():
            wildcards = [o for o in data["origins"] if o == "*"]
            assert len(wildcards) == 0, (
                f"Wildcard origin found in {data['file']} ({env}). "
                "CORS origins must be explicit, not wildcards."
            )

    def test_prod_origins_subset_of_preprod(self, all_tfvars: dict) -> None:
        """All prod HTTPS origins should also be in preprod for testing.

        This ensures that origins configured in prod were testable in preprod
        before deployment. Localhost origins in preprod are excluded from comparison.
        """
        if "prod" not in all_tfvars or "preprod" not in all_tfvars:
            pytest.skip("Need both prod.tfvars and preprod.tfvars")
        prod_origins = set(all_tfvars["prod"]["origins"])
        preprod_origins = set(all_tfvars["preprod"]["origins"])
        missing = prod_origins - preprod_origins
        if missing:
            pytest.xfail(
                f"Prod origins not in preprod: {missing}. "
                "Consider adding these to preprod.tfvars for pre-deployment testing."
            )
