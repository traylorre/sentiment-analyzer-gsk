# Rollback Deployment Procedure

Recovery procedure for failed deployment after legacy framework removal. Target: restore service within 15 minutes.

## Prerequisites
- AWS CLI configured with appropriate permissions
- Access to ECR repository and S3 deployment bucket
- Previous SHA-tagged images available in ECR

## Step 1: Identify Previous Versions

```bash
# List recent ECR images for each Lambda
aws ecr describe-images --repository-name <env>-sentiment-dashboard --query 'imageDetails[*].[imageTags,imageDigest]' --output table
aws ecr describe-images --repository-name <env>-sse-streaming --query 'imageDetails[*].[imageTags,imageDigest]' --output table
```

## Step 2: Rollback Container Lambdas

```bash
# Dashboard Lambda
aws lambda update-function-code \
  --function-name <env>-sentiment-dashboard \
  --image-uri <account>.dkr.ecr.<region>.amazonaws.com/<env>-sentiment-dashboard@sha256:<previous-hash>

# SSE Streaming Lambda
aws lambda update-function-code \
  --function-name <env>-sse-streaming \
  --image-uri <account>.dkr.ecr.<region>.amazonaws.com/<env>-sse-streaming@sha256:<previous-hash>
```

## Step 3: Rollback ZIP Lambdas

```bash
aws lambda update-function-code \
  --function-name <env>-<lambda-name> \
  --s3-bucket <deployment-bucket> \
  --s3-key <previous-version-key>
```

## Step 4: Rollback Terraform State (if needed)

```bash
terraform apply -target=module.<lambda> -var="image_tag=<previous-tag>"
```

## Step 5: Verify Recovery

For each Lambda:
1. Check health endpoint returns HTTP 200
2. Verify CloudWatch logs show successful invocations
3. Confirm no error spikes in CloudWatch metrics

## Recovery Time Objective
- Target: 15 minutes from detection to full recovery
- Container Lambdas: ~2 minutes each (image pull)
- ZIP Lambdas: ~30 seconds each
- Terraform apply: ~3 minutes
