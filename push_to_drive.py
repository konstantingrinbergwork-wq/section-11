"""
push_to_drive.py

Uploads (creates or updates) a local file into a specific Google Drive folder,
authenticating as the folder owner via OAuth refresh token (NOT a service
account -- service accounts have no storage quota on personal "My Drive").

Required environment variables:
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  GOOGLE_OAUTH_REFRESH_TOKEN
  DRIVE_FOLDER_ID

Usage:
  python push_to_drive.py latest.json
  python push_to_drive.py latest.json --name training_data.json
"""
import argparse
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_drive_service():
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")

    missing = [
        name for name, val in [
            ("GOOGLE_OAUTH_CLIENT_ID", client_id),
            ("GOOGLE_OAUTH_CLIENT_SECRET", client_secret),
            ("GOOGLE_OAUTH_REFRESH_TOKEN", refresh_token),
        ] if not val
    ]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def find_file_id(service, name, folder_id):
    query = (
        f"name = '{name}' and '{folder_id}' in parents "
        "and trashed = false"
    )
    results = service.files().list(
        q=query, spaces="drive", fields="files(id, name)"
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def push_file(local_path, drive_name, folder_id, mimetype="application/json"):
    service = get_drive_service()
    media = MediaFileUpload(local_path, mimetype=mimetype, resumable=False)
    existing_id = find_file_id(service, drive_name, folder_id)

    if existing_id:
        service.files().update(fileId=existing_id, media_body=media).execute()
        print(f"Updated existing file '{drive_name}' (id={existing_id})")
    else:
        metadata = {"name": drive_name, "parents": [folder_id]}
        created = service.files().create(
            body=metadata, media_body=media, fields="id"
        ).execute()
        print(f"Created new file '{drive_name}' (id={created.get('id')})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("local_path", help="Path to the local file to upload")
    parser.add_argument(
        "--name", default=None,
        help="Filename to use in Drive (defaults to the local filename)"
    )
    parser.add_argument(
        "--mimetype", default="application/json",
        help="MIME type for the upload (default: application/json)"
    )
    args = parser.parse_args()

    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    if not folder_id:
        print("ERROR: DRIVE_FOLDER_ID env var not set", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.local_path):
        print(f"ERROR: file not found: {args.local_path}", file=sys.stderr)
        sys.exit(1)

    drive_name = args.name or os.path.basename(args.local_path)
    push_file(args.local_path, drive_name, folder_id, args.mimetype)


if __name__ == "__main__":
    main()
