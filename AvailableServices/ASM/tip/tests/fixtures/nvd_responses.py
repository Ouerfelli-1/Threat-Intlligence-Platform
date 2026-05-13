"""
Mock responses for the NVD API v2.0.
"""

NVD_RECENT_CVES_RESPONSE = {
    "resultsPerPage": 3,
    "startIndex": 0,
    "totalResults": 3,
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2026-0001",
                "published": "2026-02-20T12:00:00.000",
                "lastModified": "2026-02-21T08:00:00.000",
                "descriptions": [
                    {"lang": "en", "value": "A critical RCE vulnerability in Apache HTTP Server 2.4.x before 2.4.58."},
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "baseScore": 9.8,
                                "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                                "baseSeverity": "CRITICAL",
                            }
                        }
                    ]
                },
                "configurations": [
                    {
                        "nodes": [
                            {
                                "cpeMatch": [
                                    {
                                        "vulnerable": True,
                                        "criteria": "cpe:2.3:a:apache:http_server:*:*:*:*:*:*:*:*",
                                        "versionEndExcluding": "2.4.58",
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "references": [
                    {"url": "https://httpd.apache.org/security/vulnerabilities_24.html"}
                ],
            }
        },
        {
            "cve": {
                "id": "CVE-2026-0002",
                "published": "2026-02-21T10:00:00.000",
                "lastModified": "2026-02-22T09:00:00.000",
                "descriptions": [
                    {"lang": "en", "value": "An information disclosure vulnerability in OpenSSL 3.0.x before 3.0.12."},
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "baseScore": 5.3,
                                "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
                                "baseSeverity": "MEDIUM",
                            }
                        }
                    ]
                },
                "configurations": [
                    {
                        "nodes": [
                            {
                                "cpeMatch": [
                                    {
                                        "vulnerable": True,
                                        "criteria": "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*",
                                        "versionEndExcluding": "3.0.12",
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "references": [],
            }
        },
        {
            "cve": {
                "id": "CVE-2026-0003",
                "published": "2026-02-22T14:00:00.000",
                "lastModified": "2026-02-22T14:00:00.000",
                "descriptions": [
                    {"lang": "en", "value": "A privilege escalation vulnerability in Example Software."},
                ],
                "metrics": {},  # no CVSS yet
                "configurations": [],
                "references": [],
            }
        },
    ],
}

NVD_SINGLE_CVE_RESPONSE = {
    "resultsPerPage": 1,
    "startIndex": 0,
    "totalResults": 1,
    "vulnerabilities": [NVD_RECENT_CVES_RESPONSE["vulnerabilities"][0]],
}

NVD_EMPTY_RESPONSE = {
    "resultsPerPage": 0,
    "startIndex": 0,
    "totalResults": 0,
    "vulnerabilities": [],
}

# ── CISA KEV ─────────────────────────────────────────────────────

CISA_KEV_RESPONSE = {
    "title": "CISA Known Exploited Vulnerabilities Catalog",
    "catalogVersion": "2026.02.25",
    "dateReleased": "2026-02-25T00:00:00.000Z",
    "count": 2,
    "vulnerabilities": [
        {
            "cveID": "CVE-2026-0001",
            "vendorProject": "Apache",
            "product": "HTTP Server",
            "vulnerabilityName": "Apache HTTP Server RCE",
            "dateAdded": "2026-02-23",
            "dueDate": "2026-03-09",
            "knownRansomwareCampaignUse": "Known",
        },
        {
            "cveID": "CVE-2025-9999",
            "vendorProject": "FooBar",
            "product": "Widget",
            "vulnerabilityName": "FooBar Widget RCE",
            "dateAdded": "2026-01-10",
            "dueDate": "2026-01-24",
            "knownRansomwareCampaignUse": "Unknown",
        },
    ],
}
