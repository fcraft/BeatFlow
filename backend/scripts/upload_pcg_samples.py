#!/usr/bin/env python3
"""Upload PCG sample WAV files to BeatFlow project via REST API."""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/qqvip/proj/BeatFlow/backend')

from app.core.security import create_access_token
from app.core.config import settings

PROJECT_ID = "4fbce5dc-662a-460d-9031-2e300741e32b"
SAMPLES_DIR = Path("/qqvip/proj/BeatFlow/backend/uploads/pcg-samples")
BACKEND_URL = "http://localhost:3090"

def get_token():
    """Generate a JWT token for local development."""
    from app.schemas.user import UserLogin
    
    # Create a dev token for local testing
    # In real scenario, we'd login with credentials
    subject = {"sub": "dev-user", "user_id": "00000000-0000-0000-0000-000000000000"}
    token = create_access_token(subject, expires_delta=None)
    return token

async def upload_files():
    """Upload all PCG sample WAV files."""
    import aiohttp
    
    token = get_token()
    print(f"Generated token: {token[:40]}...")
    
    if not SAMPLES_DIR.exists():
        print(f"Error: Samples directory not found: {SAMPLES_DIR}")
        return False
    
    uploaded = 0
    failed = 0
    
    async with aiohttp.ClientSession() as session:
        for version_dir in sorted(SAMPLES_DIR.iterdir()):
            if not version_dir.is_dir():
                continue
            
            version_name = version_dir.name
            print(f"\nVersion: {version_name}")
            
            for wav_file in sorted(version_dir.glob("*.wav")):
                file_name = wav_file.name
                print(f"  Uploading: {file_name}...", end=" ", flush=True)
                
                try:
                    with open(wav_file, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename=str(wav_file.name))
                        data.add_field('metadata', json.dumps({"version": version_name}))
                        
                        headers = {"Authorization": f"Bearer {token}"}
                        
                        async with session.post(
                            f"{BACKEND_URL}/api/v1/projects/{PROJECT_ID}/files/upload",
                            data=data,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                result = await resp.json()
                                print(f"✓ ({result.get('id', 'unknown')[:8]}...)")
                                uploaded += 1
                            else:
                                error_text = await resp.text()
                                print(f"✗ (HTTP {resp.status})")
                                print(f"    Error: {error_text[:100]}")
                                failed += 1
                
                except Exception as e:
                    print(f"✗ (Exception: {str(e)[:50]})")
                    failed += 1
    
    print(f"\n{'='*50}")
    print(f"Upload Summary")
    print(f"  Success: {uploaded} files")
    print(f"  Failed:  {failed} files")
    print(f"  Project: {PROJECT_ID}")
    print(f"{'='*50}")
    
    return failed == 0

if __name__ == '__main__':
    # Check if backend is running
    import urllib.request
    try:
        urllib.request.urlopen(f"{BACKEND_URL}/api/v1/health", timeout=2)
        print("Backend is running ✓")
    except Exception as e:
        print(f"Error: Backend is not running at {BACKEND_URL}")
        print(f"Please start the backend with: cd /qqvip/proj/BeatFlow/backend && .venv/bin/uvicorn app.main:app --port 3090")
        sys.exit(1)
    
    success = asyncio.run(upload_files())
    sys.exit(0 if success else 1)
