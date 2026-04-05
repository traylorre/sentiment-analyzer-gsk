# Tasks: WAF SQL Injection Ruleset

**Feature**: 1312-waf-sqli-ruleset
**Created**: 2026-04-02

## Tasks

### Task 1: Fix header comment in WAF module
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **Lines**: 8-12
- **Action**: Update rule evaluation order comment. Remove SQLi from CommonRuleSet line. Add SQLi ruleset at Priority 2. Shift all subsequent priorities by +1.
- **Status**: [ ]

### Task 2: Fix Rule 1 inline comment
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **Line**: 68
- **Action**: Remove "SQL injection" from the comment. Change to "Includes XSS, size constraints, and known bad patterns."
- **Status**: [ ]

### Task 3: Add AWSManagedRulesSQLiRuleSet rule block
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **After**: Line 89 (end of CommonRuleSet rule block)
- **Action**: Insert new rule block with name `aws-managed-sqli-rules`, priority 2, `override_action { none {} }`, managed rule group `AWSManagedRulesSQLiRuleSet`, metric name `${var.environment}-waf-sqli-rules`.
- **Status**: [ ]
- **Depends on**: Task 1 (header comment should be accurate before code change)

### Task 4: Shift KnownBadInputs priority from 2 to 3
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **Line**: 97 (current `priority = 2`)
- **Action**: Change to `priority = 3`. Update section comment from "Rule 2" to "Rule 3".
- **Status**: [ ]
- **Depends on**: Task 3

### Task 5: Shift BotControl priority from 3 to 4
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **Line**: 125 (current `priority = 3`)
- **Action**: Change to `priority = 4`. Update section comment from "Rule 3" to "Rule 4".
- **Status**: [ ]
- **Depends on**: Task 4

### Task 6: Shift RateLimit priority from 4 to 5
- **File**: `infrastructure/terraform/modules/waf/main.tf`
- **Line**: 165 (current `priority = 4`)
- **Action**: Change to `priority = 5`. Update section comment from "Rule 4" to "Rule 5".
- **Status**: [ ]
- **Depends on**: Task 5
