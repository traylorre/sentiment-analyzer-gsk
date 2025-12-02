.PHONY: help install install-tools validate fmt fmt-check lint security test test-local test-unit test-integration test-e2e \
        localstack-up localstack-down localstack-wait localstack-logs localstack-status \
        tf-init tf-plan tf-apply tf-destroy tf-init-local tf-plan-local tf-apply-local tf-destroy-local \
        cost cost-diff cost-baseline clean clean-all

SHELL := /bin/bash
TF_DIR := infrastructure/terraform
ENV ?= dev

# Colors
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

# ============================================================================
# Setup
# ============================================================================

install: ## Install all dependencies
	pip install -e ".[dev]"
	pip install -r requirements.txt
	pre-commit install
	@echo "$(GREEN)✓ Development environment ready$(NC)"

install-tools: ## Install CLI tools via aqua
	@if ! command -v aqua &>/dev/null; then \
		echo "$(YELLOW)Installing aqua...$(NC)"; \
		curl -sSfL https://raw.githubusercontent.com/aquaproj/aqua-installer/v3.0.1/aqua-installer | bash -s -- -v v2.27.4; \
		echo "$(YELLOW)Add to PATH: export PATH=\"\$$HOME/.local/share/aquaproj-aqua/bin:\$$PATH\"$(NC)"; \
	fi
	PATH="$$HOME/.local/share/aquaproj-aqua/bin:$$PATH" aqua i -l

# ============================================================================
# Validation (Zero AWS Cost)
# ============================================================================

validate: fmt lint security ## Run all validation (fmt + lint + security)
	@echo "$(GREEN)✓ All validation passed$(NC)"

fmt: ## Format Python code
	black src tests
	ruff format src tests
	@echo "$(GREEN)✓ Formatting complete$(NC)"

fmt-check: ## Check formatting without changes
	black --check src tests
	ruff format --check src tests

lint: ## Run linters
	ruff check src tests
	@if [ -d "$(TF_DIR)" ]; then terraform -chdir=$(TF_DIR) validate; fi
	@echo "$(GREEN)✓ Linting passed$(NC)"

security: ## Run security scanners
	pip-audit --ignore-vuln PYSEC-2024-58 || true
	@if command -v tfsec &>/dev/null && [ -d "$(TF_DIR)" ]; then tfsec $(TF_DIR) --soft-fail; fi
	@echo "$(YELLOW)⚠ Review security findings above$(NC)"

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

# ============================================================================
# LocalStack
# ============================================================================

LOCALSTACK_ENDPOINT ?= http://localhost:4566

localstack-up: ## Start LocalStack
	docker-compose up -d localstack
	@echo "$(GREEN)LocalStack starting on :4566$(NC)"

localstack-down: ## Stop LocalStack
	docker-compose down

localstack-logs: ## Show LocalStack logs
	docker-compose logs -f localstack

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
	infracost breakdown --path $(TF_DIR) --format table

cost-diff: ## Compare costs to baseline
	infracost diff --path $(TF_DIR) --compare-to infracost-baseline.json

cost-baseline: ## Save current costs as baseline
	infracost breakdown --path $(TF_DIR) --format json > infracost-baseline.json

# ============================================================================
# Cleanup
# ============================================================================

clean: ## Clean generated files
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf $(TF_DIR)/.terraform $(TF_DIR)/*.tfplan
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-all: clean localstack-down ## Clean everything including LocalStack
	docker-compose down -v
	rm -rf localstack-data
