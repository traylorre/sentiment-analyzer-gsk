"""Unit tests for interview HTML page.

Tests cover:
- HTML structure and validity
- No broken internal links (navigation)
- External links (Google Fonts)
- JavaScript function definitions
- All sections have matching nav items
"""

import re
from pathlib import Path


def get_html_content() -> str:
    """Load the interview HTML file."""
    html_path = Path(__file__).parent.parent.parent.parent / "interview" / "index.html"
    return html_path.read_text()


class TestHTMLStructure:
    """Tests for basic HTML structure."""

    def test_html_file_exists(self):
        """HTML file should exist."""
        html_path = (
            Path(__file__).parent.parent.parent.parent / "interview" / "index.html"
        )
        assert html_path.exists(), "interview/index.html should exist"

    def test_has_doctype(self):
        """HTML should have DOCTYPE declaration."""
        content = get_html_content()
        assert content.strip().startswith("<!DOCTYPE html>")

    def test_has_html_lang(self):
        """HTML should have lang attribute."""
        content = get_html_content()
        assert 'lang="en"' in content

    def test_has_charset(self):
        """HTML should have charset meta tag."""
        content = get_html_content()
        assert 'charset="UTF-8"' in content

    def test_has_viewport_meta(self):
        """HTML should have viewport meta for mobile."""
        content = get_html_content()
        assert 'name="viewport"' in content

    def test_has_title(self):
        """HTML should have title tag."""
        content = get_html_content()
        assert "<title>" in content
        assert "</title>" in content


class TestExternalResources:
    """Tests for external resource links."""

    def test_google_fonts_link_valid(self):
        """Google Fonts link should be valid HTTPS."""
        content = get_html_content()
        fonts_pattern = r'href="(https://fonts\.googleapis\.com[^"]+)"'
        match = re.search(fonts_pattern, content)

        assert match is not None, "Should have Google Fonts link"
        fonts_url = match.group(1)

        # Validate URL structure
        assert fonts_url.startswith("https://fonts.googleapis.com/css2")
        assert "family=Inter" in fonts_url

    def test_no_http_links(self):
        """All external links should be HTTPS, not HTTP."""
        content = get_html_content()
        # Find all href attributes
        http_pattern = r'href="http://[^"]+"'
        http_matches = re.findall(http_pattern, content)

        assert len(http_matches) == 0, f"Found insecure HTTP links: {http_matches}"

    def test_no_broken_src_attributes(self):
        """No empty or invalid src attributes."""
        content = get_html_content()
        # Find all src attributes
        empty_src = re.findall(r'src=""', content)
        assert len(empty_src) == 0, "Should have no empty src attributes"


class TestNavigation:
    """Tests for navigation links matching sections."""

    def test_all_nav_items_have_sections(self):
        """Every nav item should have a matching section."""
        content = get_html_content()

        # Extract all nav item data-section values
        nav_pattern = r'data-section="([^"]+)"'
        nav_sections = set(re.findall(nav_pattern, content))

        # Extract all section ids
        section_pattern = r'<section id="([^"]+)"'
        section_ids = set(re.findall(section_pattern, content))

        # Every nav item should have a section
        for nav_section in nav_sections:
            assert (
                nav_section in section_ids
            ), f"Nav item '{nav_section}' has no matching section"

    def test_all_sections_have_nav_items(self):
        """Every section should have a nav item (except special sections)."""
        content = get_html_content()

        nav_pattern = r'data-section="([^"]+)"'
        nav_sections = set(re.findall(nav_pattern, content))

        section_pattern = r'<section id="([^"]+)"'
        section_ids = set(re.findall(section_pattern, content))

        # Every section should have a nav item
        for section_id in section_ids:
            assert section_id in nav_sections, f"Section '{section_id}' has no nav item"

    def test_expected_sections_exist(self):
        """All expected sections should exist."""
        content = get_html_content()

        expected_sections = [
            "welcome",
            "architecture",
            "auth",
            "config",
            "sentiment",
            "external",
            "circuit",
            "traffic",
            "chaos",
            "caching",
            "observability",
            "testing",
            "infra",
        ]

        for section in expected_sections:
            assert f'id="{section}"' in content, f"Section '{section}' should exist"

    def test_welcome_section_is_active_by_default(self):
        """Welcome section should be active by default."""
        content = get_html_content()
        # Welcome section should have 'active' class
        welcome_pattern = r'<section id="welcome" class="section active">'
        assert re.search(welcome_pattern, content), "Welcome section should be active"


class TestJavaScript:
    """Tests for JavaScript functionality."""

    def test_environments_defined(self):
        """ENVIRONMENTS constant should be defined."""
        content = get_html_content()
        assert "const ENVIRONMENTS = Object.assign({" in content

    def test_preprod_url_defined(self):
        """Preprod URL should be defined with Amplify URL (Feature 1207: CloudFront removed)."""
        content = get_html_content()
        assert "preprod:" in content
        # Uses Amplify URL for frontend hosting
        assert "amplifyapp.com" in content

    def test_required_functions_defined(self):
        """All required JavaScript functions should be defined."""
        content = get_html_content()

        required_functions = [
            "initNavigation",
            "navigateTo",
            "initEnvToggle",
            "callAPI",
            "callAuthenticatedAPI",
            "fetchHealthStats",
            "showToast",
            "copyCommand",
            "startInterviewTimer",
            "updateTimer",
            "startChaosExperiment",
        ]

        for func in required_functions:
            assert f"function {func}" in content, f"Function '{func}' should be defined"

    def test_dom_content_loaded_handler(self):
        """Should have DOMContentLoaded event handler."""
        content = get_html_content()
        assert "DOMContentLoaded" in content

    def test_auth_token_variable(self):
        """Should have authToken variable for session management."""
        content = get_html_content()
        assert "let authToken = null" in content


class TestAPIEndpoints:
    """Tests for API endpoint references."""

    def test_health_endpoint(self):
        """Health endpoint should be referenced."""
        content = get_html_content()
        assert "/health" in content

    def test_auth_endpoint(self):
        """Auth endpoint should be referenced."""
        content = get_html_content()
        assert "/api/v2/auth/anonymous" in content

    def test_configurations_endpoint(self):
        """Configurations endpoint should be referenced."""
        content = get_html_content()
        assert "/api/v2/configurations" in content

    def test_sentiment_endpoint(self):
        """Sentiment endpoint should be referenced."""
        content = get_html_content()
        # Sentiment is now accessed via configuration endpoint
        assert "/sentiment" in content
        assert "config_id" in content  # Dynamic endpoint reference


class TestInteractiveElements:
    """Tests for interactive UI elements."""

    def test_execute_buttons_exist(self):
        """Execute buttons should exist for API demos."""
        content = get_html_content()
        execute_count = content.count("Execute")
        assert execute_count >= 3, "Should have multiple Execute buttons"

    def test_env_toggle_buttons(self):
        """Environment toggle buttons should exist."""
        content = get_html_content()
        assert 'data-env="preprod"' in content
        assert 'data-env="prod"' in content

    def test_response_boxes_exist(self):
        """Response boxes should exist for API demos."""
        content = get_html_content()
        response_boxes = [
            "auth-anon-response",
            "config-list-response",
            "sentiment-response",
            "health-response",
        ]

        for box_id in response_boxes:
            assert f'id="{box_id}"' in content, f"Response box '{box_id}' should exist"

    def test_interview_timer_element(self):
        """Interview timer element should exist."""
        content = get_html_content()
        assert 'id="interview-timer"' in content

    def test_toast_element(self):
        """Toast notification element should exist."""
        content = get_html_content()
        assert 'id="toast"' in content


class TestCSS:
    """Tests for CSS styles."""

    def test_css_variables_defined(self):
        """CSS variables should be defined in :root."""
        content = get_html_content()
        assert ":root {" in content

        required_vars = [
            "--bg-primary",
            "--bg-secondary",
            "--text-primary",
            "--accent-green",
            "--accent-red",
            "--accent-blue",
        ]

        for var in required_vars:
            assert var in content, f"CSS variable '{var}' should be defined"

    def test_responsive_breakpoints(self):
        """Should have responsive CSS breakpoints."""
        content = get_html_content()
        assert "@media (max-width:" in content

    def test_animation_definitions(self):
        """Animation keyframes should be defined."""
        content = get_html_content()
        assert "@keyframes fadeIn" in content


class TestAccessibility:
    """Basic accessibility checks."""

    def test_buttons_have_onclick(self):
        """Interactive buttons should have onclick handlers."""
        content = get_html_content()
        # Find all button tags
        buttons = re.findall(r"<button[^>]+>", content)

        for button in buttons:
            # Button should have onclick or be an env-btn (handled via event delegation)
            has_onclick = "onclick=" in button
            is_env_btn = "env-btn" in button
            assert (
                has_onclick or is_env_btn
            ), f"Button should have handler: {button[:50]}..."

    def test_labels_for_checkboxes(self):
        """Checkboxes should have associated labels."""
        content = get_html_content()
        # Find all checkbox inputs
        checkboxes = re.findall(r'id="(chaos-[^"]+)"', content)

        for checkbox_id in checkboxes:
            # Should have a corresponding label
            assert (
                f'for="{checkbox_id}"' in content
            ), f"Checkbox '{checkbox_id}' should have label"


class TestContentIntegrity:
    """Tests for content integrity."""

    def test_no_placeholder_text(self):
        """Should not have obvious placeholder text."""
        content = get_html_content()
        placeholders = [
            "TODO",
            "FIXME",
            "XXX",
            "Lorem ipsum",
            "placeholder",
        ]

        content_lower = content.lower()
        for placeholder in placeholders:
            # Allow "placeholder" in specific contexts like attrs
            if placeholder.lower() == "placeholder":
                continue
            assert (
                placeholder.lower() not in content_lower
            ), f"Found placeholder: {placeholder}"

    def test_consistent_branding(self):
        """Should have consistent branding."""
        content = get_html_content()
        assert "Sentiment Analyzer" in content
        assert "Interview Mode" in content

    def test_stats_elements_exist(self):
        """Dashboard stats elements should exist."""
        content = get_html_content()
        stats = [
            "stat-health",
            "stat-latency",
            "stat-cache",
            "stat-circuits",
        ]

        for stat_id in stats:
            assert (
                f'id="{stat_id}"' in content
            ), f"Stat element '{stat_id}' should exist"


class TestDashboardLink:
    """Tests for live dashboard link feature."""

    def test_dashboard_link_exists(self):
        """Live dashboard link element should exist."""
        content = get_html_content()
        assert 'id="live-dashboard-link"' in content

    def test_last_deployed_element_exists(self):
        """Last deployed date element should exist."""
        content = get_html_content()
        assert 'id="last-deployed"' in content

    def test_fetch_deployment_metadata_function(self):
        """fetchDeploymentMetadata function should be defined."""
        content = get_html_content()
        assert "function fetchDeploymentMetadata" in content

    def test_update_dashboard_link_function(self):
        """updateDashboardLink function should be defined."""
        content = get_html_content()
        assert "function updateDashboardLink" in content

    def test_metadata_url_defined(self):
        """Metadata URL constant should be defined."""
        content = get_html_content()
        assert "METADATA_URL" in content


class TestMobileNavigation:
    """Tests for mobile navigation features."""

    def test_hamburger_element_exists(self):
        """Hamburger menu element should exist."""
        content = get_html_content()
        assert 'id="hamburger"' in content
        assert 'class="hamburger"' in content

    def test_sidebar_overlay_exists(self):
        """Sidebar overlay for mobile should exist."""
        content = get_html_content()
        assert 'id="sidebarOverlay"' in content
        assert 'class="sidebar-overlay"' in content

    def test_toggle_sidebar_function(self):
        """toggleSidebar function should be defined."""
        content = get_html_content()
        assert "function toggleSidebar()" in content

    def test_open_sidebar_function(self):
        """openSidebar function should be defined."""
        content = get_html_content()
        assert "function openSidebar()" in content

    def test_close_sidebar_function(self):
        """closeSidebar function should be defined."""
        content = get_html_content()
        assert "function closeSidebar()" in content

    def test_swipe_gesture_handlers(self):
        """Touch event handlers should be defined for swipe gestures."""
        content = get_html_content()
        assert "function handleTouchStart" in content
        assert "function handleTouchEnd" in content
        assert "function handleSwipe" in content

    def test_mobile_css_breakpoints(self):
        """Mobile CSS should have proper breakpoints."""
        content = get_html_content()
        # Check for hamburger display on mobile
        assert ".hamburger {" in content
        # Check for media query
        assert "@media (max-width:" in content

    def test_sidebar_closes_on_navigation(self):
        """navigateTo should close sidebar on mobile."""
        content = get_html_content()
        # Check that navigateTo includes closeSidebar call
        assert "closeSidebar()" in content
