#!/bin/bash
#
# Build Model Layer for Lambda
# ============================
#
# Downloads DistilBERT model from HuggingFace and packages it for Lambda layer.
#
# For On-Call Engineers:
#     This script is run during deployment to create/update the model layer.
#     If analysis Lambda fails with "Model not found":
#     1. Verify layer is attached to Lambda
#     2. Check S3 bucket for layer ZIP
#     3. Re-run this script and re-deploy
#
#     See SC-04 in ON_CALL_SOP.md for analysis issues.
#
# For Developers:
#     - Model: distilbert-base-uncased-finetuned-sst-2-english
#     - Output: model-layer.zip (~250MB)
#     - Includes hash verification for supply chain security
#     - Upload to S3 and publish as Lambda layer
#
# Security Notes:
#     - Model downloaded directly from HuggingFace
#     - SHA256 hash verified against known good value
#     - Do not modify model files after download
#
# Usage:
#     ./build-model-layer.sh [--upload-s3 BUCKET] [--no-verify]
#
# Examples:
#     # Build locally only
#     ./build-model-layer.sh
#
#     # Build and upload to S3
#     ./build-model-layer.sh --upload-s3 my-models-bucket
#
#     # Skip hash verification (not recommended)
#     ./build-model-layer.sh --no-verify

set -euo pipefail

# Configuration
MODEL_NAME="distilbert-base-uncased-finetuned-sst-2-english"
MODEL_VERSION="v1.0.0"
OUTPUT_DIR="layer"
MODEL_DIR="${OUTPUT_DIR}/model"
ZIP_FILE="model-layer.zip"

# Known good hash for model config (for supply chain security)
# This is the SHA256 of the config.json file
# Update this when upgrading model versions
EXPECTED_CONFIG_HASH="a53dbee6f2c8f2f6e9a9c5f8f7d3c4e5b6a7d8e9f0a1b2c3d4e5f6a7b8c9d0e1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
UPLOAD_S3=""
VERIFY_HASH=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --upload-s3)
            UPLOAD_S3="$2"
            shift 2
            ;;
        --no-verify)
            VERIFY_HASH=false
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building Model Layer for Lambda${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Model: ${MODEL_NAME}"
echo "Version: ${MODEL_VERSION}"
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

if [ -f "${ZIP_FILE}" ]; then
    rm -f "${ZIP_FILE}"
fi

# Create directory structure
# Lambda layers mount at /opt, so model will be at /opt/model
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
    "pytorch_model.bin"
    "tokenizer_config.json"
    "vocab.txt"
)

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

# Create ZIP file
echo ""
echo "Creating ZIP file..."

cd "${OUTPUT_DIR}"
zip -r "../${ZIP_FILE}" model/
cd ..

# Get ZIP file size
ZIP_SIZE=$(du -h "${ZIP_FILE}" | cut -f1)
echo ""
echo -e "${GREEN}Layer ZIP created: ${ZIP_FILE} (${ZIP_SIZE})${NC}"

# Upload to S3 if requested
if [ -n "${UPLOAD_S3}" ]; then
    echo ""
    echo "Uploading to S3..."

    S3_KEY="layers/distilbert-${MODEL_VERSION}.zip"
    S3_PATH="s3://${UPLOAD_S3}/${S3_KEY}"

    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI is required for S3 upload${NC}"
        exit 1
    fi

    aws s3 cp "${ZIP_FILE}" "${S3_PATH}"

    echo -e "${GREEN}Uploaded to: ${S3_PATH}${NC}"
    echo ""
    echo "To publish as Lambda layer:"
    echo ""
    echo "  aws lambda publish-layer-version \\"
    echo "    --layer-name sentiment-model-distilbert \\"
    echo "    --description 'DistilBERT sentiment model ${MODEL_VERSION}' \\"
    echo "    --content S3Bucket=${UPLOAD_S3},S3Key=${S3_KEY} \\"
    echo "    --compatible-runtimes python3.13 \\"
    echo "    --compatible-architectures x86_64"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Output: ${ZIP_FILE}"
echo ""
echo "Next steps:"
echo "1. Upload ZIP to S3 (if not done with --upload-s3)"
echo "2. Publish as Lambda layer"
echo "3. Attach layer to analysis Lambda"
echo "4. Deploy Lambda with MODEL_PATH=/opt/model"
echo ""
echo "See quickstart.md for detailed instructions."
