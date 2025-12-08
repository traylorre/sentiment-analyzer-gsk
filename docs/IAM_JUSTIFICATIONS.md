# IAM Policy Justifications

This document provides canonical source citations for IAM policy patterns that trigger validator warnings but are justified for this project.

## IAM-002: CloudFront Cache Policy Operations

**Finding**: `Resource: "*"` in CloudFront cache policy statement

**Justification**: CloudFront List operations require `Resource: "*"` per AWS Service Authorization Reference.

| Action | Resource Types | Requirement |
|--------|----------------|-------------|
| `cloudfront:GetCachePolicy` | `cache-policy*` | Resource-level supported |
| `cloudfront:GetOriginRequestPolicy` | `origin-request-policy*` | Resource-level supported |
| `cloudfront:ListCachePolicies` | **None** | **Requires `*`** |
| `cloudfront:ListOriginRequestPolicies` | **None** | **Requires `*`** |

**Canonical Source**: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncloudfront.html

**Verification**: The "Resource types" column for List operations is empty, indicating resource-level permissions are not supported. The wildcard is an AWS API limitation, not a policy design flaw.

**Affected Files**:
- `infrastructure/iam-policies/preprod-deployer-policy.json` (CloudFrontCachePolicies statement)
- `infrastructure/iam-policies/prod-deployer-policy.json` (if applicable)

**Note**: The IAMValidator in the template methodology does not currently support allowlist suppressions for IAM-002. This finding is expected and documented here as the canonical justification.

---

## LAMBDA-007: CreateFunction + PassRole

**Finding**: `lambda:CreateFunction` combined with `iam:PassRole` enables privilege escalation

**Justification**: CI/CD pipelines legitimately require these permissions for automated Lambda deployments. The risk is mitigated by scoping PassRole to specific role ARN patterns.

**PassRole Scope** (all environments):
- `arn:aws:iam::*:role/{env}-*` (environment-prefixed roles only)

**Canonical Source**: https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-cicd-litmus/cicd-best-practices.html

**Suppression**: Suppressed via `iam-allowlist.yaml` entry `lambda-cicd-deployment`

---

## LAMBDA-011: CreateEventSourceMapping + PassRole

**Finding**: `lambda:CreateEventSourceMapping` combined with `iam:PassRole` enables privilege escalation

**Justification**: Event-driven architectures require these permissions for connecting Lambda functions to SQS/DynamoDB/Kinesis triggers.

**PassRole Scope**: Same as LAMBDA-007

**Canonical Source**: https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html

**Suppression**: Suppressed via `iam-allowlist.yaml` entry `lambda-event-source-mapping`

---

## SQS-009: DeleteQueue Permission

**Finding**: `sqs:DeleteQueue` enables queue deletion

**Justification**: Dev and preprod CI deployers require this for terraform destroy operations during infrastructure testing. Prod CI deployer does NOT have this permission - prod destroy requires break-glass access.

**Scope**:
- Dev/preprod deployer policies: Allowed
- Prod deployer policy: Not allowed
- CI user policy: Scoped to `*-sentiment-*` queue patterns

**Canonical Source**: https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html

**Suppression**: Suppressed via `iam-allowlist.yaml` entries `dev-preprod-sqs-delete` and `ci-user-sqs-delete`

---

## References

- [AWS Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/)
- [AWS CI/CD Best Practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-cicd-litmus/cicd-best-practices.html)
- [OWASP CI/CD Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html)
- [terraform-gsk-template Constitution Amendment 1.5](https://github.com/traylorre/terraform-gsk-template/blob/main/.specify/memory/constitution.md#amendment-15---canonical-source-verification-2025-12-03)
