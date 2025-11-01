#!/usr/bin/env python3
"""
Gmail Diagnostic Script
Check what emails are actually in the inbox
"""

import os
import sys
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.core.config import settings

def main():
    """Diagnose Gmail inbox"""
    print("=" * 60)
    print("Gmail Diagnostic Tool")
    print("=" * 60)

    # Load credentials
    if not os.path.exists(settings.GMAIL_TOKEN_PATH):
        print(f"❌ Token not found at {settings.GMAIL_TOKEN_PATH}")
        return

    creds = Credentials.from_authorized_user_file(
        settings.GMAIL_TOKEN_PATH,
        settings.gmail_scopes_list
    )

    service = build('gmail', 'v1', credentials=creds)

    # Test 1: Check ALL recent emails (read + unread)
    print("\n📧 Test 1: ALL emails from last 48 hours (read + unread)")
    print("-" * 60)
    after_date = datetime.now() - timedelta(hours=48)
    after_timestamp = int(after_date.timestamp())

    query_all = f"after:{after_timestamp}"
    results_all = service.users().messages().list(
        userId='me',
        q=query_all,
        maxResults=50
    ).execute()

    messages_all = results_all.get('messages', [])
    print(f"Found {len(messages_all)} total emails")

    for msg in messages_all[:10]:  # Show first 10
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()

        headers = message['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        # Check if unread
        labels = message.get('labelIds', [])
        is_unread = 'UNREAD' in labels

        print(f"\n  {'[UNREAD]' if is_unread else '[READ]  '} {sender[:40]}")
        print(f"  Subject: {subject[:60]}")
        print(f"  Date: {date}")

    # Test 2: Check UNREAD emails only
    print("\n\n📧 Test 2: UNREAD emails from last 48 hours")
    print("-" * 60)

    query_unread = f"is:unread after:{after_timestamp}"
    results_unread = service.users().messages().list(
        userId='me',
        q=query_unread,
        maxResults=50
    ).execute()

    messages_unread = results_unread.get('messages', [])
    print(f"Found {len(messages_unread)} unread emails")

    for msg in messages_unread:
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()

        headers = message['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        print(f"\n  From: {sender}")
        print(f"  Subject: {subject}")
        print(f"  Date: {date}")

    # Test 3: Search for emails from gregori.bonetto@gmail.com
    print("\n\n📧 Test 3: Emails from gregori.bonetto@gmail.com (last 48h)")
    print("-" * 60)

    query_sender = f"from:gregori.bonetto@gmail.com after:{after_timestamp}"
    results_sender = service.users().messages().list(
        userId='me',
        q=query_sender,
        maxResults=20
    ).execute()

    messages_sender = results_sender.get('messages', [])
    print(f"Found {len(messages_sender)} emails from gregori.bonetto@gmail.com")

    for msg in messages_sender:
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()

        headers = message['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

        # Check labels
        labels = message.get('labelIds', [])
        is_unread = 'UNREAD' in labels
        is_spam = 'SPAM' in labels
        is_trash = 'TRASH' in labels

        status = []
        if is_unread:
            status.append('UNREAD')
        else:
            status.append('READ')
        if is_spam:
            status.append('SPAM')
        if is_trash:
            status.append('TRASH')

        print(f"\n  [{', '.join(status)}]")
        print(f"  From: {sender}")
        print(f"  Subject: {subject}")
        print(f"  Date: {date}")

    # Test 4: Check timestamp calculation
    print("\n\n🕐 Test 4: Timestamp Calculation")
    print("-" * 60)
    now = datetime.now()
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"24h ago: {after_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Unix timestamp used in query: {after_timestamp}")

    print("\n" + "=" * 60)
    print("✅ Diagnostic complete")
    print("=" * 60)

if __name__ == "__main__":
    main()
