"""Dork catalog — categories of search patterns, target-type aware.

Each dork template uses Python str.format placeholders:
  {target} — the raw target (domain / email / ip / company)
  {target_q} — quoted target for exact-match (`"example.com"`)

The catalog is intentionally curated and conservative — broad enough to be
useful, narrow enough that a full 7-category run against a single target
fires ~35 queries (which fits inside Google CSE's 100/day free tier with
room for several investigations per day before fallback kicks in).

Extending the catalog: add a new entry under CATEGORIES with a description
and a list of dork templates. UI renders categories from this dict.
"""
from __future__ import annotations

from typing import Literal

TargetType = Literal["domain", "email", "ip", "company"]


# ──────────────────────────────────────────────────────────────────────────
# Domain-targeted dorks
# ──────────────────────────────────────────────────────────────────────────
_DOMAIN: dict[str, dict] = {
    "exposed_files": {
        "label": "Exposed files",
        "description": "Config, env, backup, log and database dumps left on the public web.",
        "dorks": [
            'site:{target} ext:env',
            'site:{target} ext:sql',
            'site:{target} ext:bak',
            'site:{target} ext:log',
            'site:{target} ext:json (apikey OR password OR secret)',
            'site:{target} ext:yml (token OR password OR aws)',
            'site:{target} ext:xml (password OR secret)',
        ],
    },
    "admin_panels": {
        "label": "Admin panels & login pages",
        "description": "Authenticated entry points that shouldn't be Google-crawlable.",
        "dorks": [
            'site:{target} inurl:admin',
            'site:{target} inurl:wp-admin',
            'site:{target} inurl:phpmyadmin',
            'site:{target} inurl:login',
            'site:{target} intitle:"login" -inurl:public',
        ],
    },
    "directory_listing": {
        "label": "Open directory listings",
        "description": "Apache/nginx index pages exposing file trees.",
        "dorks": [
            'site:{target} intitle:"index of"',
            'site:{target} intitle:"index of" "parent directory"',
            'site:{target} intitle:"index of" (backup OR config OR db)',
        ],
    },
    "sensitive_data": {
        "label": "Sensitive data leaks",
        "description": "Keys, passwords, tokens accidentally indexed by Google.',",
        "dorks": [
            'site:{target} intext:"BEGIN RSA PRIVATE KEY"',
            'site:{target} intext:"AWS_SECRET_ACCESS_KEY"',
            'site:{target} intext:"api_key"',
            'site:{target} intext:"client_secret"',
            'site:{target} intext:"jdbc:postgresql"',
        ],
    },
    "github_leaks": {
        "label": "GitHub / GitLab leaks",
        "description": "Source-control repos referencing this target with secrets nearby.",
        "dorks": [
            'site:github.com {target_q} (password OR token OR api_key)',
            'site:gitlab.com {target_q} (password OR token)',
            'site:bitbucket.org {target_q} (password OR token)',
        ],
    },
    "paste_sites": {
        "label": "Paste sites & dumps",
        "description": "Pastebin / ghostbin / paste.ee leaks mentioning the target.",
        "dorks": [
            'site:pastebin.com {target_q}',
            'site:paste.ee {target_q}',
            'site:ghostbin.com {target_q}',
            'site:hastebin.com {target_q}',
        ],
    },
    "cloud_storage": {
        "label": "Cloud storage buckets",
        "description": "S3/GCS/Azure buckets owned by or referencing the target.",
        "dorks": [
            'site:s3.amazonaws.com {target_q}',
            'site:storage.googleapis.com {target_q}',
            'site:blob.core.windows.net {target_q}',
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Email-targeted dorks — narrow set, focused on breach/dump exposure.
# ──────────────────────────────────────────────────────────────────────────
_EMAIL: dict[str, dict] = {
    "breach_exposure": {
        "label": "Breach / dump exposure",
        "description": "Email appearing in public dumps, paste sites, or text files.",
        "dorks": [
            '{target_q} filetype:csv',
            '{target_q} filetype:txt',
            'site:pastebin.com {target_q}',
            'site:psbdmp.ws {target_q}',
        ],
    },
    "github_leaks": {
        "label": "Email in source control",
        "description": "Commits / configs with this email + nearby credentials.",
        "dorks": [
            'site:github.com {target_q}',
            'site:gitlab.com {target_q}',
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────
# IP-targeted dorks — Shodan / Censys / passive DNS coverage by referenced IP.
# ──────────────────────────────────────────────────────────────────────────
_IP: dict[str, dict] = {
    "shodan_censys": {
        "label": "Public scan databases",
        "description": "Shodan / Censys / FOFA records that publicly cite this IP.",
        "dorks": [
            'site:shodan.io {target_q}',
            'site:censys.io {target_q}',
            'site:fofa.so {target_q}',
            'site:zoomeye.org {target_q}',
        ],
    },
    "abuse_mentions": {
        "label": "Abuse reports",
        "description": "Forums / advisories / blocklists mentioning the IP.",
        "dorks": [
            'site:abuseipdb.com {target_q}',
            'site:virustotal.com {target_q}',
            '{target_q} ("malicious" OR "C2" OR "ransomware" OR "phishing")',
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Company-name targeted dorks.
# ──────────────────────────────────────────────────────────────────────────
_COMPANY: dict[str, dict] = {
    "breach_exposure": {
        "label": "Breach mentions",
        "description": "Public dumps and paste sites referencing the company.",
        "dorks": [
            '{target_q} (breach OR leak OR dump) filetype:txt',
            'site:pastebin.com {target_q} (password OR breach)',
            '{target_q} site:github.com (password OR token)',
        ],
    },
    "exec_emails": {
        "label": "Executive / staff emails",
        "description": "Public mentions of @company.tld addresses.",
        "dorks": [
            'intext:"@{target}" (ceo OR cto OR ciso OR director)',
            '"@{target}" filetype:pdf',
        ],
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Catalog union — keyed by target_type for /dorks/catalog and runner lookup.
# ──────────────────────────────────────────────────────────────────────────
CATEGORIES: dict[TargetType, dict[str, dict]] = {
    "domain":  _DOMAIN,
    "email":   _EMAIL,
    "ip":      _IP,
    "company": _COMPANY,
}


def build_dorks(
    target: str,
    target_type: TargetType,
    categories: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return [(category, dork_string), ...] ready to execute against the
    search backend.

    `categories` filters to a subset. None = every category for that target
    type. Unknown categories are silently dropped (forward-compat for the
    UI sending old category names).
    """
    if target_type not in CATEGORIES:
        raise ValueError(f"unsupported target_type: {target_type}")
    cat_dict = CATEGORIES[target_type]

    target_clean = target.strip()
    target_q = f'"{target_clean}"'

    out: list[tuple[str, str]] = []
    selected = categories or list(cat_dict.keys())
    for cat_name in selected:
        spec = cat_dict.get(cat_name)
        if not spec:
            continue
        for template in spec["dorks"]:
            try:
                rendered = template.format(target=target_clean, target_q=target_q)
            except (KeyError, IndexError):
                # Templates only use {target}/{target_q}; anything else is a
                # catalog bug — skip rather than blow up the whole run.
                continue
            out.append((cat_name, rendered))
    return out
