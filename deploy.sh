#!/usr/bin/env bash
#
# Deploy Receipt Ranger to AWS App Runner.
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - Docker installed and running
#
# Usage:
#   ./deploy.sh                   # Full deploy (build, push, create/update service)
#   ./deploy.sh --build-only      # Build and push Docker image only
#   ./deploy.sh --dry-run         # Show what would be done without executing
#
# Required environment variables (set in .env or export before running):
#   ECR_REGISTRY              - Full ECR registry URI
#                               e.g. 123456.dkr.ecr.us-east-2.amazonaws.com/ai-projects/receipt-ranger
#   SESSION_SECRET            - Fernet key for encrypting API key session cookies
#                               Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# Optional environment variables:
#   AWS_REGION                - AWS region (default: us-east-2)
#   AWS_ACCOUNT_ID            - Auto-detected if not set
#   APP_NAME                  - App name (default: receipt-ranger)
#   OWNER_OPENAI_API_KEY      - Owner's OpenAI API key (enables Google Sheets for owner sessions)
#   OWNER_ANTHROPIC_API_KEY   - Owner's Anthropic API key (optional)
#   ENABLE_GOOGLE_SHEETS      - true/false (default: true)
#   GOOGLE_SHEETS_CREDENTIALS - Base64-encoded service_account.json content
#                               Generate with: base64 -i service_account.json | tr -d '\n'

set -euo pipefail

# ---------- Configuration ----------
AWS_REGION="${AWS_REGION:-us-east-2}"
APP_NAME="${APP_NAME:-receipt-ranger}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
DRY_RUN=false
BUILD_ONLY=false

# Parse flags
for arg in "$@"; do
    case $arg in
        --dry-run)    DRY_RUN=true ;;
        --build-only) BUILD_ONLY=true ;;
        *)            echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ECR registry (required)
if [ -z "${ECR_REGISTRY:-}" ]; then
    echo "ERROR: ECR_REGISTRY is not set. Set it in .env or export it before running."
    echo "Example: ECR_REGISTRY=123456.dkr.ecr.us-east-2.amazonaws.com/ai-projects/receipt-ranger"
    exit 1
fi

# Derive the registry host (everything before the first /) and repo name (everything after)
ECR_HOST="${ECR_REGISTRY%%/*}"
ECR_REPO_NAME="${ECR_REGISTRY#*/}"

# Auto-detect AWS account ID
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

echo "=== Receipt Ranger Deployment ==="
echo "Region:       ${AWS_REGION}"
echo "Account:      ${AWS_ACCOUNT_ID}"
echo "ECR Registry: ${ECR_REGISTRY}"
echo "Image Tag:    ${IMAGE_TAG}"
echo "Dry Run:      ${DRY_RUN}"
echo ""

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] $*"
    else
        echo ">>> $*"
        "$@"
    fi
}

# ---------- Step 1: Create ECR repository (if it doesn't exist) ----------
echo "--- Step 1: ECR Repository ---"
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" > /dev/null 2>&1; then
    run_cmd aws ecr create-repository \
        --repository-name "${ECR_REPO_NAME}" \
        --region "${AWS_REGION}" \
        --image-scanning-configuration scanOnPush=true
else
    echo "ECR repository already exists."
fi

# ---------- Step 2: Build Docker image ----------
echo ""
echo "--- Step 2: Build Docker Image ---"
run_cmd docker build --no-cache --platform linux/amd64 -t "${APP_NAME}:${IMAGE_TAG}" .

# ---------- Step 3: Push to ECR ----------
echo ""
echo "--- Step 3: Push to ECR ---"
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] aws ecr get-login-password | docker login --password-stdin ${ECR_HOST}"
else
    echo ">>> Logging in to ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_HOST}"
fi
run_cmd docker tag "${APP_NAME}:${IMAGE_TAG}" "${ECR_REGISTRY}:${IMAGE_TAG}"
run_cmd docker push "${ECR_REGISTRY}:${IMAGE_TAG}"

if [ "$BUILD_ONLY" = true ]; then
    echo ""
    echo "=== Build complete. Image pushed to ${ECR_REGISTRY}:${IMAGE_TAG} ==="
    exit 0
fi

# ---------- Step 4: Create IAM role for App Runner (if it doesn't exist) ----------
echo ""
echo "--- Step 4: IAM Role ---"
ROLE_NAME="${APP_NAME}-apprunner-role"

if ! aws iam get-role --role-name "${ROLE_NAME}" > /dev/null 2>&1; then
    run_cmd aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "build.apprunner.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }'
    run_cmd aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
else
    echo "Access role already exists."
fi

ACCESS_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

# ---------- Step 5: Create or update App Runner service ----------
echo ""
echo "--- Step 5: App Runner Service ---"

if [ -z "${SESSION_SECRET:-}" ]; then
    echo "WARNING: SESSION_SECRET is not set. A random key will be generated (sessions won't survive restarts)."
    echo "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
fi

SERVICE_EXISTS=$(aws apprunner list-services \
    --region "${AWS_REGION}" \
    --query "ServiceSummaryList[?ServiceName=='${APP_NAME}'].ServiceArn" \
    --output text 2>/dev/null || echo "")

if [ -z "$SERVICE_EXISTS" ]; then
    echo "Creating new App Runner service..."
    run_cmd aws apprunner create-service \
        --service-name "${APP_NAME}" \
        --region "${AWS_REGION}" \
        --source-configuration "{
            \"AuthenticationConfiguration\": {
                \"AccessRoleArn\": \"${ACCESS_ROLE_ARN}\"
            },
            \"ImageRepository\": {
                \"ImageIdentifier\": \"${ECR_REGISTRY}:${IMAGE_TAG}\",
                \"ImageRepositoryType\": \"ECR\",
                \"ImageConfiguration\": {
                    \"Port\": \"8501\",
                    \"RuntimeEnvironmentVariables\": {
                        \"SESSION_SECRET\": \"${SESSION_SECRET:-}\",
                        \"OWNER_OPENAI_API_KEY\": \"${OWNER_OPENAI_API_KEY:-}\",
                        \"OWNER_ANTHROPIC_API_KEY\": \"${OWNER_ANTHROPIC_API_KEY:-}\",
                        \"ENABLE_GOOGLE_SHEETS\": \"${ENABLE_GOOGLE_SHEETS:-true}\",
                        \"GOOGLE_SHEETS_CREDENTIALS\": \"${GOOGLE_SHEETS_CREDENTIALS:-}\"
                    }
                }
            },
            \"AutoDeploymentsEnabled\": false
        }" \
        --instance-configuration "{
            \"Cpu\": \"1024\",
            \"Memory\": \"2048\"
        }" \
        --health-check-configuration "{
            \"Protocol\": \"HTTP\",
            \"Path\": \"/_stcore/health\",
            \"Interval\": 10,
            \"Timeout\": 5,
            \"HealthyThreshold\": 1,
            \"UnhealthyThreshold\": 5
        }"
else
    echo "Updating existing App Runner service..."
    SERVICE_ARN="${SERVICE_EXISTS}"
    run_cmd aws apprunner update-service \
        --service-arn "${SERVICE_ARN}" \
        --region "${AWS_REGION}" \
        --source-configuration "{
            \"AuthenticationConfiguration\": {
                \"AccessRoleArn\": \"${ACCESS_ROLE_ARN}\"
            },
            \"ImageRepository\": {
                \"ImageIdentifier\": \"${ECR_REGISTRY}:${IMAGE_TAG}\",
                \"ImageRepositoryType\": \"ECR\",
                \"ImageConfiguration\": {
                    \"Port\": \"8501\",
                    \"RuntimeEnvironmentVariables\": {
                        \"SESSION_SECRET\": \"${SESSION_SECRET:-}\",
                        \"OWNER_OPENAI_API_KEY\": \"${OWNER_OPENAI_API_KEY:-}\",
                        \"OWNER_ANTHROPIC_API_KEY\": \"${OWNER_ANTHROPIC_API_KEY:-}\",
                        \"ENABLE_GOOGLE_SHEETS\": \"${ENABLE_GOOGLE_SHEETS:-true}\",
                        \"GOOGLE_SHEETS_CREDENTIALS\": \"${GOOGLE_SHEETS_CREDENTIALS:-}\"
                    }
                }
            },
            \"AutoDeploymentsEnabled\": false
        }"
fi

echo ""
echo "=== Deployment initiated! ==="
echo ""
echo "Check service status with:"
echo "  aws apprunner list-services --region ${AWS_REGION} --query 'ServiceSummaryList[?ServiceName==\`${APP_NAME}\`]'"
echo ""
echo "Get service URL with:"
echo "  aws apprunner describe-service --service-arn \$(aws apprunner list-services --region ${AWS_REGION} --query 'ServiceSummaryList[?ServiceName==\`${APP_NAME}\`].ServiceArn' --output text) --region ${AWS_REGION} --query 'Service.ServiceUrl' --output text"
