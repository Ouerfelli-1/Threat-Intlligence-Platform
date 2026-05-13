"""
Mock responses for the existing Recon Findings API (port 8001).
"""

SCOPES_RESPONSE = {
    "scopes": [
        {"id": "scope-uuid-001", "name": "example.com", "enabled": True},
        {"id": "scope-uuid-002", "name": "targetcompany.com", "enabled": True},
    ]
}

SCOPE_SUBDOMAINS_RESPONSE = {
    "subdomains": [
        {"value": "www.example.com", "source": "crt.sh", "first_seen": "2026-01-15T10:00:00Z"},
        {"value": "mail.example.com", "source": "dnsdumpster", "first_seen": "2026-01-15T10:05:00Z"},
        {"value": "api.example.com", "source": "subfinder", "first_seen": "2026-01-15T10:10:00Z"},
        {"value": "admin.example.com", "source": "crt.sh", "first_seen": "2026-01-15T10:12:00Z"},
    ]
}

SCOPE_FINDINGS_RESPONSE = {
    "findings": [
        {
            "id": "finding-001",
            "finding_type": "subdomain",
            "value": "www.example.com",
            "source": "crt.sh",
            "extra_data": {"ip": "93.184.216.34"},
        },
        {
            "id": "finding-002",
            "finding_type": "subdomain",
            "value": "mail.example.com",
            "source": "dnsdumpster",
            "extra_data": {"ip": "93.184.216.35"},
        },
        {
            "id": "finding-003",
            "finding_type": "port",
            "value": "93.184.216.34:443",
            "source": "nmap",
            "extra_data": {
                "port": 443,
                "protocol": "tcp",
                "service": "https",
                "product": "nginx",
                "version": "1.20.1",
            },
        },
        {
            "id": "finding-004",
            "finding_type": "port",
            "value": "93.184.216.34:80",
            "source": "nmap",
            "extra_data": {
                "port": 80,
                "protocol": "tcp",
                "service": "http",
                "product": "nginx",
                "version": "1.20.1",
            },
        },
        {
            "id": "finding-005",
            "finding_type": "port",
            "value": "93.184.216.34:22",
            "source": "nmap",
            "extra_data": {
                "port": 22,
                "protocol": "tcp",
                "service": "ssh",
                "product": "OpenSSH",
                "version": "8.9p1",
            },
        },
        {
            "id": "finding-006",
            "finding_type": "technology",
            "value": "WordPress 6.4",
            "source": "httpx",
            "extra_data": {"hostname": "www.example.com"},
        },
    ],
    "total": 6,
    "page": 1,
    "per_page": 50,
}

SCOPE_CVES_RESPONSE = {
    "cves": [
        {
            "id": "cve-find-001",
            "finding_type": "cve",
            "value": "CVE-2023-44487",
            "source": "nmap_cve",
            "extra_data": {
                "cvss": 7.5,
                "severity": "HIGH",
                "service": "nginx",
                "port": 443,
                "description": "HTTP/2 Rapid Reset Attack",
            },
        }
    ]
}

SCOPE_SERVICES_RESPONSE = {
    "services": [
        {"service": "https", "port": 443, "product": "nginx", "version": "1.20.1", "count": 1},
        {"service": "http", "port": 80, "product": "nginx", "version": "1.20.1", "count": 1},
        {"service": "ssh", "port": 22, "product": "OpenSSH", "version": "8.9p1", "count": 1},
    ]
}

SEARCH_RESPONSE = {
    "results": [
        {"id": "finding-001", "finding_type": "subdomain", "value": "www.example.com"},
    ],
    "total": 1,
}
