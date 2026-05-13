import hashlib
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"


# ---------------------------------------------------------------------------
#  DB connection context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
#  Password hashing (PBKDF2-HMAC-SHA256, 600 000 iterations)
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
    if ":" not in stored:
        # Legacy plaintext — validate then return False to force re-login after upgrade
        if not secrets.compare_digest(password, stored):
            return False
        # Auto-upgrade to PBKDF2 hash in-place
        try:
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET password = ? WHERE password = ?",
                    (hash_password(password), stored),
                )
            print("[DomainWatch] Auto-upgraded legacy plaintext password to PBKDF2")
        except Exception:
            pass  # upgrade is best-effort; login still succeeds
        return True
    salt, hashed = stored.split(":", 1)
    computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return secrets.compare_digest(computed, hashed)


# ---------------------------------------------------------------------------
#  Schema migration helpers
# ---------------------------------------------------------------------------

_ALLOWED_TABLES = {
    "domains", "users", "domain_history",
    "domain_iocs", "domain_subdomains", "status", "sources",
}
_ALLOWED_COLUMNS = re.compile(r'^[a-z_]+$')
_ALLOWED_TYPES = {
    "TEXT", "INTEGER", "REAL", "BLOB",
    "TEXT DEFAULT ''", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0 NOT NULL",
}

def _add_column(conn, table: str, column: str, col_type: str):
    if table not in _ALLOWED_TABLES or not _ALLOWED_COLUMNS.match(column) or col_type not in _ALLOWED_TYPES:
        raise ValueError(f"Invalid migration params: {table}.{column} {col_type}")
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # column already exists


# ---------------------------------------------------------------------------
#  Database initialisation & seed data
# ---------------------------------------------------------------------------

def init_db():
    with get_db() as conn:
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL;")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                case_id TEXT DEFAULT '',
                source_id INTEGER REFERENCES sources(id),
                status TEXT NOT NULL DEFAULT 'unknown',
                details_json TEXT,
                content_hash TEXT,
                screenshot_path TEXT,
                created_at TEXT NOT NULL,
                last_checked TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                added_by TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER NOT NULL REFERENCES domains(id),
                change_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                screenshot_path TEXT,
                changed_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_iocs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER NOT NULL REFERENCES domains(id),
                ioc_value TEXT NOT NULL,
                ioc_type TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                UNIQUE(domain_id, ioc_value, ioc_type)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_subdomains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER NOT NULL REFERENCES domains(id),
                subdomain TEXT NOT NULL,
                a_records_json TEXT,
                aaaa_records_json TEXT,
                cname_target TEXT,
                ns_records_json TEXT,
                soa_record TEXT,
                is_delegated INTEGER NOT NULL DEFAULT 0,
                is_resolving INTEGER NOT NULL DEFAULT 0,
                wildcard_match INTEGER NOT NULL DEFAULT 0,
                last_checked_at TEXT,
                last_error TEXT,
                first_seen_at TEXT NOT NULL,
                UNIQUE(domain_id, subdomain)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS status (
                state TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        # Seed default sources
        for src in ("CTI", "CSIRT"):
            conn.execute("INSERT OR IGNORE INTO sources (name) VALUES (?)", (src,))

        # Seed status table if empty
        cur = conn.execute("SELECT COUNT(*) as cnt FROM status")
        if cur.fetchone()["cnt"] == 0:
            conn.execute("INSERT INTO status (state) VALUES ('idle')")

        # Migrate existing domains table if columns are missing
        _add_column(conn, "domains", "case_id", "TEXT DEFAULT ''")
        _add_column(conn, "domains", "source_id", "INTEGER")
        _add_column(conn, "domains", "details_json", "TEXT")
        _add_column(conn, "domains", "content_hash", "TEXT")
        _add_column(conn, "domains", "screenshot_path", "TEXT")
        _add_column(conn, "domains", "created_at", "TEXT DEFAULT ''")
        _add_column(conn, "domains", "archived", "INTEGER DEFAULT 0")
        _add_column(conn, "domains", "added_by", "TEXT DEFAULT ''")

        # Migrate existing domain_subdomains table if enrichment columns are missing
        _add_column(conn, "domain_subdomains", "a_records_json", "TEXT")
        _add_column(conn, "domain_subdomains", "aaaa_records_json", "TEXT")
        _add_column(conn, "domain_subdomains", "cname_target", "TEXT")
        _add_column(conn, "domain_subdomains", "ns_records_json", "TEXT")
        _add_column(conn, "domain_subdomains", "soa_record", "TEXT")
        _add_column(conn, "domain_subdomains", "is_delegated", "INTEGER DEFAULT 0 NOT NULL")
        _add_column(conn, "domain_subdomains", "is_resolving", "INTEGER DEFAULT 0 NOT NULL")
        _add_column(conn, "domain_subdomains", "wildcard_match", "INTEGER DEFAULT 0 NOT NULL")
        _add_column(conn, "domain_subdomains", "last_checked_at", "TEXT")
        _add_column(conn, "domain_subdomains", "last_error", "TEXT")

        # Seed admin user with a strong generated password on first run
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("admin",)
        ).fetchone()

        if not existing_user:
            generated_pw = secrets.token_urlsafe(16)
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                ("admin", hash_password(generated_pw))
            )
            print("\n" + "=" * 60)
            print("  DOMAINWATCH — INITIAL ADMIN CREDENTIALS")
            print("=" * 60)
            print(f"  Username : admin")
            print(f"  Password : {generated_pw}")
            print("=" * 60)
            print("  Save this password now. It will NOT be shown again.")
            print("=" * 60 + "\n")