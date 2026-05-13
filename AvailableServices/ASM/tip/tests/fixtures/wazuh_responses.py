"""
Realistic mock responses for the Wazuh REST API.

Based on the Wazuh 4.x API documentation.  Three mock agents are
provided: Ubuntu (Apache), CentOS (Nginx), and Windows (IIS).
"""

# ── Authentication ───────────────────────────────────────────────

AUTH_RESPONSE = {
    "data": {
        "token": "eyJhbGciOiJFUzUxMiIsInR5cCI6IkpXVCJ9.mock_token_payload.mock_sig"
    }
}

AUTH_FAILURE = {"title": "Unauthorized", "detail": "Invalid credentials"}

# ── Agents ───────────────────────────────────────────────────────

AGENTS_RESPONSE = {
    "data": {
        "affected_items": [
            {
                "id": "001",
                "name": "ubuntu-web",
                "ip": "10.0.1.10",
                "status": "active",
                "os": {"name": "Ubuntu", "version": "22.04.3 LTS", "platform": "ubuntu"},
                "node_name": "node01",
                "version": "Wazuh v4.9.0",
            },
            {
                "id": "002",
                "name": "centos-app",
                "ip": "10.0.1.20",
                "status": "active",
                "os": {"name": "CentOS", "version": "8", "platform": "centos"},
                "node_name": "node01",
                "version": "Wazuh v4.9.0",
            },
            {
                "id": "003",
                "name": "win-iis",
                "ip": "10.0.1.30",
                "status": "active",
                "os": {"name": "Microsoft Windows Server 2019", "version": "10.0.17763", "platform": "windows"},
                "node_name": "node01",
                "version": "Wazuh v4.9.0",
            },
        ],
        "total_affected_items": 3,
    }
}

# ── Syscollector: Packages ───────────────────────────────────────

PACKAGES_AGENT_001 = {
    "data": {
        "affected_items": [
            {"name": "apache2", "version": "2.4.52-1ubuntu4.6", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
            {"name": "openssl", "version": "3.0.2-0ubuntu1.10", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
            {"name": "libssl3", "version": "3.0.2-0ubuntu1.10", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
            {"name": "php8.1", "version": "8.1.2-1ubuntu2.14", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
            {"name": "mysql-server", "version": "8.0.35-0ubuntu0.22.04.1", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
            {"name": "curl", "version": "7.81.0-1ubuntu1.14", "vendor": "Ubuntu Developers", "architecture": "amd64", "format": "deb"},
        ],
        "total_affected_items": 6,
    }
}

PACKAGES_AGENT_002 = {
    "data": {
        "affected_items": [
            {"name": "nginx", "version": "1.20.1-9.el8", "vendor": "CentOS", "architecture": "x86_64", "format": "rpm"},
            {"name": "openssl", "version": "1.1.1k-9.el8", "vendor": "CentOS", "architecture": "x86_64", "format": "rpm"},
            {"name": "postgresql-server", "version": "12.17-1.el8", "vendor": "CentOS", "architecture": "x86_64", "format": "rpm"},
            {"name": "python3", "version": "3.6.8-51.el8", "vendor": "CentOS", "architecture": "x86_64", "format": "rpm"},
        ],
        "total_affected_items": 4,
    }
}

PACKAGES_AGENT_003 = {
    "data": {
        "affected_items": [
            {"name": "Microsoft-Windows-IIS-WebServer", "version": "10.0.17763.1", "vendor": "Microsoft", "architecture": "x86_64", "format": "win"},
            {"name": ".NET Framework", "version": "4.8.04084", "vendor": "Microsoft", "architecture": "x86_64", "format": "win"},
            {"name": "Microsoft SQL Server 2019", "version": "15.0.2000.5", "vendor": "Microsoft", "architecture": "x86_64", "format": "win"},
        ],
        "total_affected_items": 3,
    }
}

# ── Syscollector: OS ─────────────────────────────────────────────

OS_AGENT_001 = {
    "data": {
        "affected_items": [
            {"os_name": "Ubuntu", "os_version": "22.04.3 LTS", "hostname": "ubuntu-web", "architecture": "x86_64"}
        ]
    }
}

# ── Syscollector: Ports ──────────────────────────────────────────

PORTS_AGENT_001 = {
    "data": {
        "affected_items": [
            {"local": {"ip": "0.0.0.0", "port": 80}, "protocol": "tcp", "state": "listening", "process": "apache2"},
            {"local": {"ip": "0.0.0.0", "port": 443}, "protocol": "tcp", "state": "listening", "process": "apache2"},
            {"local": {"ip": "127.0.0.1", "port": 3306}, "protocol": "tcp", "state": "listening", "process": "mysqld"},
        ]
    }
}

# ── Alerts (rule levels 7-15) ────────────────────────────────────

ALERTS_RESPONSE = {
    "data": {
        "affected_items": [
            {
                "id": "wazuh-alert-001",
                "timestamp": "2026-02-24T10:15:30Z",
                "rule": {"id": 5710, "level": 10, "description": "sshd: Attempt to login using a denied user."},
                "agent": {"id": "001", "name": "ubuntu-web"},
                "data": {"srcip": "203.0.113.42"},
                "full_log": "Feb 24 10:15:30 ubuntu-web sshd[12345]: Failed password for invalid user admin from 203.0.113.42 port 55432 ssh2",
            },
            {
                "id": "wazuh-alert-002",
                "timestamp": "2026-02-24T10:20:15Z",
                "rule": {"id": 100200, "level": 12, "description": "Integrity checksum changed."},
                "agent": {"id": "001", "name": "ubuntu-web"},
                "data": {"file": "/etc/passwd"},
                "full_log": "Integrity checksum changed for '/etc/passwd'",
            },
            {
                "id": "wazuh-alert-003",
                "timestamp": "2026-02-24T11:00:00Z",
                "rule": {"id": 87105, "level": 15, "description": "Trojan detected in system."},
                "agent": {"id": "002", "name": "centos-app"},
                "data": {"srcip": "198.51.100.5", "file": "/tmp/malware.bin"},
                "full_log": "ClamAV: /tmp/malware.bin: Trojan.Generic FOUND",
            },
            {
                "id": "wazuh-alert-004",
                "timestamp": "2026-02-24T12:30:00Z",
                "rule": {"id": 5712, "level": 8, "description": "Multiple authentication failures."},
                "agent": {"id": "003", "name": "win-iis"},
                "data": {"srcip": "192.0.2.100"},
                "full_log": "Multiple authentication failures for user Administrator",
            },
        ],
        "total_affected_items": 4,
    }
}

# ── Vulnerability detection ──────────────────────────────────────

VULNERABILITIES_AGENT_001 = {
    "data": {
        "affected_items": [
            {
                "cve": "CVE-2023-25690",
                "name": "apache2",
                "version": "2.4.52-1ubuntu4.6",
                "severity": "Critical",
                "cvss3_score": 9.8,
            },
            {
                "cve": "CVE-2023-0286",
                "name": "openssl",
                "version": "3.0.2-0ubuntu1.10",
                "severity": "High",
                "cvss3_score": 7.4,
            },
        ],
        "total_affected_items": 2,
    }
}
