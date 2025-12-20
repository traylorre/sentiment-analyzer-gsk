# Feature Specification: Fix Analysis Lambda S3 IAM Permissions

**Feature Branch**: `1006-analysis-s3-iam`
**Created**: 2025-12-20
**Status**: Draft
**Input**: User description: "Analysis Lambda has s3:GetObject but lacks s3:HeadObject permission for model bucket. boto3 download_file() requires both. Fix: infrastructure/terraform/modules/iam/main.tf lines 274-276. Add s3:HeadObject to analysis_s3_model policy."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sentiment Analysis Pipeline Completion (Priority: P1)

When a news article is received for sentiment analysis, the Analysis Lambda successfully downloads the ML model from S3 and processes the article, updating the sentiment classification in DynamoDB.

**Why this priority**: This is the core functionality that's currently broken. Without S3 model access, no sentiment analysis can occur, resulting in zero data on the dashboard.

**Independent Test**: Deploy the IAM fix and invoke the Analysis Lambda with a test SNS message. Verify the model downloads successfully and the article receives a sentiment classification.

**Acceptance Scenarios**:

1. **Given** an article message arrives via SNS, **When** the Analysis Lambda starts processing, **Then** the ML model downloads from S3 without 403 errors
2. **Given** the model downloads successfully, **When** sentiment analysis completes, **Then** the DynamoDB item is updated with a sentiment attribute (positive/neutral/negative)
3. **Given** the self-healing process republishes 100 pending items, **When** the Analysis Lambda processes them, **Then** all items receive sentiment classification within the processing window

---

### User Story 2 - Dashboard Data Visibility (Priority: P2)

After sentiment analysis completes, the dashboard displays updated metrics showing the count of positive, neutral, and negative articles.

**Why this priority**: This is the user-facing outcome that proves the pipeline works end-to-end. Dependent on P1 being resolved.

**Independent Test**: After P1 fix is deployed and items are analyzed, load the dashboard and verify non-zero counts appear for sentiment categories.

**Acceptance Scenarios**:

1. **Given** items have been analyzed with sentiment, **When** the dashboard loads, **Then** Total Items shows a non-zero count
2. **Given** items have mixed sentiments, **When** viewing the sentiment breakdown, **Then** Positive/Neutral/Negative counts reflect actual analyzed items

---

### Edge Cases

- What happens when the S3 bucket is temporarily unavailable? The Lambda fails with a retriable error, and SNS will redeliver the message.
- What happens when the model file is corrupted or missing? The Lambda logs a specific error and fails for that item.
- What happens when KMS encryption is added to the model bucket? Additional kms:Decrypt permission would be required - out of scope for this fix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Analysis Lambda IAM role MUST have `s3:HeadObject` permission on the model bucket
- **FR-002**: Analysis Lambda IAM role MUST have `s3:GetObject` permission on the model bucket (already exists)
- **FR-003**: Permissions MUST be scoped to the model bucket ARN with `/*` suffix for objects
- **FR-004**: The fix MUST be applied in Terraform to maintain infrastructure-as-code practices

### Key Entities

- **IAM Policy**: `analysis_s3_model` - grants S3 permissions for model access
- **S3 Bucket**: `sentiment-analyzer-models-{account_id}` - stores ML model files
- **Lambda Role**: `{environment}-analysis-lambda-role` - execution role for Analysis Lambda

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Analysis Lambda can download model files from S3 without 403 errors
- **SC-002**: Items republished by self-healing receive sentiment classification within 5 minutes
- **SC-003**: Dashboard displays non-zero values for Total Items and sentiment categories after fix deployment
- **SC-004**: No regression in existing S3 GetObject functionality

## Assumptions

- The S3 model bucket exists and contains the required model files
- The model bucket does not have a bucket policy that explicitly denies the Lambda role
- boto3's `download_file()` method is the only S3 operation requiring HeadObject (confirmed by error logs)
- No KMS encryption is currently applied to the model bucket (KMS permissions out of scope)

## Out of Scope

- Adding ListBucket permission (not required for download_file)
- Changing model storage location or format
- KMS encryption support for model bucket
- Model versioning or multi-model support
