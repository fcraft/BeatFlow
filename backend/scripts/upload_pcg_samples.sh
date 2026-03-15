#!/bin/bash
# Upload PCG sample WAV files to BeatFlow project

set -e

PROJECT_ID="4fbce5dc-662a-460d-9031-2e300741e32b"
BACKEND_URL="http://localhost:3090"
SAMPLES_DIR="/qqvip/proj/BeatFlow/backend/uploads/pcg-samples"

# For local development, we'll use curl with basic auth or token
# First, let's try to get a token via the login endpoint

# Try to get token (use demo credentials)
echo "Getting JWT token..."
TOKEN_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' 2>/dev/null || echo '{}')

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "Warning: Could not get JWT token. Trying without authentication..."
  # Proceed without token - might work for local dev
  TOKEN=""
else
  echo "Got token: ${TOKEN:0:20}..."
fi

# Upload function
upload_file() {
  local file_path=$1
  local file_name=$(basename "$file_path")
  local version_name=$(basename $(dirname "$file_path"))
  
  echo ""
  echo "Uploading: $version_name / $file_name"
  
  if [ -n "$TOKEN" ]; then
    curl -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@$file_path" \
      -F "metadata={\"version\":\"$version_name\"}" \
      "$BACKEND_URL/api/v1/projects/$PROJECT_ID/files/upload" \
      -w "\nStatus: %{http_code}\n" 2>&1 | tail -10
  else
    curl -X POST \
      -F "file=@$file_path" \
      -F "metadata={\"version\":\"$version_name\"}" \
      "$BACKEND_URL/api/v1/projects/$PROJECT_ID/files/upload" \
      -w "\nStatus: %{http_code}\n" 2>&1 | tail -10
  fi
}

# Main upload loop
echo "========================================"
echo "PCG Sample WAV Upload to BeatFlow"
echo "Project: $PROJECT_ID"
echo "========================================"

if [ ! -d "$SAMPLES_DIR" ]; then
  echo "Error: Samples directory not found: $SAMPLES_DIR"
  exit 1
fi

success=0
failed=0

# Upload all .wav files
for version_dir in "$SAMPLES_DIR"/*; do
  if [ -d "$version_dir" ]; then
    version_name=$(basename "$version_dir")
    echo ""
    echo "Processing version: $version_name"
    
    for wav_file in "$version_dir"/*.wav; do
      if [ -f "$wav_file" ]; then
        if upload_file "$wav_file"; then
          ((success++))
        else
          ((failed++))
        fi
      fi
    done
  fi
done

echo ""
echo "========================================"
echo "Upload Complete"
echo "Success: $success files"
echo "Failed: $failed files"
echo "========================================"
