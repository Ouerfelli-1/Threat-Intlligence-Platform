"""CLI tool for managing DomainWatch users.

Usage:
    python scripts/create_user.py                   # interactive
    python scripts/create_user.py -u alice -p S3cur3 # non-interactive
    python scripts/create_user.py --reset -u admin   # reset password
"""

import argparse
import getpass
import secrets
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.database import get_db, hash_password, init_db


def _strong_password() -> str:
    return secrets.token_urlsafe(16)


def _prompt_password() -> str:
    while True:
        pw = getpass.getpass("Password (leave blank to auto-generate): ")
        if not pw:
            pw = _strong_password()
            print(f"Generated password: {pw}")
            return pw
        if len(pw) < 8:
            print("Password must be at least 8 characters.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("Passwords do not match.")
            continue
        return pw


def create_user(username: str, password: str) -> bool:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            print(f"Error: user '{username}' already exists. Use --reset to change password.")
            return False
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password)),
        )
    print(f"User '{username}' created successfully.")
    return True


def reset_password(username: str, password: str) -> bool:
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            print(f"Error: user '{username}' does not exist.")
            return False
        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hash_password(password), username),
        )
    print(f"Password for '{username}' has been reset.")
    return True


def list_users():
    with get_db() as conn:
        users = conn.execute("SELECT id, username FROM users ORDER BY id").fetchall()
    if not users:
        print("No users found.")
        return
    print(f"{'ID':<6}{'Username'}")
    print("-" * 30)
    for u in users:
        print(f"{u['id']:<6}{u['username']}")


def delete_user(username: str) -> bool:
    if username == "admin":
        print("Error: cannot delete the admin user.")
        return False
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            print(f"Error: user '{username}' does not exist.")
            return False
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
    print(f"User '{username}' deleted.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Manage DomainWatch users")
    sub = parser.add_subparsers(dest="command", help="Command")

    # create
    p_create = sub.add_parser("create", help="Create a new user")
    p_create.add_argument("-u", "--username", required=False, help="Username")
    p_create.add_argument("-p", "--password", required=False, help="Password (omit to prompt or auto-generate)")

    # reset
    p_reset = sub.add_parser("reset", help="Reset a user's password")
    p_reset.add_argument("-u", "--username", required=False, help="Username")
    p_reset.add_argument("-p", "--password", required=False, help="New password (omit to prompt or auto-generate)")

    # list
    sub.add_parser("list", help="List all users")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a user")
    p_delete.add_argument("-u", "--username", required=False, help="Username to delete")

    args = parser.parse_args()

    # Ensure DB is initialised
    init_db()

    if args.command == "list":
        list_users()
        return

    if args.command == "create":
        username = args.username or input("Username: ").strip()
        if not username:
            print("Error: username cannot be empty.")
            sys.exit(1)
        password = args.password or _prompt_password()
        ok = create_user(username, password)
        sys.exit(0 if ok else 1)

    if args.command == "reset":
        username = args.username or input("Username: ").strip()
        if not username:
            print("Error: username cannot be empty.")
            sys.exit(1)
        password = args.password or _prompt_password()
        ok = reset_password(username, password)
        sys.exit(0 if ok else 1)

    if args.command == "delete":
        username = args.username or input("Username to delete: ").strip()
        if not username:
            print("Error: username cannot be empty.")
            sys.exit(1)
        confirm = input(f"Delete user '{username}'? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            sys.exit(0)
        ok = delete_user(username)
        sys.exit(0 if ok else 1)

    # No subcommand — show help
    parser.print_help()


if __name__ == "__main__":
    main()
