# Contributing to sentiment-analyzer-gsk

Thank you for your interest in contributing! This document outlines the collaboration model, security requirements, and development workflow.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Security Model](#security-model)
  - [Zero-Trust Principles](#zero-trust-principles)
  - [Role Separation: Admin vs Contributor](#role-separation-admin-vs-contributor)
  - [What Contributors CAN Do](#what-contributors-can-do)
  - [What Contributors CANNOT Do](#what-contributors-cannot-do)
- [Getting Started](#getting-started)
- [Pull Request Process](#pull-request-process)
- [AWS Access & Credentials](#aws-access--credentials)
- [Secrets Management](#secrets-management)
- [Audit Trail Requirements](#audit-trail-requirements)
- [Incident Response](#incident-response)
- [Questions](#questions)

---

## Code of Conduct

### Our Standards

- **Professional conduct**: Treat all contributors with respect
- **Constructive feedback**: Focus on improving code, not attacking people
- **Transparency**: Communicate openly about blockers and concerns
- **Security-first**: Report vulnerabilities responsibly (see [SECURITY.md](./SECURITY.md))

### Unacceptable Behavior

- Attempting to bypass security controls
- Accessing systems/data beyond authorized scope
- Sharing credentials or access tokens
- Creating backdoors or obfuscated code
- Harassment or discriminatory behavior

**Violations will result in immediate removal from the project.**

---

## Security Model

### Zero-Trust Principles

⚠️ **CRITICAL ASSUMPTION: All contributors are treated as potential bad-faith actors.**

This is not personal - it's defense-in-depth security. The project implements:

1. **Least privilege**: Contributors get minimum necessary access
2. **Separation of duties**: No single person (except @traylorre) can deploy to production
3. **Audit everything**: All actions are logged and monitored
4. **Assume breach**: System designed to limit damage from compromised accounts
5. **Mandatory review**: All code changes require explicit approval

---

### Role Separation: Admin vs Contributor

There are **two roles** in this project:

#### Admin Role (Project Owner: @traylorre)

**Responsibilities:**
- Approve all pull requests (MANDATORY)
- Deploy infrastructure changes via Terraform Cloud
- Manage AWS IAM roles and policies
- Rotate credentials and API keys
- Access AWS Secrets Manager
- Modify CloudWatch alarms and dashboards
- Grant/revoke contributor access
- Respond to security incidents

**Access:**
- Full AWS account access (production)
- Terraform Cloud admin
- GitHub repository admin
- All monitoring and logs

#### Contributor Role (All Other Collaborators)

**Responsibilities:**
- Develop features, fix bugs, improve documentation
- Create pull requests for review
- Participate in code reviews (non-binding)
- Test changes locally
- Report bugs and security issues

**Access:**
- GitHub repository: read + create PRs (NO merge permissions)
- AWS: Read-only CloudWatch metrics (filtered)
- Terraform Cloud: Read-only workspace status
- No access to: Secrets Manager, IAM, production deployments

---

### What Contributors CAN Do

✅ **GitHub:**
- Clone repository
- Create feature branches
- Push to feature branches
- Create pull requests
- Comment on PRs and issues
- View CI/CD workflow results

✅ **AWS (Read-Only):**
- List Lambda functions (names only)
- View CloudWatch dashboards (non-sensitive metrics only)
- Read Lambda logs (sanitized - no secrets)
- View DynamoDB table schemas (not data)
- Check EventBridge rule status
- View alarm states (OK/ALARM/INSUFFICIENT_DATA)

✅ **Terraform Cloud (Read-Only):**
- View workspace status
- See plan/apply run history
- Read non-sensitive variables

✅ **Local Development:**
- Run tests locally
- Lint code
- Build Lambda packages
- Use LocalStack for local testing

---

### What Contributors CANNOT Do

❌ **GitHub:**
- Merge pull requests (requires @traylorre approval)
- Modify branch protection rules
- Change repository settings
- Delete branches
- Force push to main
- Bypass CODEOWNERS requirements

❌ **AWS:**
- Deploy infrastructure changes
- Access AWS Secrets Manager
- Modify IAM roles/policies
- Create/modify CloudWatch alarms
- Access DynamoDB table data
- View sensitive metrics:
  - DDoS attack patterns
  - Quota exhaustion rates
  - Detailed failure analysis
  - Cost breakdown by source
  - Twitter API usage details

❌ **Terraform Cloud:**
- Queue plan/apply runs
- Modify workspaces
- Change variables
- Access state files
- Approve runs

❌ **Credentials:**
- Generate API keys
- Rotate secrets
- Access OAuth tokens
- View Twitter API credentials
- Obtain admin AWS credentials

---

## Getting Started

### 1. Request Access

Contact @traylorre with:
- Your GitHub username
- Brief introduction (background, what you want to contribute)
- Acknowledgment that you've read this document

**Response time:** 24-48 hours

### 2. Receive Credentials

@traylorre will provide:
- ✅ GitHub repository contributor access
- ✅ AWS IAM credentials (Contributor role - read-only)
- ✅ Terraform Cloud observer access
- ❌ NO production admin access
- ❌ NO Secrets Manager access

**Store credentials securely:**
```bash
# Use AWS profiles (NEVER commit credentials)
aws configure --profile sentiment-analyzer-contributor

# Verify access
aws sts get-caller-identity --profile sentiment-analyzer-contributor
# Should show: arn:aws:iam::ACCOUNT:user/contributor-YOUR-NAME
```

### 3. Complete Onboarding

Follow [README.md Getting Started](./README.md#getting-started) section:
1. Install prerequisites
2. Clone repository
3. Configure AWS profile
4. Verify access
5. Read SPEC.md

---

## Pull Request Process

### Branch Strategy

**Protected branches:**
- `main` - Production-ready code (requires PR + approval)
- `develop` - (Future) Integration branch

**Feature branches:**
```bash
# Always branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# Naming conventions:
# - feature/add-twitter-ingestion
# - fix/scheduler-timeout-bug
# - docs/update-contributing-guide
# - refactor/lambda-error-handling
# - test/add-rss-parser-tests
```

### Creating a Pull Request

**1. Ensure your branch is up-to-date:**
```bash
git checkout main
git pull origin main
git checkout feature/your-feature-name
git rebase main  # Or merge main into your branch
```

**2. Run pre-submission checks:**
```bash
# Lint (when linter configured)
# terraform fmt -check
# python -m black --check src/
# python -m pylint src/

# Run tests (when test suite exists)
# pytest tests/

# Check for secrets (CRITICAL)
# git secrets --scan  # Or use gitleaks
```

**3. Write clear commit messages:**
```
<type>: <summary in 50 chars or less>

<Detailed explanation of changes in 72-char lines>

- Bullet points for key changes
- Reference related issues: #123, #456

Addresses: #<issue-number>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `security`

**4. Push and create PR:**
```bash
git push origin feature/your-feature-name

# GitHub will show PR creation link
# Or navigate to: https://github.com/traylorre/sentiment-analyzer-gsk/pulls
```

**5. PR template (auto-populated):**
```markdown
## Description
[What does this PR do?]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Security fix

## Testing
[How was this tested?]

## Checklist
- [ ] Code follows project style guidelines
- [ ] No secrets or credentials committed
- [ ] Tests pass locally
- [ ] Documentation updated (if needed)
- [ ] SPEC.md updated (if API/architecture changed)
```

### Review Process

⚠️ **MANDATORY REVIEW BY @traylorre**

**Automated Checks (GitHub Actions):**
1. Terraform format validation (`terraform fmt`)
2. Terraform validation (`terraform validate`)
3. Security scanning (tfsec, checkov)
4. Secret scanning (gitleaks)
5. Linting (when configured)
6. Unit tests (when configured)
7. CODEOWNERS enforcement

**All checks must pass before review.**

**Manual Review:**
- @traylorre is automatically assigned (via CODEOWNERS)
- Review focuses on:
  - Security implications
  - Architecture alignment with SPEC.md
  - Code quality and maintainability
  - Test coverage
  - Documentation completeness

**Approval Required:**
- ✅ @traylorre MUST approve before merge
- ❌ Contributors CANNOT approve their own PRs
- ❌ Contributors CANNOT merge PRs (even if approved)
- ❌ NO bypassing review (branch protection enforced)

**Merge Process:**
1. All automated checks ✅
2. @traylorre approval ✅
3. **@traylorre merges** (contributors cannot merge)
4. Feature branch deleted automatically
5. Contributor pulls latest main

---

## AWS Access & Credentials

### Credential Lifecycle

**Issuance:**
1. @traylorre creates IAM user: `contributor-{username}`
2. Generates access key pair
3. Sends credentials via secure channel (NOT email/Slack)
4. Contributor acknowledges receipt

**Rotation:**
- **Automatic rotation**: Every 90 days
- **Manual rotation**: On contributor offboarding
- **Emergency rotation**: If credentials suspected compromised

**@traylorre will notify you 7 days before rotation.**

### Using AWS Credentials

**Setup profile:**
```bash
# Configure dedicated profile
aws configure --profile sentiment-analyzer-contributor
AWS Access Key ID: [PROVIDED_BY_ADMIN]
AWS Secret Access Key: [PROVIDED_BY_ADMIN]
Default region name: us-west-2
Default output format: json

# Always use --profile flag
aws lambda list-functions --profile sentiment-analyzer-contributor
```

**DO NOT:**
- ❌ Commit credentials to git
- ❌ Share credentials with others
- ❌ Use credentials outside this project
- ❌ Store in plaintext files
- ❌ Use default AWS profile for this project

**Credential Storage:**
```bash
# Credentials stored in:
~/.aws/credentials  # Ensure proper file permissions
chmod 600 ~/.aws/credentials
```

### IAM Policy (Contributor Role)

Contributors have **read-only** access to:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetDashboard",
        "cloudwatch:ListDashboards",
        "cloudwatch:GetMetricData",
        "dynamodb:DescribeTable",
        "dynamodb:ListTables",
        "events:DescribeRule",
        "events:ListRules"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Effect": "Deny",
      "Action": [
        "secretsmanager:*",
        "iam:*",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "lambda:InvokeFunction",
        "lambda:UpdateFunctionCode",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms"
      ],
      "Resource": "*"
    }
  ]
}
```

**Key restrictions:**
- ✅ Can describe/list resources
- ✅ Can read logs (CloudWatch filters out secrets)
- ❌ Cannot access Secrets Manager
- ❌ Cannot read DynamoDB data
- ❌ Cannot invoke Lambdas
- ❌ Cannot modify infrastructure

---

## Secrets Management

### What Are Secrets?

**Secrets include:**
- AWS access keys / secret access keys
- Twitter API keys / OAuth tokens
- API Gateway API keys
- Database credentials
- Encryption keys
- Terraform Cloud tokens
- Any authentication tokens

### Golden Rules

**NEVER commit secrets:**
```bash
# Check before committing
git diff --cached

# Scan for secrets
gitleaks detect --source . --verbose

# If you accidentally committed a secret:
1. Immediately notify @traylorre
2. DO NOT just delete from history (too late if pushed)
3. @traylorre will rotate the compromised credential
4. Incident will be logged
```

### How Secrets Are Managed

**AWS Secrets Manager (Admin Only):**
- All production secrets stored here
- Contributors have ZERO access
- Lambdas retrieve secrets at runtime
- Secrets automatically rotated

**Terraform Cloud (Admin Only):**
- Sensitive variables marked as "Sensitive"
- Contributors cannot view values
- State files encrypted at rest

**Local Development:**
```bash
# Use placeholder/dummy values
export TWITTER_API_KEY="dummy-key-for-local-testing"

# Or use LocalStack with fake credentials
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
```

**NEVER use production secrets locally.**

---

## Audit Trail Requirements

### What Gets Audited

**All actions are logged via:**
1. **AWS CloudTrail**: All API calls (who, what, when)
2. **GitHub Audit Log**: All repository actions
3. **Terraform Cloud Run History**: All infrastructure changes

**Monitored activities:**
- AWS API calls (CloudTrail)
- PR creation/merge (GitHub)
- File access patterns (GitHub)
- Failed authentication attempts (AWS, GitHub)
- Suspicious AWS queries (CloudWatch Insights)

### Contributor Obligations

**You MUST:**
- ✅ Use only provided credentials
- ✅ Report suspicious activity immediately
- ✅ Document rationale for unusual AWS queries
- ✅ Notify @traylorre before accessing production logs

**You MUST NOT:**
- ❌ Attempt to access unauthorized resources
- ❌ Share credentials
- ❌ Scrape or bulk download data
- ❌ Probe for security vulnerabilities (without permission)

### Audit Log Retention

- **CloudTrail**: 90 days in CloudWatch, 7 years in S3
- **GitHub Audit Log**: 90 days (organization level)
- **Terraform Cloud**: Indefinite run history

**Reviewable by:** @traylorre only (admin access required)

---

## Incident Response

### Suspected Credential Compromise

**If you suspect your AWS credentials are compromised:**

**Immediate actions (within 5 minutes):**
1. Contact @traylorre immediately
   - GitHub: `@traylorre` in issue/PR
   - Email: [Configure contact email]
   - Subject: "URGENT: Credential Compromise"

2. Provide details:
   - When did you notice?
   - What were you doing when you noticed?
   - Any suspicious AWS activity?
   - Where were credentials potentially exposed?

**@traylorre will:**
1. Immediately revoke credentials (< 5 min)
2. Review CloudTrail for unauthorized access
3. Rotate all related secrets if needed
4. Investigate scope of compromise
5. Issue new credentials if appropriate

### Security Vulnerability Discovery

**If you discover a security vulnerability:**

**DO:**
- ✅ Report privately to @traylorre (see [SECURITY.md](./SECURITY.md))
- ✅ Provide detailed reproduction steps
- ✅ Suggest mitigation if you have ideas
- ✅ Wait for acknowledgment before disclosure

**DO NOT:**
- ❌ Create public GitHub issues
- ❌ Exploit the vulnerability
- ❌ Disclose to third parties
- ❌ Tweet/blog about it

**Response time:**
- Acknowledgment: 48 hours
- Initial assessment: 72 hours
- Fix timeline: Depends on severity (P0: 1 week, P1: 2 weeks, P2: 1 month)

### Unauthorized Access Attempts

**If you accidentally access unauthorized resources:**

**Example:** You run `aws secretsmanager list-secrets` and it fails with "AccessDenied"

**Correct response:**
1. Stop immediately
2. Document what you tried
3. Notify @traylorre (not urgent, but within 24 hours)
4. Explain why you attempted it

**This is NOT a violation** - mistakes happen. We audit to detect patterns, not single incidents.

**Red flags that WILL trigger investigation:**
- Repeated unauthorized access attempts
- Trying to bypass IAM policies
- Scripting unauthorized API calls
- Not reporting accidental access

---

## Questions

### Getting Help

**For questions about:**
- **Technical design**: Comment on PR or create GitHub issue
- **AWS access problems**: Contact @traylorre directly
- **Contribution process**: Refer to this document or ask in PR
- **Security concerns**: See [SECURITY.md](./SECURITY.md)

### Common Questions

**Q: Why such strict security?**
A: Defense-in-depth. Even trusted contributors can have compromised accounts. Limiting blast radius protects everyone.

**Q: Can I get admin access after contributing for a while?**
A: No. This is a single-maintainer project. @traylorre is sole admin.

**Q: What if I need to test something that requires AWS write access?**
A: Use LocalStack or request @traylorre to run test in dev environment.

**Q: How do I know if I'm accessing something unauthorized?**
A: If AWS returns "AccessDenied", you don't have permission. That's expected for many operations.

**Q: What happens if I accidentally commit a secret?**
A: Notify @traylorre immediately. We'll rotate the secret. Not a disciplinary issue if accidental.

**Q: Can I contribute to Terraform code if I can't deploy it?**
A: Yes! Submit PRs with Terraform changes. @traylorre will review and deploy if approved.

---

## Summary

**To contribute successfully:**

1. ✅ Read and follow this document
2. ✅ Use only provided credentials
3. ✅ Never commit secrets
4. ✅ Create PRs for all changes
5. ✅ Wait for @traylorre approval
6. ✅ Report security issues privately
7. ✅ Ask questions when unsure

**Remember:**
- Zero-trust is protective, not punitive
- Auditing is for security, not surveillance
- Restrictions limit damage from compromised accounts
- Your contributions are valued!

**Thank you for contributing!** 🙏
