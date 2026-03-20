"""T008: Regression test for ingestion handler import.

Ensures that `from src.lambdas.ingestion.handler import lambda_handler`
succeeds without ImportError. This prevents the packaging regression
(missing transitive dependencies) from recurring.
"""


def test_ingestion_handler_imports_without_error():
    """Importing lambda_handler must not raise ImportError.

    This guards against:
    - Missing __init__.py files in the package chain
    - Broken transitive imports within the handler module
    - Dependency drift between requirements files
    """
    from src.lambdas.ingestion.handler import lambda_handler

    assert callable(lambda_handler)
