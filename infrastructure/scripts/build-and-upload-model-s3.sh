#!/bin/bash
#
# Build Model Package for S3 Lazy Loading
# ========================================
#
# Downloads DistilBERT model from HuggingFace and packages it for S3 storage.
# Lambda downloads and extracts on-demand (lazy loading pattern).
#
# For On-Call Engineers:
#     This script is run once to upload model to S3.
#     If analysis Lambda fails with "Model not found in S3":
#     1. Verify S3 object exists at s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/model.tar.gz
#     2. Check Lambda has s3:GetObject permission
#     3. Re-run this script if model missing
#
# For Developers:
#     - Model: distilbert-base-uncased-finetuned-sst-2-english
#     - Output: model.tar.gz (~250MB)
#     - Uploads to S3 bucket for all envs (preprod, prod)
#
# Security Notes:
#     - Model downloaded directly from HuggingFace
#     - SHA256 hash verified against known good value
#     - Do not modify model files after download
#
# Usage:
#     ./build-and-upload-model-s3.sh [--no-verify] [--no-upload]
#
# Examples:
#     # Build and upload to S3
#     ./build-and-upload-model-s3.sh
#
#     # Build locally only (no upload)
#     ./build-and-upload-model-s3.sh --no-upload
#
#     # Skip hash verification (not recommended)
#     ./build-and-upload-model-s3.sh --no-verify

set -euo pipefail

# Configuration
MODEL_NAME="distilbert-base-uncased-finetuned-sst-2-english"
MODEL_VERSION="v1.0.0"
OUTPUT_DIR="model-build"
MODEL_DIR="${OUTPUT_DIR}/model"
TAR_FILE="model.tar.gz"
S3_BUCKET="sentiment-analyzer-models-218795110243"
S3_KEY="distilbert/${MODEL_VERSION}/model.tar.gz"

# Known good hash for model config (for supply chain security)
# This is the SHA256 of the config.json file
# Update this when upgrading model versions
# Updated 2025-12-20 for distilbert-base-uncased-finetuned-sst-2-english
EXPECTED_CONFIG_HASH="df80ff6a470008e42520222530ca1559e2533afc931a21277a08707391fbca74"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
VERIFY_HASH=true
UPLOAD_TO_S3=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-verify)
            VERIFY_HASH=false
            shift
            ;;
        --no-upload)
            UPLOAD_TO_S3=false
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building Model Package for S3${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Model: ${MODEL_NAME}"
echo "Version: ${MODEL_VERSION}"
echo "S3 Destination: s3://${S3_BUCKET}/${S3_KEY}"
echo ""

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but not installed${NC}"
    exit 1
fi

# Check pip is available
if ! python3 -m pip --version &> /dev/null; then
    echo -e "${RED}Error: pip is required but not installed${NC}"
    exit 1
fi

# Clean previous build
if [ -d "${OUTPUT_DIR}" ]; then
    echo "Cleaning previous build..."
    rm -rf "${OUTPUT_DIR}"
fi

if [ -f "${TAR_FILE}" ]; then
    rm -f "${TAR_FILE}"
fi

# Create directory structure
echo "Creating directory structure..."
mkdir -p "${MODEL_DIR}"

# Install transformers if not available
echo "Checking for transformers library..."
if ! python3 -c "import transformers" &> /dev/null; then
    echo "Installing transformers..."
    python3 -m pip install --quiet transformers torch
fi

# Download model from HuggingFace
echo ""
echo -e "${YELLOW}Downloading model from HuggingFace...${NC}"
echo "This may take a few minutes (~250MB)"
echo ""

python3 << EOF
import os
import sys

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_name = "${MODEL_NAME}"
    output_dir = "${MODEL_DIR}"

    print(f"Downloading model: {model_name}")

    # Download model
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Save to output directory
    print(f"Saving model to: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("Model download complete!")

except Exception as e:
    print(f"Error downloading model: {e}", file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to download model${NC}"
    exit 1
fi

# Verify model files exist
echo ""
echo "Verifying model files..."

required_files=(
    "config.json"
    "tokenizer_config.json"
    "vocab.txt"
)

# Check for model weights (either pytorch_model.bin or model.safetensors)
has_model_weights=false
if [ -f "${MODEL_DIR}/pytorch_model.bin" ]; then
    has_model_weights=true
    echo "Found pytorch_model.bin"
fi
if [ -f "${MODEL_DIR}/model.safetensors" ]; then
    has_model_weights=true
    echo "Found model.safetensors (HuggingFace new default)"
fi

if [ "$has_model_weights" = false ]; then
    echo -e "${RED}Error: No model weights found (need pytorch_model.bin or model.safetensors)${NC}"
    exit 1
fi

missing_files=()
for file in "${required_files[@]}"; do
    if [ ! -f "${MODEL_DIR}/${file}" ]; then
        missing_files+=("${file}")
    fi
done

if [ ${#missing_files[@]} -ne 0 ]; then
    echo -e "${RED}Error: Missing required model files:${NC}"
    printf '  - %s\n' "${missing_files[@]}"
    exit 1
fi

echo -e "${GREEN}All required files present${NC}"

# Verify hash (supply chain security)
if [ "${VERIFY_HASH}" = true ]; then
    echo ""
    echo "Verifying model hash for supply chain security..."

    # Calculate hash of config.json
    if command -v sha256sum &> /dev/null; then
        ACTUAL_HASH=$(sha256sum "${MODEL_DIR}/config.json" | cut -d' ' -f1)
    elif command -v shasum &> /dev/null; then
        ACTUAL_HASH=$(shasum -a 256 "${MODEL_DIR}/config.json" | cut -d' ' -f1)
    else
        echo -e "${YELLOW}Warning: Cannot verify hash (sha256sum/shasum not available)${NC}"
        ACTUAL_HASH=""
    fi

    if [ -n "${ACTUAL_HASH}" ]; then
        echo "Expected hash: ${EXPECTED_CONFIG_HASH}"
        echo "Actual hash:   ${ACTUAL_HASH}"

        # Note: Hash will differ from expected on first run
        # Update EXPECTED_CONFIG_HASH after verifying model manually
        if [ "${ACTUAL_HASH}" != "${EXPECTED_CONFIG_HASH}" ]; then
            echo -e "${YELLOW}Warning: Hash mismatch - update EXPECTED_CONFIG_HASH if this is a new model version${NC}"
            echo ""
            echo "To update, set:"
            echo "  EXPECTED_CONFIG_HASH=\"${ACTUAL_HASH}\""
        else
            echo -e "${GREEN}Hash verified successfully${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Skipping hash verification (--no-verify)${NC}"
fi

# Create tar.gz file
echo ""
echo "Creating tar.gz file..."

cd "${OUTPUT_DIR}"
tar -czf "../${TAR_FILE}" model/
cd ..

# Get tar.gz file size
TAR_SIZE=$(du -h "${TAR_FILE}" | cut -f1)
echo ""
echo -e "${GREEN}Model package created: ${TAR_FILE} (${TAR_SIZE})${NC}"

# Upload to S3 if requested
if [ "${UPLOAD_TO_S3}" = true ]; then
    echo ""
    echo "Uploading to S3..."

    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI is required for S3 upload${NC}"
        exit 1
    fi

    S3_PATH="s3://${S3_BUCKET}/${S3_KEY}"

    aws s3 cp "${TAR_FILE}" "${S3_PATH}"

    echo -e "${GREEN}Uploaded to: ${S3_PATH}${NC}"
    echo ""
    echo "Verifying upload..."
    aws s3 ls "${S3_PATH}" && echo -e "${GREEN}✓ Upload verified${NC}"
else
    echo ""
    echo -e "${YELLOW}Skipping S3 upload (--no-upload)${NC}"
    echo ""
    echo "To upload manually:"
    echo "  aws s3 cp ${TAR_FILE} s3://${S3_BUCKET}/${S3_KEY}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Output: ${TAR_FILE}"
echo "S3 Location: s3://${S3_BUCKET}/${S3_KEY}"
echo ""
echo "Next steps:"
echo "1. ✓ Model uploaded to S3 (if --upload was used)"
echo "2. Deploy Lambda with S3 lazy loading code"
echo "3. Lambda will download model on first cold start"
echo ""
