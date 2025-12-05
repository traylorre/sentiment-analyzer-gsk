validation:
  command: validate
  repo: /home/traylorre/projects/sentiment-analyzer-gsk
  repo_type: target
  timestamp: '2025-12-05T18:18:33.198622+00:00'
  duration_ms: 0
  status: FAIL
summary:
  validators_run: 13
  validators_passed: 7
  validators_failed: 3
  total_findings: 9
  suppressed: 7
  critical: 0
  high: 3
  medium: 6
  low: 0
  info: 0
validators:
- name: security-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 67532
- name: iam-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 567
- name: s3-iam-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 576
- name: sns-iam-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 586
- name: sqs-iam-validate
  status: FAIL
  findings: 6
  critical: 0
  duration_ms: 632
- name: lambda-iam
  status: PASS
  findings: 5
  critical: 5
  duration_ms: 325
- name: cost-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 0
- name: canonical-validate
  status: FAIL
  findings: 1
  critical: 0
  duration_ms: 1400
- name: format-validate
  status: PASS
  findings: 0
  critical: 0
  duration_ms: 0
  skipped_checks:
  - check: test-existence
    reason: Template repo - methodology tests not subject to application test requirements
- name: spec-coherence
  status: WARN
  findings: 1
  critical: 0
  duration_ms: 2
- name: bidirectional
  status: WARN
  findings: 1
  critical: 0
  duration_ms: 2
- name: property
  status: FAIL
  findings: 1
  critical: 0
  duration_ms: 125
- name: mutation
  status: WARN
  findings: 1
  critical: 0
  duration_ms: 2
findings:
- validator: sqs-iam-validate
  id: SQS-009
  severity: HIGH
  status: SUPPRESSED
  rule: sqs-iam-least-privilege
  file: docs/iam-policies/dev-deployer-policy.json
  line: 115
  message: sqs:DeleteQueue detected - destructive action that permanently removes queues
  remediation: Restrict Resource to specific queue ARNs. sqs:DeleteQueue permanently removes queues.
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
  suppressed_by: dev-preprod-sqs-delete
- validator: sqs-iam-validate
  id: SQS-006
  severity: MEDIUM
  status: FAIL
  rule: sqs-iam-least-privilege
  file: docs/iam-policies/dev-deployer-policy.json
  line: 1
  message: SQS queue policy missing HTTPS enforcement (aws:SecureTransport)
  remediation: 'Add a Deny statement with condition: Bool: aws:SecureTransport: false. See: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html'
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
- validator: sqs-iam-validate
  id: SQS-009
  severity: HIGH
  status: FAIL
  rule: sqs-iam-least-privilege
  file: infrastructure/terraform/ci-user-policy.tf
  line: 177
  message: sqs:DeleteQueue detected - destructive action that permanently removes queues
  remediation: Restrict Resource to specific queue ARNs. sqs:DeleteQueue permanently removes queues.
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
- validator: sqs-iam-validate
  id: SQS-006
  severity: MEDIUM
  status: FAIL
  rule: sqs-iam-least-privilege
  file: infrastructure/iam-policies/prod-deployer-policy.json
  line: 1
  message: SQS queue policy missing HTTPS enforcement (aws:SecureTransport)
  remediation: 'Add a Deny statement with condition: Bool: aws:SecureTransport: false. See: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html'
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
- validator: sqs-iam-validate
  id: SQS-009
  severity: HIGH
  status: SUPPRESSED
  rule: sqs-iam-least-privilege
  file: infrastructure/iam-policies/preprod-deployer-policy.json
  line: 115
  message: sqs:DeleteQueue detected - destructive action that permanently removes queues
  remediation: Restrict Resource to specific queue ARNs. sqs:DeleteQueue permanently removes queues.
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
  suppressed_by: dev-preprod-sqs-delete
- validator: sqs-iam-validate
  id: SQS-006
  severity: MEDIUM
  status: FAIL
  rule: sqs-iam-least-privilege
  file: infrastructure/iam-policies/preprod-deployer-policy.json
  line: 1
  message: SQS queue policy missing HTTPS enforcement (aws:SecureTransport)
  remediation: 'Add a Deny statement with condition: Bool: aws:SecureTransport: false. See: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html'
  canonical_source: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html
- validator: lambda-iam
  id: LAMBDA-007
  severity: CRITICAL
  status: SUPPRESSED
  rule: lambda-privilege-escalation
  file: infrastructure/terraform/ci-user-policy.tf
  line: 48
  message: lambda:CreateFunction + iam:PassRole combination enables privilege escalation
  remediation: 'Remove lambda:CreateFunction or iam:PassRole. This combination allows creating functions with elevated permissions.
    See: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/'
  canonical_source: null
  suppressed_by: lambda-cicd-deployment
- validator: lambda-iam
  id: LAMBDA-011
  severity: CRITICAL
  status: SUPPRESSED
  rule: lambda-privilege-escalation
  file: infrastructure/terraform/ci-user-policy.tf
  line: 71
  message: lambda:CreateEventSourceMapping + iam:PassRole combination enables privilege escalation via event triggers
  remediation: 'Remove lambda:CreateEventSourceMapping or iam:PassRole. This combination allows triggering functions with
    elevated permissions without InvokeFunction. See: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/'
  canonical_source: null
  suppressed_by: lambda-event-source-mapping
- validator: lambda-iam
  id: LAMBDA-007
  severity: CRITICAL
  status: SUPPRESSED
  rule: lambda-privilege-escalation
  file: docs/iam-policies/dev-deployer-policy.json
  line: 37
  message: lambda:CreateFunction + iam:PassRole combination enables privilege escalation
  remediation: 'Remove lambda:CreateFunction or iam:PassRole. This combination allows creating functions with elevated permissions.
    See: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/'
  canonical_source: null
  suppressed_by: lambda-cicd-deployment
- validator: lambda-iam
  id: LAMBDA-007
  severity: CRITICAL
  status: SUPPRESSED
  rule: lambda-privilege-escalation
  file: infrastructure/iam-policies/prod-deployer-policy.json
  line: 35
  message: lambda:CreateFunction + iam:PassRole combination enables privilege escalation
  remediation: 'Remove lambda:CreateFunction or iam:PassRole. This combination allows creating functions with elevated permissions.
    See: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/'
  canonical_source: null
  suppressed_by: lambda-cicd-deployment
- validator: lambda-iam
  id: LAMBDA-007
  severity: CRITICAL
  status: SUPPRESSED
  rule: lambda-privilege-escalation
  file: infrastructure/iam-policies/preprod-deployer-policy.json
  line: 37
  message: lambda:CreateFunction + iam:PassRole combination enables privilege escalation
  remediation: 'Remove lambda:CreateFunction or iam:PassRole. This combination allows creating functions with elevated permissions.
    See: https://rhinosecuritylabs.com/aws/aws-privilege-escalation-methods-mitigation/'
  canonical_source: null
  suppressed_by: lambda-cicd-deployment
- validator: canonical-validate
  id: CAN-002
  severity: HIGH
  status: FAIL
  rule: canonical-source-section
  file: PR description
  line: null
  message: PR modifies 4 IAM file(s) but missing 'Canonical Sources Cited' section
  remediation: Add '## Canonical Sources Cited' section to PR description with AWS documentation links
  canonical_source: https://docs.aws.amazon.com/IAM/latest/UserGuide/
- validator: spec-coherence
  id: SPEC-001
  severity: MEDIUM
  status: FAIL
  rule: spec-coherence
  file: specs/
  line: null
  message: Spec coherence check produced warnings
  remediation: Review make test-spec output for details
  canonical_source: null
- validator: bidirectional
  id: BIDIR-001
  severity: MEDIUM
  status: FAIL
  rule: bidirectional-alignment
  file: .specify/verification/
  line: null
  message: Bidirectional verification produced warnings
  remediation: Review make test-bidirectional output for details
  canonical_source: null
- validator: property
  id: PROP-001
  severity: HIGH
  status: FAIL
  rule: property-invariant
  file: tests/property/
  line: null
  message: Property tests failed or found counterexamples
  remediation: Review make test-property output for counterexamples
  canonical_source: null
- validator: mutation
  id: MUT-001
  severity: MEDIUM
  status: FAIL
  rule: mutation-score
  file: tests/mutation/
  line: null
  message: Mutation testing found surviving mutants
  remediation: Review make test-mutation output for surviving mutants
  canonical_source: null
metadata:
  constitution_version: '1.5'
  validator_version: 0.1.0
