#!/bin/bash
# Pin the Gemini CLI to Vertex AI auth (no API key, no browser login).
#
# Google discontinued the Gemini CLI's free "Sign in with Google" (Code Assist
# for individuals) tier, so Gemini is driven through Vertex AI on a GCP project
# instead. One-time prerequisites, done with Windows gcloud (owner of the project):
#
#   PROJECT=agentready-0615152320
#   gcloud iam service-accounts create vista-vertex --project=$PROJECT
#   gcloud projects add-iam-policy-binding $PROJECT \
#       --member="serviceAccount:vista-vertex@$PROJECT.iam.gserviceaccount.com" \
#       --role="roles/aiplatform.user"
#   gcloud iam service-accounts keys create "$USERPROFILE/.vista/vertex-sa.json" \
#       --iam-account="vista-vertex@$PROJECT.iam.gserviceaccount.com"
#   # ^ the key lives OUTSIDE the repo so it can never be committed.
#
# This script just pins the CLI's selected auth type to Vertex. Runs then export
# GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION /
# GOOGLE_APPLICATION_CREDENTIALS (the runner does this for you).
set -e
mkdir -p ~/.gemini
cat > ~/.gemini/settings.json <<'JSON'
{
  "security": {
    "auth": {
      "selectedType": "vertex-ai"
    }
  }
}
JSON
echo "Gemini CLI auth pinned to vertex-ai:"
cat ~/.gemini/settings.json
