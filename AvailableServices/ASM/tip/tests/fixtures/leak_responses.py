"""
Sample data for the dummy leak API and leak collector tests.
"""

SAMPLE_LEAKS = [
    {
        "id": "leak-001",
        "source": "DarkMarket Forums",
        "type": "credentials",
        "discovered_date": "2026-02-20T10:00:00Z",
        "affected_domains": ["example.com", "mail.example.com"],
        "affected_emails": ["admin@example.com", "user@example.com"],
        "record_count": 1500,
        "contains_passwords": True,
        "contains_pii": False,
        "severity": "HIGH",
        "sample": [
            {"email": "admin@example.com", "password_hash": "5f4dcc3b5aa765d61d8327deb882cf99"},
        ],
    },
    {
        "id": "leak-002",
        "source": "Paste Site",
        "type": "database_dump",
        "discovered_date": "2026-02-22T14:30:00Z",
        "affected_domains": ["targetcompany.com"],
        "affected_emails": ["ceo@targetcompany.com", "hr@targetcompany.com"],
        "record_count": 5000,
        "contains_passwords": True,
        "contains_pii": True,
        "severity": "CRITICAL",
        "sample": [
            {"name": "John Doe", "email": "ceo@targetcompany.com"},
        ],
    },
    {
        "id": "leak-003",
        "source": "Telegram Channel",
        "type": "documents",
        "discovered_date": "2026-02-23T09:00:00Z",
        "affected_domains": ["othercompany.org"],
        "affected_emails": [],
        "record_count": 200,
        "contains_passwords": False,
        "contains_pii": True,
        "severity": "MEDIUM",
        "sample": [],
    },
]

LEAK_SEARCH_RESPONSE_EXAMPLE_COM = {
    "leaks": [SAMPLE_LEAKS[0]],
    "total": 1,
}

LEAK_SEARCH_NO_RESULTS = {
    "leaks": [],
    "total": 0,
}

LEAK_ALL_RESPONSE = {
    "leaks": SAMPLE_LEAKS,
    "total": len(SAMPLE_LEAKS),
}
