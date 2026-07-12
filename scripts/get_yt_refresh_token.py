#!/usr/bin/env python3
"""
One-time helper: obtain a YouTube Analytics OAuth refresh token.

Prereq: download the OAuth client JSON from Google Cloud Console to
./client_secret.json (Desktop app type). See docs/setup-youtube-oauth.md.

Usage: python scripts/get_yt_refresh_token.py
Opens a browser for consent as the channel owner, then prints the values
to copy into .env.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_SECRET_FILE = "client_secret.json"


def main():
    if not os.path.exists(CLIENT_SECRET_FILE):
        print(
            f"Error: {CLIENT_SECRET_FILE} not found. Download it from "
            "Google Cloud Console (APIs & Services > Credentials).",
            file=sys.stderr,
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )

    print("\nAdd these lines to .env at the repo root:\n")
    print(f"YT_CLIENT_ID={creds.client_id}")
    print(f"YT_CLIENT_SECRET={creds.client_secret}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
