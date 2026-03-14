"""T022: Integration test for X-Ray subsegment on SendGrid API call.

Verifies via static analysis that sendgrid_service.py:
- Has @tracer.capture_method decorator on the send_email method
- Sets annotations for recipient_count, template_name, and sendgrid_status

Uses static analysis (ast + source inspection) to avoid importing the module
and pulling in sendgrid/aws_lambda_powertools dependencies not available in CI.
"""

import ast
from pathlib import Path

import pytest

# Mark as integration test
pytestmark = pytest.mark.integration

SOURCE_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "lambdas"
    / "notification"
    / "sendgrid_service.py"
)


def _load_source() -> str:
    """Load the sendgrid_service.py source text."""
    assert SOURCE_PATH.exists(), f"Source file not found: {SOURCE_PATH}"
    return SOURCE_PATH.read_text(encoding="utf-8")


def _parse_ast(source: str) -> ast.Module:
    """Parse the source into an AST module."""
    return ast.parse(source)


def _find_class(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Return the first class definition matching class_name."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _find_method(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef | None:
    """Return the first method definition matching method_name inside a class."""
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return node
    return None


def _decorator_names(func_node: ast.FunctionDef) -> list[str]:
    """Return a flat list of decorator expressions as unparsed strings."""
    names = []
    for decorator in func_node.decorator_list:
        names.append(ast.unparse(decorator))
    return names


def _find_put_annotation_keys(func_node: ast.FunctionDef) -> set[str]:
    """Return all string literal keys passed to tracer.put_annotation() calls."""
    keys: set[str] = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        # Match tracer.put_annotation(key, value)
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "put_annotation":
            continue
        # First positional arg is the key
        if node.args and isinstance(node.args[0], ast.Constant):
            keys.add(node.args[0].value)
    return keys


class TestSendGridXRaySubsegment:
    """Verify that send_email is wrapped in an X-Ray subsegment via static analysis."""

    def test_source_file_exists(self):
        """The sendgrid_service.py source file must exist at the expected path."""
        assert SOURCE_PATH.exists(), f"sendgrid_service.py not found at {SOURCE_PATH}"

    def test_send_email_has_capture_method_decorator(self):
        """send_email must be decorated with @tracer.capture_method.

        aws_lambda_powertools Tracer.capture_method wraps the function in an
        X-Ray subsegment automatically, so every SendGrid call is traced.
        """
        source = _load_source()
        tree = _parse_ast(source)

        email_service = _find_class(tree, "EmailService")
        assert email_service is not None, "EmailService class not found in source"

        send_email = _find_method(email_service, "send_email")
        assert send_email is not None, "send_email method not found in EmailService"

        decorator_exprs = _decorator_names(send_email)
        assert "tracer.capture_method" in decorator_exprs, (
            f"@tracer.capture_method not found on send_email. "
            f"Found decorators: {decorator_exprs}"
        )

    def test_send_email_annotates_recipient_count(self):
        """send_email must call tracer.put_annotation('recipient_count', ...).

        Annotating recipient_count enables X-Ray filter expressions to query
        traces by the number of recipients in a single call.
        """
        source = _load_source()
        tree = _parse_ast(source)

        email_service = _find_class(tree, "EmailService")
        assert email_service is not None, "EmailService class not found in source"

        send_email = _find_method(email_service, "send_email")
        assert send_email is not None, "send_email method not found in EmailService"

        keys = _find_put_annotation_keys(send_email)
        assert "recipient_count" in keys, (
            f"tracer.put_annotation('recipient_count', ...) not found in send_email. "
            f"Annotations found: {keys}"
        )

    def test_send_email_annotates_template_name(self):
        """send_email must call tracer.put_annotation('template_name', ...).

        Annotating template_name (derived from subject) allows X-Ray traces to
        be filtered by the type of email sent (magic link, alert, digest).
        """
        source = _load_source()
        tree = _parse_ast(source)

        email_service = _find_class(tree, "EmailService")
        assert email_service is not None, "EmailService class not found in source"

        send_email = _find_method(email_service, "send_email")
        assert send_email is not None, "send_email method not found in EmailService"

        keys = _find_put_annotation_keys(send_email)
        assert "template_name" in keys, (
            f"tracer.put_annotation('template_name', ...) not found in send_email. "
            f"Annotations found: {keys}"
        )

    def test_send_email_annotates_sendgrid_status(self):
        """send_email must call tracer.put_annotation('sendgrid_status', ...).

        Annotating the HTTP status code from SendGrid's response enables
        distinguishing successful 202 responses from unexpected status codes
        in X-Ray trace filtering.
        """
        source = _load_source()
        tree = _parse_ast(source)

        email_service = _find_class(tree, "EmailService")
        assert email_service is not None, "EmailService class not found in source"

        send_email = _find_method(email_service, "send_email")
        assert send_email is not None, "send_email method not found in EmailService"

        keys = _find_put_annotation_keys(send_email)
        assert "sendgrid_status" in keys, (
            f"tracer.put_annotation('sendgrid_status', ...) not found in send_email. "
            f"Annotations found: {keys}"
        )

    def test_all_required_annotations_present(self):
        """All three required X-Ray annotations must be present in send_email.

        This is a combined assertion that fails with a full diff of what is
        missing vs what is expected.
        """
        source = _load_source()
        tree = _parse_ast(source)

        email_service = _find_class(tree, "EmailService")
        assert email_service is not None, "EmailService class not found in source"

        send_email = _find_method(email_service, "send_email")
        assert send_email is not None, "send_email method not found in EmailService"

        required = {"recipient_count", "template_name", "sendgrid_status"}
        found = _find_put_annotation_keys(send_email)
        missing = required - found
        assert not missing, (
            f"Missing X-Ray annotations in send_email: {sorted(missing)}. "
            f"Found: {sorted(found)}"
        )
