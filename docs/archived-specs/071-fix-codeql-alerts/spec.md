# Feature Specification: Fix CodeQL Security Alerts

**Feature Branch**: `071-fix-codeql-alerts`
**Created**: 2025-12-09
**Status**: Draft
**Input**: User description: "fix CodeQL alerts https://github.com/traylorre/sentiment-analyzer-gsk/security"

## Overview

This feature addresses 3 HIGH severity security alerts identified by GitHub CodeQL scanning:

1. **Log Injection (CWE-117)**: User-provided values logged without sanitization in `ohlc.py` (lines 121, 261)
2. **Clear-text Logging of Sensitive Data (CWE-312)**: Sensitive data logged in `secrets.py` (line 228)

These vulnerabilities could allow attackers to inject malicious content into logs or expose sensitive credentials in log files.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Security Team Reviews Logs Safely (Priority: P1)

A security analyst reviews application logs to investigate potential incidents. The logs should not contain injected malicious content that could exploit log viewing tools or mislead investigations.

**Why this priority**: Log injection can compromise security investigations and potentially exploit log analysis tools. This is the highest priority as it affects security operations.

**Independent Test**: Can be tested by sending requests with log injection payloads (e.g., newlines, ANSI escape codes) and verifying logs are sanitized.

**Acceptance Scenarios**:

1. **Given** an attacker sends a request with a ticker symbol containing newline characters, **When** the request is logged, **Then** the newline characters are sanitized and the log entry appears as a single line
2. **Given** an attacker sends a request with ANSI escape codes in parameters, **When** the request is logged, **Then** the escape codes are stripped or encoded
3. **Given** a user sends a legitimate request with special characters, **When** the request is logged, **Then** the original intent is preserved while dangerous characters are neutralized

---

### User Story 2 - Operations Team Troubleshoots Without Credential Exposure (Priority: P1)

An operations engineer reviews application logs to troubleshoot API connectivity issues. The logs should provide useful diagnostic information without exposing sensitive credentials.

**Why this priority**: Clear-text credential logging creates severe security risk if logs are accessed by unauthorized parties. Equal priority to log injection.

**Independent Test**: Can be tested by triggering secret retrieval and verifying logs contain redacted values instead of actual secrets.

**Acceptance Scenarios**:

1. **Given** the application retrieves a secret from secrets manager, **When** the retrieval is logged for debugging, **Then** the secret value is redacted (e.g., "***REDACTED***")
2. **Given** secret retrieval fails, **When** the error is logged, **Then** the log contains diagnostic information but no partial secret values
3. **Given** logs are forwarded to CloudWatch, **When** the logs are viewed, **Then** no sensitive credentials are visible

---

### User Story 3 - Developer Maintains Code Quality (Priority: P2)

A developer modifies logging code in the future. The codebase should have clear patterns for safe logging that prevent reintroduction of these vulnerabilities.

**Why this priority**: Prevents regression but not as urgent as fixing existing vulnerabilities.

**Independent Test**: Can be tested by reviewing code patterns and running local SAST tools.

**Acceptance Scenarios**:

1. **Given** a developer adds new logging statements, **When** they follow the established patterns, **Then** CodeQL scanning passes without new alerts
2. **Given** the codebase has logging utilities, **When** a developer needs to log user input, **Then** there is a clear `sanitize_for_log()` function to use

---

### Edge Cases

- What happens when sanitization removes all characters from user input? (Log placeholder like "[empty after sanitization]")
- How does the system handle multi-byte UTF-8 characters in log sanitization? (Preserve valid UTF-8, only strip control characters)
- What if a legitimate ticker symbol contains characters that look like injection? (Should not break valid inputs)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST sanitize all user-provided values before including them in log statements
- **FR-002**: System MUST strip or encode newline characters (CR, LF, CRLF) from logged user input
- **FR-003**: System MUST strip or encode ANSI escape sequences from logged user input
- **FR-004**: System MUST redact sensitive data (API keys, passwords, tokens) before logging
- **FR-005**: System MUST provide a centralized `sanitize_for_log()` utility function for consistent sanitization
- **FR-006**: System MUST NOT log the actual value of secrets retrieved from secrets manager
- **FR-007**: System MUST preserve enough information in sanitized logs to support troubleshooting

### Assumptions

- Existing `sanitize_for_log()` helper in `src/lambdas/shared/logging_utils.py` can be extended if needed
- Existing `redact_sensitive_fields()` helper can be used for credential redaction
- Log format changes are acceptable as long as diagnostic value is preserved

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: CodeQL scanning reports 0 open alerts for `py/log-injection` rule
- **SC-002**: CodeQL scanning reports 0 open alerts for `py/clear-text-logging-sensitive-data` rule
- **SC-003**: Local `make sast` passes without warnings related to logging
- **SC-004**: All existing unit tests continue to pass after changes
- **SC-005**: Log output remains useful for debugging (developers can still trace requests)

## Out of Scope

- Comprehensive audit of all logging statements (only fixing CodeQL-flagged issues)
- Changes to log retention or access policies
- Log aggregation or SIEM integration
- Performance optimization of logging
