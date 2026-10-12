"""
Command line interface: ``superbio upload <local_path> [datahub_path]``.

Credentials come from the environment, either SUPERBIO_EMAIL and SUPERBIO_PASSWORD
or SUPERBIO_TOKEN and SUPERBIO_USER_ID. SUPERBIO_BASE_URL overrides the API address.
"""

import argparse
import os
import sys
from typing import List, Optional

import requests

from superbio.client import Client
from superbio.upload import DEFAULT_CONCURRENCY


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="superbio", description="Superbio command line tools")
    commands = parser.add_subparsers(dest="command", required=True)

    upload = commands.add_parser(
        "upload",
        help="Upload a file or folder to your Data Hub",
        description="Upload a file or folder to your Data Hub. Re-run the same command to resume "
                    "an interrupted upload.",
    )
    upload.add_argument("local_path", help="File or folder to upload")
    upload.add_argument("datahub_path", nargs="?", default="",
                        help="Destination folder in the Data Hub (default: root)")
    upload.add_argument("--org", action="store_true", help="Upload to the organisation Data Hub")
    upload.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Parts uploaded in parallel per file (default: {DEFAULT_CONCURRENCY})")
    return parser


def _client_from_env() -> Client:
    base_url = os.environ.get("SUPERBIO_BASE_URL")
    if base_url:
        Client.BASE_URL = base_url.rstrip("/")
    email = os.environ.get("SUPERBIO_EMAIL")
    password = os.environ.get("SUPERBIO_PASSWORD")
    token = os.environ.get("SUPERBIO_TOKEN")
    user_id = os.environ.get("SUPERBIO_USER_ID")
    if not ((email and password) or (token and user_id)):
        raise SystemExit(
            "Set SUPERBIO_EMAIL and SUPERBIO_PASSWORD (or SUPERBIO_TOKEN and SUPERBIO_USER_ID)."
        )
    return Client(email=email, password=password, token=token, user_id=user_id)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    client = _client_from_env()
    try:
        results = client.upload_to_datahub(
            args.datahub_path,
            local_files={"upload": args.local_path},
            is_organisation=args.org,
            concurrency=args.concurrency,
        )
    except requests.RequestException as error:
        response = getattr(error, "response", None)
        print(f"Upload failed: {response.text if response is not None else error}", file=sys.stderr)
        print("Run the same command again to resume.", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as error:
        print(f"Upload failed: {error}", file=sys.stderr)
        return 1
    print(f"Uploaded {len(results)} file(s) to the Data Hub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
