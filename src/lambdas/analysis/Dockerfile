# Dockerfile for Analysis Lambda
# ==============================
# Packages DistilBERT sentiment model inside container for fast, predictable cold starts.
#
# Build: docker build -t analysis-lambda:latest .
# Test:  docker run -p 9000:8080 analysis-lambda:latest
# Invoke: curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
#         -d '{"Records":[{"Sns":{"Message":"{\"article_id\":\"test-123\"}"}}]}'

# Use AWS Lambda Python 3.13 base image
FROM public.ecr.aws/lambda/python:3.13

# Install system dependencies for building ML packages
RUN yum install -y gcc gcc-c++ make && yum clean all

# Copy requirements first for layer caching
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install production dependencies only
# No test dependencies (pytest, coverage, etc.) in production container
RUN pip install --no-cache-dir -r requirements.txt

# Download and cache DistilBERT model at build time
# Model will be baked into the container image (~250MB)
RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
    model = AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
    tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
    model.save_pretrained('${LAMBDA_TASK_ROOT}/model'); \
    tokenizer.save_pretrained('${LAMBDA_TASK_ROOT}/model')"

# Copy application code
COPY sentiment.py ${LAMBDA_TASK_ROOT}/
COPY handler.py ${LAMBDA_TASK_ROOT}/
COPY ../shared/ ${LAMBDA_TASK_ROOT}/shared/

# Set Lambda handler
CMD ["handler.lambda_handler"]
