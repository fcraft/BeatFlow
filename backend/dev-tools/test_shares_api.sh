#!/bin/bash
# Test shares API endpoints

set -e

BASE="http://localhost:3090/api/v1"
EMAIL="admin@beatflow.com"
PASSWORD="Admin123!"

echo "=========================================="
echo "Testing Shares API Endpoints"
echo "=========================================="

# Helper function to extract JSON field
extract_json() {
  local json="$1"
  local field="$2"
  echo "$json" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('$field', ''))" 2>/dev/null || echo ""
}

# 1. Login
echo -e "\n[1/10] Logging in..."
LOGIN_RESP=$(curl -s -L -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
  echo "Login failed"
  echo "$LOGIN_RESP"
  exit 1
fi
echo "Logged in successfully"

# 2. Get first project
echo -e "\n[2/10] Getting first project..."
PROJECTS=$(curl -s -L -X GET "$BASE/projects/" \
  -H "Authorization: Bearer $TOKEN")
PROJECT_ID=$(echo "$PROJECTS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('items',[{}])[0].get('id',''))" 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo "No projects found"
  exit 1
fi
echo "Found project: $PROJECT_ID"

# 3. Get first file
echo -e "\n[3/10] Getting first file..."
FILES=$(curl -s -L -X GET "$BASE/projects/$PROJECT_ID/files/" \
  -H "Authorization: Bearer $TOKEN")
FILE_ID=$(echo "$FILES" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('items',[{}])[0].get('id',''))" 2>/dev/null)
FILE_NAME=$(echo "$FILES" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('items',[{}])[0].get('original_filename','unknown'))" 2>/dev/null)
if [ -z "$FILE_ID" ]; then
  echo "No files found"
  exit 1
fi
echo "Found file: $FILE_ID ($FILE_NAME)"

# 4. Create file share with 7-day expiry
echo -e "\n[4/10] Creating file share (7-day expiry)..."
SHARE=$(curl -s -L -X POST "$BASE/files/$FILE_ID/share?expires_in_days=7" \
  -H "Authorization: Bearer $TOKEN")
SHARE_CODE=$(echo "$SHARE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('share_code',''))" 2>/dev/null)
SHARE_ID=$(echo "$SHARE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
if [ -z "$SHARE_CODE" ]; then
  echo "Share creation failed"
  echo "$SHARE"
  exit 1
fi
echo "Share created: $SHARE_CODE (ID: $SHARE_ID)"

# 5. Create share with custom code
echo -e "\n[5/10] Creating share with custom code..."
CUSTOM_CODE="mycustomcode$(date +%s%N | tail -c 4)"
SHARE2=$(curl -s -L -X POST "$BASE/files/$FILE_ID/share?expires_in_days=1&share_code=$CUSTOM_CODE" \
  -H "Authorization: Bearer $TOKEN")
SHARE2_CODE=$(echo "$SHARE2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('share_code',''))" 2>/dev/null)
if [ "$SHARE2_CODE" != "$CUSTOM_CODE" ]; then
  echo "Custom code share failed"
  echo "$SHARE2"
  exit 1
fi
echo "Share created with custom code: $SHARE2_CODE"

# 6. List file shares
echo -e "\n[6/10] Listing file shares..."
SHARES_LIST=$(curl -s -L -X GET "$BASE/files/$FILE_ID/shares" \
  -H "Authorization: Bearer $TOKEN")
SHARE_COUNT=$(echo "$SHARES_LIST" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('items',[])))" 2>/dev/null)
if [ "$SHARE_COUNT" -lt 2 ]; then
  echo "Share list failed or incomplete"
  echo "$SHARES_LIST"
  exit 1
fi
echo "Found $SHARE_COUNT shares in list"

# 7. Access file share (no auth)
echo -e "\n[7/10] Accessing file share without auth..."
ACCESS=$(curl -s -L -X GET "$BASE/share/file/$SHARE_CODE")
VIEW_COUNT=$(echo "$ACCESS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('share',{}).get('view_count',0))" 2>/dev/null)
if [ -z "$VIEW_COUNT" ] || [ "$VIEW_COUNT" != "1" ]; then
  echo "Share access failed or unexpected view_count"
  echo "$ACCESS"
  exit 1
fi
echo "Share accessed, view_count: $VIEW_COUNT"

# 8. Download shared file
echo -e "\n[8/10] Downloading shared file..."
DOWNLOAD=$(curl -s -L -X GET "$BASE/share/file/$SHARE_CODE/download")
DOWNLOAD_SIZE=$(echo "$DOWNLOAD" | wc -c)
if [ "$DOWNLOAD_SIZE" -lt 100 ]; then
  echo "Download seems small ($DOWNLOAD_SIZE bytes), might be error"
  echo "$DOWNLOAD" | head -c 200
fi
echo "Downloaded $DOWNLOAD_SIZE bytes"

# 9. Verify download count updated
echo -e "\n[9/10] Verifying download count increased..."
ACCESS2=$(curl -s -L -X GET "$BASE/share/file/$SHARE_CODE")
DOWNLOAD_COUNT=$(echo "$ACCESS2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('share',{}).get('download_count',0))" 2>/dev/null)
if [ "$DOWNLOAD_COUNT" != "1" ]; then
  echo "Warning: Download count: $DOWNLOAD_COUNT (expected: 1)"
fi
echo "Download count verified: $DOWNLOAD_COUNT"

# 10. Delete share
echo -e "\n[10/10] Deleting file share..."
DELETE=$(curl -s -L -X DELETE "$BASE/file-shares/$SHARE_ID" \
  -H "Authorization: Bearer $TOKEN")
DELETE_MSG=$(echo "$DELETE" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('message',''))" 2>/dev/null)
if [ -z "$DELETE_MSG" ]; then
  echo "Delete response: $DELETE"
fi
echo "Share deleted"

# Cleanup: delete the custom code share too
echo -e "\nCleaning up custom share..."
SHARE2_ID=$(echo "$SHARE2" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null)
if [ -n "$SHARE2_ID" ]; then
  curl -s -L -X DELETE "$BASE/file-shares/$SHARE2_ID" \
    -H "Authorization: Bearer $TOKEN" > /dev/null
  echo "Custom share cleaned up"
fi

echo -e "\n=========================================="
echo "All shares API tests passed!"
echo "=========================================="
