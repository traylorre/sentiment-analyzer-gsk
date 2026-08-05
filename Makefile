.PHONY: help install validate fmt fmt-check lint security sast audit-pragma audit-exemptions check-banned-terms test test-local test-unit test-integration test-e2e test-spec test-mutation \
        check-test-target-headers check-waitforresponse-race check-iam-patterns check-terraform-version \
        compose-preflight localstack-up localstack-down localstack-wait localstack-logs localstack-status \
        tf-init tf-plan tf-apply tf-destroy tf-init-local tf-plan-local tf-apply-local tf-destroy-local \
        cost cost-diff cost-baseline cost-check clean clean-all \
        check-annotation-budget check-annotation-pii regenerate-mermaid-url tf-output validate-mermaid \
        verify-dual-emit verify-dual-emit-json

SHELL := /bin/bash
TF_DIR := infrastructure/terraform
ENV ?= dev
COST_MONTHLY_LIMIT ?= 50
COST_DELTA_LIMIT ?= 10

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# ============================================================================
# Setup
# ============================================================================

install: ## Install all dependencies
	pip install -e ".[dev]"
	pip install -r requirements.txt
	pre-commit install --install-hooks
	pre-commit install --hook-type pre-push
	@echo "$(GREEN)✓ Development environment ready$(NC)"

# ============================================================================
# Validation (Zero AWS Cost)
# ============================================================================

# `make -n validate` cannot produce a trustworthy result, so it is refused outright.
#
# Recipe lines containing $(MAKE) run even under -n, by design, so that recursive make
# can show the whole tree. The -n then propagates to those sub-makes through MAKEFLAGS,
# each does nothing and exits 0, and the driver below records seven clean stages without
# a single check having executed. That is precisely the false all-clear this feature
# exists to remove, so it must not be reachable by adding one flag.
#
# The guard has to fire at parse time. A shell test inside the recipe would not work:
# under -n, lines that do not contain $(MAKE) are printed rather than run, so the guard
# would be echoed while the stages it guards went ahead.
ifneq (,$(findstring n,$(firstword $(MAKEFLAGS))))
ifneq (,$(filter validate,$(MAKECMDGOALS)))
$(error `make -n validate` is not supported: -n propagates to the sub-makes, so every \
stage would report success without running. Run `make validate` for a real result.)
endif
endif

# Stages run in sequence; the driver continues past a failure so one run shows every
# problem (FR-001). Before this was a driver it was a prerequisite list, and make stops
# at the first failed prerequisite, which is how a second broken stage stayed hidden
# behind a first one long enough for this feature's spec to be written without knowing
# it existed.
#
# fmt-check, not fmt: a gate must not modify the tree it is judging (FR-004).
#
# Sub-make exit codes are not meaningful beyond zero versus non-zero. $(MAKE) reports 2
# for any recipe failure regardless of what the underlying tool returned, so PASS/FAIL
# is the only signal available here, and the stage's own output carries the detail.
validate: ## Run every validation stage, report each, and gate on the blocking ones
	@set -uo pipefail; \
	declare -a ORDER=() MODE=() OUTCOME=(); \
	run_stage() { \
		local target="$$1" label="$$2" mode="$$3" rc=0; \
		echo ""; \
		printf '%b\n' "$(YELLOW)━━━ $$label ━━━$(NC)"; \
		$(MAKE) --no-print-directory "$$target" || rc=$$?; \
		ORDER+=("$$label"); MODE+=("$$mode"); \
		if [ "$$mode" = "ADVISORY" ]; then OUTCOME+=("reported"); \
		elif [ "$$rc" -eq 0 ]; then OUTCOME+=("PASS"); \
		else OUTCOME+=("FAIL"); fi; \
	}; \
	run_stage fmt-check                  "format check"        BLOCKING; \
	run_stage lint                       "lint"                BLOCKING; \
	run_stage security                   "dependency audit"    ADVISORY; \
	run_stage sast                       "static analysis"     BLOCKING; \
	run_stage check-banned-terms         "legacy terms"        BLOCKING; \
	run_stage check-test-target-headers  "test target headers" BLOCKING; \
	run_stage check-waitforresponse-race "e2e race guard"      BLOCKING; \
	run_stage check-terraform-version    "terraform version"   BLOCKING; \
	run_stage check-iam-patterns         "iam arn patterns"    BLOCKING; \
	echo ""; \
	echo "================ validate summary ================"; \
	fails=0; blocking=0; \
	for i in "$${!ORDER[@]}"; do \
		printf "  %-21s %-10s %s\n" "$${ORDER[$$i]}" "$${MODE[$$i]}" "$${OUTCOME[$$i]}"; \
		if [ "$${MODE[$$i]}" = "BLOCKING" ]; then \
			blocking=$$((blocking + 1)); \
			if [ "$${OUTCOME[$$i]}" = "FAIL" ]; then fails=$$((fails + 1)); fi; \
		fi; \
	done; \
	echo "=================================================="; \
	if [ "$$fails" -eq 0 ]; then \
		printf '%b\n' "$(GREEN)✓ PASS: all $$blocking blocking stages passed.$(NC)"; \
	else \
		printf '%b\n' "$(RED)✗ FAIL: $$fails of $$blocking blocking stages failed. See output above.$(NC)"; \
		exit 1; \
	fi

check-waitforresponse-race: ## Detect act-then-wait waitForResponse races in frontend/tests/e2e/
	@echo "Checking waitForResponse race ordering..."
	@python3 scripts/scan-waitforresponse-race.py

check-terraform-version: ## Verify the terraform binary and every pinned surface match .terraform-version
	@scripts/check-terraform-version.sh

# The guard exists because confusing the two dashboards has caused repeated incidents,
# so every e2e file must declare what it targets. It previously accepted only the two
# dashboard declarations, which left no way to be honest about a test that targets
# neither: eleven files test API Gateway, Cognito, WAF, CloudFront and log groups. They
# could not pass without claiming to test a UI they do not touch, so the stage simply
# failed forever and stopped being read. A third sanctioned declaration fixes that
# without weakening the rule: a file with no declaration at all still fails (FR-025).
#
# The globs are NOT recursive. Adding a subdirectory under either e2e tree would make
# its tests invisible to this guard while it continued to report success.
check-test-target-headers: ## Verify all e2e test files declare what they target
	@echo "Checking test target headers..."
	@MISSING=$$(cd $(CURDIR) && grep -rLE "Target:.*(Dashboard|Infrastructure)" frontend/tests/e2e/*.spec.ts tests/e2e/test_*.py 2>/dev/null); \
	if [ -n "$$MISSING" ]; then \
		printf '%b\n' "$(RED)✗ Files missing Target: header:$(NC)"; \
		echo "$$MISSING"; \
		echo "Add one of these as the first line, naming what the file actually exercises:"; \
		echo "  // Target: Customer Dashboard (Next.js/Amplify)"; \
		echo "  # Target: Admin Dashboard (Lambda HTMX)"; \
		echo "  # Target: Infrastructure (API Gateway, WAF, Cognito, CloudFront, ...)"; \
		exit 1; \
	fi
	@printf '%b\n' "$(GREEN)✓ All e2e test files declare a target$(NC)"

fmt: ## Format Python code (Ruff)
	ruff format src tests
	@echo "$(GREEN)✓ Formatting complete$(NC)"

fmt-check: ## Check formatting without changes
	ruff format --check src tests

lint: ## Run linters
	ruff check src tests
	@if [ -d "$(TF_DIR)" ]; then terraform -chdir=$(TF_DIR) validate; fi
	@echo "$(GREEN)✓ Linting passed$(NC)"

# ADVISORY, and labelled that way in the validate summary, because this target is
# structurally unable to fail: the scan's exit code is discarded by `|| true` and the
# last command is an unconditional echo. It reports; it does not gate.
#
# The summary prints "reported" for it rather than PASS. Printing PASS for a stage that
# cannot fail is the same misrepresentation this feature exists to remove, only quieter.
#
# Promotion to blocking is deferred by FR-005a until the dependency-alert backlog clears
# (the scan currently exits non-zero on real findings, so flipping it now would wedge the
# gate on work that is already tracked elsewhere). A board card tracks the promotion.
security: ## Run security scanners (ADVISORY: reports findings, does not gate)
	pip-audit --ignore-vuln PYSEC-2024-58 || true
	@echo "$(YELLOW)⚠ Review security findings above$(NC)"

sast: ## Run SAST (Static Application Security Testing) - Semgrep
	@echo "$(YELLOW)Running Semgrep (comprehensive SAST)...$(NC)"
	@command -v semgrep >/dev/null 2>&1 || { echo "$(RED)✗ Semgrep not installed. Install: pip install -r requirements-dev.txt$(NC)"; exit 1; }
	semgrep scan --config auto --error --severity ERROR --severity WARNING src/
	@echo "$(GREEN)✓ SAST scan complete$(NC)"

audit-pragma: ## Audit pragma comments (# noqa) and dead scanning suppressions
	@echo "$(YELLOW)=== [BLOCKING] Unused # noqa comments (RUF100) ===$(NC)"
	ruff check --extend-select RUF100 src/ tests/ scripts/
	@echo ""
	@echo "$(YELLOW)=== [BLOCKING] Dead inline scanning suppressions ===$(NC)"
	@python3 scripts/check_dead_suppressions.py
	@echo ""
	@echo "$(GREEN)✓ Pragma audit complete$(NC)"

check-iam-patterns: ## Validate IAM ARN patterns match Terraform resource names
	@./scripts/check-iam-patterns.sh

check-banned-terms: ## Verify no legacy framework references remain
	@python3 scripts/check_banned_terms.py

audit-exemptions: ## Audit legacy-term exemptions (inline markers) for validity
	@python3 scripts/check_banned_terms.py --list-exemptions

# ============================================================================
# Testing
# ============================================================================

test-local: test-unit test-integration ## Run all local tests (unit + integration)
	@echo "$(GREEN)✓ All local tests passed$(NC)"

test-unit: ## Run unit tests with moto mocks
	pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration: localstack-up localstack-wait ## Run integration tests with LocalStack
	LOCALSTACK_ENDPOINT=$(LOCALSTACK_ENDPOINT) pytest tests/integration/ -v
	@$(MAKE) localstack-down

test-e2e: ## Run E2E tests (requires preprod deployment)
	AWS_ENV=preprod pytest tests/e2e/ -v -m preprod

test: test-unit ## Alias for test-unit

test-spec: ## Run spec coherence validation
	@echo "$(YELLOW)Running spec coherence validation...$(NC)"
	@if [ -d "specs" ]; then \
		echo "Checking spec files for coherence..."; \
		for spec in specs/*/spec.md; do \
			if [ -f "$$spec" ]; then \
				grep -q "## Functional Requirements" "$$spec" || echo "$(RED)Missing FR section: $$spec$(NC)"; \
				grep -q "## Success Criteria" "$$spec" || echo "$(RED)Missing SC section: $$spec$(NC)"; \
			fi; \
		done; \
		echo "$(GREEN)Spec coherence check complete$(NC)"; \
	else \
		echo "$(YELLOW)No specs directory found$(NC)"; \
	fi

test-mutation: ## Run mutation tests (requires mutmut)
	@echo "$(YELLOW)Running mutation tests...$(NC)"
	@if command -v mutmut &>/dev/null; then \
		mutmut run || echo "$(YELLOW)Mutation testing complete (check results with: mutmut results)$(NC)"; \
	else \
		echo "$(YELLOW)mutmut not installed. Install with: pip install mutmut$(NC)"; \
	fi

# ============================================================================
# LocalStack
# ============================================================================

LOCALSTACK_ENDPOINT ?= http://localhost:4566
COMPOSE = docker compose

compose-preflight: ## Verify Docker CLI, daemon, and Compose v2 plugin before any Compose action
	@command -v docker >/dev/null 2>&1 || { \
		echo -e "$(RED)✗ Docker CLI not found.$(NC)"; \
		echo "  Install Docker Engine first: https://docs.docker.com/engine/install/"; \
		echo "  (Ubuntu/Debian: sudo apt-get install docker.io)"; \
		exit 1; }
	@docker info >/dev/null 2>&1 || { \
		echo -e "$(RED)✗ Docker daemon unreachable (the CLI itself is installed).$(NC)"; \
		echo "  Start it (e.g. sudo systemctl start docker) or check that your user is in the docker group."; \
		exit 1; }
	@docker compose version >/dev/null 2>&1 || { \
		echo -e "$(RED)✗ Docker Compose v2 plugin missing (Docker daemon is healthy).$(NC)"; \
		echo "  Ubuntu/Debian docker.io install: sudo apt-get install docker-compose-v2"; \
		echo "  Docker CE repo install:          sudo apt-get install docker-compose-plugin"; \
		echo "  Compose-free cleanup remains available via 'make clean'."; \
		exit 1; }
	@test -n "$$LOCALSTACK_AUTH_TOKEN" || { \
		echo -e "$(RED)✗ LOCALSTACK_AUTH_TOKEN is not set (Docker and Compose are healthy).$(NC)"; \
		echo "  LocalStack images v2026.3.1+ require an auth token (app.localstack.cloud)."; \
		echo "  Plain:     export LOCALSTACK_AUTH_TOKEN=<token>"; \
		echo "  1Password: export LOCALSTACK_AUTH_TOKEN=\$$(op read 'op://<vault>/LocalStack/auth-token')"; \
		echo "  Compose-free cleanup remains available via 'make clean'."; \
		exit 1; }

localstack-up: compose-preflight ## Start LocalStack (on failure the output includes recovery steps)
	@$(COMPOSE) up -d localstack || { \
		echo -e "$(RED)✗ LocalStack start failed or was interrupted.$(NC)"; \
		echo "  Recover by re-running 'make localstack-up' — it is safe to repeat."; \
		exit 1; }
	@echo "$(GREEN)LocalStack starting on :4566$(NC)"

localstack-down: compose-preflight ## Stop LocalStack
	$(COMPOSE) down

localstack-logs: compose-preflight ## Show LocalStack logs
	$(COMPOSE) logs -f localstack

localstack-wait: ## Wait for LocalStack to be healthy
	@echo "Waiting for LocalStack to be ready..."
	@for i in $$(seq 1 30); do \
		if curl -sf $(LOCALSTACK_ENDPOINT)/_localstack/health > /dev/null 2>&1; then \
			echo "$(GREEN)✓ LocalStack is ready$(NC)"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "$(RED)✗ LocalStack not ready after 30s$(NC)"; exit 1

localstack-status: ## Show LocalStack service status
	@curl -sf $(LOCALSTACK_ENDPOINT)/_localstack/health | python3 -m json.tool 2>/dev/null || \
		echo "$(RED)LocalStack not running$(NC)"

# ============================================================================
# Terraform
# ============================================================================

tf-init: ## Initialize Terraform
	terraform -chdir=$(TF_DIR) init

tf-init-local: ## Initialize Terraform for LocalStack
	tflocal -chdir=$(TF_DIR) init

tf-plan: ## Plan Terraform changes
	terraform -chdir=$(TF_DIR) plan -var="environment=$(ENV)" -out=tfplan

tf-plan-local: localstack-up localstack-wait ## Plan against LocalStack
	tflocal -chdir=$(TF_DIR) plan -var="environment=dev"

tf-apply: ## Apply Terraform (requires plan)
	terraform -chdir=$(TF_DIR) apply tfplan

tf-apply-local: ## Apply to LocalStack
	tflocal -chdir=$(TF_DIR) apply -auto-approve -var="environment=dev"

tf-destroy: ## Destroy infrastructure (with confirmation)
	terraform -chdir=$(TF_DIR) destroy -var="environment=$(ENV)"

tf-destroy-local: ## Destroy LocalStack resources
	tflocal -chdir=$(TF_DIR) destroy -auto-approve -var="environment=dev"

tf-output: ## Show Terraform outputs
	terraform -chdir=$(TF_DIR) output

# ============================================================================
# Cost Analysis
# ============================================================================

cost: ## Analyze infrastructure costs
	@scripts/cost-check.sh --preflight
	infracost breakdown --path $(TF_DIR) --format table

cost-diff: ## Compare costs to baseline
	infracost diff --path $(TF_DIR) --compare-to $(TF_DIR)/infracost-baseline.json

cost-check: ## Gate projected costs: total <= COST_MONTHLY_LIMIT, delta <= COST_DELTA_LIMIT (USD/month)
	@COST_MONTHLY_LIMIT="$(COST_MONTHLY_LIMIT)" COST_DELTA_LIMIT="$(COST_DELTA_LIMIT)" scripts/cost-check.sh

cost-baseline: ## Regenerate the committed baseline: writes $(TF_DIR)/infracost-baseline.json from the current tree; run after intentional infra changes and commit the result (the only mutating cost target)
	infracost breakdown --path $(TF_DIR) --format json --out-file $(TF_DIR)/infracost-baseline.json

# ============================================================================
# Documentation
# ============================================================================

regenerate-mermaid-url: ## Generate mermaid.live URL from architecture diagram
	@python scripts/regenerate-mermaid-url.py docs/diagrams/architecture.mmd

validate-mermaid: ## Validate mermaid diagram syntax
	@python scripts/regenerate-mermaid-url.py --validate-only docs/diagrams/architecture.mmd

# ============================================================================
# X-Ray Verification (Phase 7 gates)
# ============================================================================

verify-dual-emit: ## Run dual-emit verification gates (FR-109)
	@python scripts/verify-dual-emit.py --environment $(ENV)

verify-dual-emit-json: ## Run dual-emit verification gates (JSON output)
	@python scripts/verify-dual-emit.py --environment $(ENV) --json

check-annotation-pii: ## Check for PII in trace annotations (FR-184)
	@bash scripts/check-annotation-pii.sh

check-annotation-budget: ## Check annotation count budget (FR-193)
	@bash scripts/check-annotation-budget.sh

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Clean generated files
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/tfplan
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-all: compose-preflight clean localstack-down ## Clean everything including LocalStack
	$(COMPOSE) down -v
	rm -rf localstack-data
