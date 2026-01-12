#!/usr/bin/env bash
# colors.sh - Terminal color constants for bootstrap scripts
# Feature: 1194-workspace-bootstrap
#
# Usage: source scripts/lib/colors.sh

# Detect color support
if [[ -t 1 ]] && [[ -n "${TERM:-}" ]] && command -v tput &>/dev/null; then
    readonly COLOR_SUPPORT=true
else
    readonly COLOR_SUPPORT=false
fi

# Color codes (empty if no color support)
if [[ "${COLOR_SUPPORT}" == true ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly BLUE='\033[0;34m'
    readonly MAGENTA='\033[0;35m'
    readonly CYAN='\033[0;36m'
    readonly WHITE='\033[0;37m'
    readonly BOLD='\033[1m'
    readonly DIM='\033[2m'
    readonly NC='\033[0m'  # No Color / Reset
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly MAGENTA=''
    readonly CYAN=''
    readonly WHITE=''
    readonly BOLD=''
    readonly DIM=''
    readonly NC=''
fi

# Status indicators
readonly CHECK_MARK="${GREEN}✓${NC}"
readonly CROSS_MARK="${RED}✗${NC}"
readonly WARN_MARK="${YELLOW}!${NC}"
readonly INFO_MARK="${BLUE}i${NC}"
readonly ARROW="${CYAN}→${NC}"

# Print functions
# Usage: print_status "PASS" "Python version"
#        print_status "FAIL" "AWS credentials" "Run: aws configure"
print_status() {
    local status="$1"
    local message="$2"
    local remediation="${3:-}"

    case "${status}" in
        PASS|pass|OK|ok)
            echo -e "  ${CHECK_MARK} ${message}"
            ;;
        FAIL|fail|ERROR|error)
            echo -e "  ${CROSS_MARK} ${RED}${message}${NC}"
            if [[ -n "${remediation}" ]]; then
                echo -e "    ${ARROW} ${DIM}${remediation}${NC}"
            fi
            ;;
        WARN|warn|WARNING|warning)
            echo -e "  ${WARN_MARK} ${YELLOW}${message}${NC}"
            if [[ -n "${remediation}" ]]; then
                echo -e "    ${ARROW} ${DIM}${remediation}${NC}"
            fi
            ;;
        INFO|info)
            echo -e "  ${INFO_MARK} ${message}"
            ;;
        *)
            echo -e "  ${message}"
            ;;
    esac
}

# Section headers
# Usage: print_header "Prerequisites Check"
print_header() {
    local title="$1"
    echo ""
    echo -e "${BOLD}${BLUE}=== ${title} ===${NC}"
    echo ""
}

# Success/failure banners
# Usage: print_success "Bootstrap complete!"
print_success() {
    local message="$1"
    echo ""
    echo -e "${GREEN}${BOLD}✓ ${message}${NC}"
    echo ""
}

# Usage: print_error "Bootstrap failed"
print_error() {
    local message="$1"
    echo ""
    echo -e "${RED}${BOLD}✗ ${message}${NC}"
    echo ""
}

# Usage: print_warning "Cache expired"
print_warning() {
    local message="$1"
    echo ""
    echo -e "${YELLOW}${BOLD}! ${message}${NC}"
    echo ""
}
