"""
Gmail OAuth Manual Token Generator
Use this if gmail_auth.py fails with redirect_uri_mismatch

This script guides you through manual OAuth flow using authorization code
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def main():
    """Manual OAuth flow - user copies auth code manually"""

    # Paths
    base_dir = Path(__file__).parent.parent
    credentials_path = base_dir / 'credentials' / 'credentials.json'
    token_path = base_dir / 'credentials' / 'token.json'

    # Load credentials
    if not credentials_path.exists():
        print("❌ credentials.json not found!")
        sys.exit(1)

    with open(credentials_path, 'r') as f:
        creds_data = json.load(f)

    # Extract client info (support both web and installed types)
    if "web" in creds_data:
        client_id = creds_data["web"]["client_id"]
        client_secret = creds_data["web"]["client_secret"]
        auth_uri = creds_data["web"]["auth_uri"]
        token_uri = creds_data["web"]["token_uri"]
    elif "installed" in creds_data:
        client_id = creds_data["installed"]["client_id"]
        client_secret = creds_data["installed"]["client_secret"]
        auth_uri = creds_data["installed"]["auth_uri"]
        token_uri = creds_data["installed"]["token_uri"]
    else:
        print("❌ Invalid credentials.json format")
        sys.exit(1)

    print("="*60)
    print("🔐 Gmail OAuth Manual Authentication")
    print("="*60)
    print()

    # Build auth URL
    scope_param = "+".join([s.replace("https://www.googleapis.com/auth/", "") for s in SCOPES])

    auth_url = (
        f"{auth_uri}?"
        f"client_id={client_id}&"
        f"redirect_uri=urn:ietf:wg:oauth:2.0:oob&"
        f"response_type=code&"
        f"scope={'%20'.join(SCOPES)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    print("📝 STEP 1: Copy this URL and paste it in your browser:")
    print()
    print(auth_url)
    print()
    print("="*60)
    print()

    print("📝 STEP 2: Authorize the application in your browser")
    print("   - Select your Gmail account")
    print("   - Click 'Allow'")
    print()

    print("📝 STEP 3: Copy the authorization code shown")
    print("   Google will show you a code like: 4/0Adeu5BW...")
    print()

    # Get auth code from user
    auth_code = input("📋 Paste the authorization code here: ").strip()

    if not auth_code:
        print("❌ No code provided")
        sys.exit(1)

    print()
    print("🔄 Exchanging code for tokens...")

    # Exchange code for token
    import requests

    token_response = requests.post(token_uri, data={
        'code': auth_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        'grant_type': 'authorization_code'
    })

    if token_response.status_code != 200:
        print(f"❌ Token exchange failed: {token_response.text}")
        sys.exit(1)

    token_data = token_response.json()

    # Create credentials object
    creds = Credentials(
        token=token_data['access_token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    # Save token
    with open(token_path, 'w') as token:
        token.write(creds.to_json())

    print(f"💾 Token saved to: {token_path}")

    # Test the credentials
    try:
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()

        print()
        print("="*60)
        print("🎉 Gmail OAuth Configuration Successful!")
        print("="*60)
        print(f"📧 Email: {profile.get('emailAddress')}")
        print(f"📬 Total messages: {profile.get('messagesTotal', 0)}")
        print(f"📨 Total threads: {profile.get('threadsTotal', 0)}")
        print("="*60)
        print()
        print("✅ DisruptIQ can now access your Gmail account")
        print("🚀 You can now generate the Digest with real emails!")

    except Exception as e:
        print(f"\n⚠️  Could not test Gmail access: {e}")
        print("   The token was saved, but there might be an issue")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Authentication cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
