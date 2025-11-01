"""
Gmail OAuth Authentication Script
Run this script once to authorize DisruptIQ to access your Gmail account
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

def main():
    """Authenticate and save Gmail OAuth credentials"""

    # Paths
    base_dir = Path(__file__).parent.parent
    credentials_path = base_dir / 'credentials' / 'credentials.json'
    token_path = base_dir / 'credentials' / 'token.json'

    # Ensure credentials directory exists
    credentials_path.parent.mkdir(exist_ok=True)

    # Check if credentials file exists
    if not credentials_path.exists():
        print("❌ Error: credentials.json not found!")
        print(f"   Expected location: {credentials_path}")
        print("\n📝 Instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create OAuth 2.0 credentials")
        print("3. Download the JSON file")
        print(f"4. Save it as: {credentials_path}")
        sys.exit(1)

    creds = None

    # Load existing token if available
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            print("📄 Existing token found")
        except Exception as e:
            print(f"⚠️  Could not load existing token: {e}")

    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            try:
                creds.refresh(Request())
                print("✅ Token refreshed successfully")
            except Exception as e:
                print(f"❌ Token refresh failed: {e}")
                print("🔄 Starting fresh authentication...")
                creds = None

        if not creds:
            print("\n🔐 Starting Gmail OAuth authentication...")
            print("📌 A browser window will open for authorization")
            print("   Please log in and grant access to DisruptIQ\n")

            try:
                # Read credentials to detect type (web vs installed)
                with open(credentials_path, 'r') as f:
                    creds_data = json.load(f)

                # Support both "web" and "installed" credential types
                if "web" in creds_data:
                    print("📝 Detected 'web' type credentials (adapting for local use)")
                    client_config = {
                        "installed": {
                            "client_id": creds_data["web"]["client_id"],
                            "client_secret": creds_data["web"]["client_secret"],
                            "auth_uri": creds_data["web"]["auth_uri"],
                            "token_uri": creds_data["web"]["token_uri"],
                            "redirect_uris": ["http://localhost:8080/"]
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(
                        client_config,
                        SCOPES
                    )
                else:
                    # Standard "installed" type credentials
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(credentials_path),
                        SCOPES
                    )

                creds = flow.run_local_server(
                    port=8080,
                    prompt='consent',
                    success_message='✅ Authentication successful! You can close this window.',
                    open_browser=True
                )
                print("✅ Authorization granted!")
            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                import traceback
                traceback.print_exc()
                sys.exit(1)

        # Save credentials for next run
        try:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"💾 Token saved to: {token_path}")
        except Exception as e:
            print(f"⚠️  Could not save token: {e}")
    else:
        print("✅ Valid token already exists")

    # Test the credentials
    try:
        from googleapiclient.discovery import build

        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()

        print("\n" + "="*50)
        print("🎉 Gmail OAuth Configuration Successful!")
        print("="*50)
        print(f"📧 Email: {profile.get('emailAddress')}")
        print(f"📬 Total messages: {profile.get('messagesTotal', 0)}")
        print(f"📨 Total threads: {profile.get('threadsTotal', 0)}")
        print("="*50)
        print("\n✅ DisruptIQ can now access your Gmail account")
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
