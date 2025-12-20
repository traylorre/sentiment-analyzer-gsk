# Tasks: Feature 1007 - Upload DistilBERT Model

## Phase 1: Upload Model to S3 (Manual)

- [ ] T001 Run infrastructure/scripts/build-and-upload-model-s3.sh
- [ ] T002 Verify S3 object exists at distilbert/v1.0.0/model.tar.gz
- [ ] T003 Confirm object size is approximately 250 MB

## Phase 2: Increase Lambda Memory (Terraform)

### Goal: Update Analysis Lambda memory from 1024 MB to 2048 MB

- [ ] T004 Find Analysis Lambda memory configuration in Terraform
- [ ] T005 Update memory_size from 1024 to 2048
- [ ] T006 Run terraform fmt and validate
- [ ] T007 Create feature branch A-upload-distilbert-model
- [ ] T008 Commit with descriptive message
- [ ] T009 Push and create PR with auto-merge

## Phase 3: Verification

### Goal: Confirm end-to-end sentiment analysis works

- [ ] T010 Wait for PR merge and deployment
- [ ] T011 Verify Lambda memory is 2048 MB via AWS CLI
- [ ] T012 Invoke ingestion Lambda to trigger self-healing
- [ ] T013 Wait 60 seconds for Analysis Lambda to process
- [ ] T014 Check CloudWatch logs for "Model loaded successfully"
- [ ] T015 Query DynamoDB for items with sentiment attribute (Count > 0)
- [ ] T016 Check dashboard shows non-zero counts

## Definition of Done

- [ ] S3 contains distilbert/v1.0.0/model.tar.gz (~250 MB)
- [ ] Lambda memory is 2048 MB
- [ ] CloudWatch shows successful model loads
- [ ] DynamoDB items have sentiment attribute
- [ ] Dashboard shows positive/neutral/negative counts > 0
