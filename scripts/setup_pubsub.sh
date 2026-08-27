#!/usr/bin/env bash
set -e

PROJECT_ID=${GCP_PROJECT:-"massive-house-506806-t6"}

echo "Initializing Pub/Sub topics and subscriptions for project: ${PROJECT_ID}"

TOPICS=(
  "buyer-to-escrow"
  "vendor-to-escrow"
  "escrow-to-buyer"
  "escrow-to-vendor"
)

SUBS=(
  "buyer-to-escrow-sub:buyer-to-escrow"
  "vendor-to-escrow-sub:vendor-to-escrow"
  "escrow-to-buyer-sub:escrow-to-buyer"
  "escrow-to-vendor-sub:escrow-to-vendor"
)

for topic in "${TOPICS[@]}"; do
  echo "Creating topic: ${topic}"
  gcloud pubsub topics create "${topic}" --project="${PROJECT_ID}" || true
done

for sub_pair in "${SUBS[@]}"; do
  IFS=":" read -r sub_name topic_name <<< "${sub_pair}"
  echo "Creating subscription: ${sub_name} for topic: ${topic_name}"
  gcloud pubsub subscriptions create "${sub_name}" \
    --topic="${topic_name}" \
    --project="${PROJECT_ID}" || true
done

echo "Pub/Sub infrastructure setup complete."
