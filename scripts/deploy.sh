#!/usr/bin/env bash
set -e

PROJECT_ID=${GCP_PROJECT:-"massive-house-506806-t6"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="agent-trust-ledger"

echo "Deploying ${SERVICE_NAME} to Google Cloud Run..."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT="${PROJECT_ID}",GCP_REGION="${REGION}",GEMINI_MODEL="gemini-3.5-flash" \
  --project="${PROJECT_ID}"

echo "Deployment complete! Cloud Run URL:"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format 'value(status.url)'
