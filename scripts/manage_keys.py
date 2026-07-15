"""Manual API key management — issue, revoke, list. No self-service
endpoint (docs/CONTEXT.md §1). Run with `uv run python -m scripts.manage_keys <command>`.
"""

import argparse
import secrets
import sys
from datetime import UTC, datetime

from app.shared.auth import hash_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey


def issue(label: str) -> None:
    plaintext = secrets.token_urlsafe(32)
    with SessionLocal() as session:
        api_key = ApiKey(key_hash=hash_key(plaintext), label=label)
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
    print(f"Issued key id={api_key.id} label={label!r}")
    print(f"Key: {plaintext}")
    print("Save this now — it will not be shown again.")


def revoke(key_id: int) -> None:
    with SessionLocal() as session:
        api_key = session.get(ApiKey, key_id)
        if api_key is None:
            print(f"No key with id={key_id}", file=sys.stderr)
            raise SystemExit(1)
        if api_key.revoked_at is not None:
            print(f"Key id={key_id} is already revoked (at {api_key.revoked_at})", file=sys.stderr)
            raise SystemExit(1)
        api_key.revoked_at = datetime.now(UTC)
        session.commit()
    print(f"Revoked key id={key_id}")


def list_keys() -> None:
    with SessionLocal() as session:
        keys = session.query(ApiKey).order_by(ApiKey.id).all()
    if not keys:
        print("No keys issued yet.")
        return
    for key in keys:
        status = f"revoked at {key.revoked_at}" if key.revoked_at else "active"
        last_used = key.last_used_at or "never"
        print(f"id={key.id} label={key.label!r} status={status} last_used_at={last_used}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    issue_parser = subparsers.add_parser("issue", help="Issue a new API key")
    issue_parser.add_argument("--label", required=True, help="Who/what this key is for")

    revoke_parser = subparsers.add_parser("revoke", help="Revoke an existing API key")
    revoke_parser.add_argument("--key-id", type=int, required=True)

    subparsers.add_parser("list", help="List all issued keys")

    args = parser.parse_args()

    if args.command == "issue":
        issue(args.label)
    elif args.command == "revoke":
        revoke(args.key_id)
    elif args.command == "list":
        list_keys()


if __name__ == "__main__":
    main()
