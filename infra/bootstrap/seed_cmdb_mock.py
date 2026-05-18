"""Populate CMDB with realistic finance-sector mock data for simulation.

What it creates:
  - ~60 assets spanning core banking, ATMs, branch infrastructure, workstations,
    domain controllers, mail servers, DBs, network gear, payment gateways,
    SWIFT terminals, and a few cloud workloads.
  - Patches the company profile with a realistic North-African bank shape if
    one isn't already populated.

Idempotent: skips assets whose hostname already exists.

Usage (from a host that can reach the auth + cmdb services):
    python infra/bootstrap/seed_cmdb_mock.py

Env vars:
    AUTH_URL                 (default http://auth:8000)
    CMDB_URL                 (default http://cmdb:8007)
    BOOTSTRAP_ADMIN_USERNAME (default admin)
    BOOTSTRAP_ADMIN_PASSWORD (default changeme)

Inside the docker network you can run it with:
    docker run --rm --network tip-platform_default \
      -e AUTH_URL=http://auth:8000 -e CMDB_URL=http://cmdb:8007 \
      -e BOOTSTRAP_ADMIN_USERNAME=admin -e BOOTSTRAP_ADMIN_PASSWORD=<pass> \
      -v $(pwd)/infra/bootstrap/seed_cmdb_mock.py:/seed.py \
      python:3.12-slim sh -c "pip install httpx && python /seed.py"
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx


AUTH_URL = os.environ.get("AUTH_URL", "http://auth:8000")
CMDB_URL = os.environ.get("CMDB_URL", "http://cmdb:8007")
ADMIN_USER = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "changeme")


# ─────────────────────────────────────────────────────────────────────────────
# Asset catalog. Realistic for a 500–1000-employee North-African retail bank.
# ─────────────────────────────────────────────────────────────────────────────

ASSETS: list[dict[str, Any]] = [
    # ── Core banking ────────────────────────────────────────────────────────
    {
        "hostname": "core-t24-prod-01",
        "ip": "10.10.1.10",
        "os": "Red Hat Enterprise Linux 8.10",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Core Banking Ops",
        "location": "DC1 — Casablanca primary",
        "software": {"app": "Temenos T24", "version": "R22", "db": "Oracle 19c"},
        "tags": ["crown-jewel", "core-banking", "t24", "pci-dss"],
    },
    {
        "hostname": "core-t24-prod-02",
        "ip": "10.10.1.11",
        "os": "Red Hat Enterprise Linux 8.10",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Core Banking Ops",
        "location": "DC1 — Casablanca primary",
        "software": {"app": "Temenos T24", "version": "R22", "db": "Oracle 19c"},
        "tags": ["crown-jewel", "core-banking", "t24", "pci-dss", "hot-standby"],
    },
    {
        "hostname": "core-t24-dr-01",
        "ip": "10.20.1.10",
        "os": "Red Hat Enterprise Linux 8.10",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Core Banking Ops",
        "location": "DC2 — Rabat DR site",
        "software": {"app": "Temenos T24", "version": "R22", "db": "Oracle 19c"},
        "tags": ["crown-jewel", "core-banking", "t24", "dr"],
    },
    {
        "hostname": "swift-alliance-gw-01",
        "ip": "10.10.2.20",
        "os": "Red Hat Enterprise Linux 7.9",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Payments Ops",
        "location": "DC1 — Casablanca primary",
        "software": {"app": "SWIFT Alliance Access", "version": "7.7"},
        "tags": ["crown-jewel", "swift", "payments", "isolated-vlan"],
    },
    {
        "hostname": "swift-alliance-gw-02",
        "ip": "10.10.2.21",
        "os": "Red Hat Enterprise Linux 7.9",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Payments Ops",
        "location": "DC1 — Casablanca primary",
        "software": {"app": "SWIFT Alliance Access", "version": "7.7"},
        "tags": ["crown-jewel", "swift", "payments", "isolated-vlan", "ha"],
    },
    {
        "hostname": "card-mgmt-prod-01",
        "ip": "10.10.3.10",
        "os": "Microsoft Windows Server 2019",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Cards Team",
        "location": "DC1",
        "software": {"app": "Way4 Card Management", "version": "23.10"},
        "tags": ["crown-jewel", "cards", "pci-dss"],
    },
    {
        "hostname": "card-auth-hsm-01",
        "ip": "10.10.3.50",
        "os": "Appliance firmware",
        "device_type": "hsm",
        "criticality": "critical",
        "owner": "Cards Team",
        "location": "DC1 — secure cage",
        "software": {"vendor": "Thales", "model": "payShield 10K", "firmware": "1.6"},
        "tags": ["crown-jewel", "hsm", "pci-dss", "fips-140-2"],
    },
    {
        "hostname": "card-auth-hsm-02",
        "ip": "10.20.3.50",
        "os": "Appliance firmware",
        "device_type": "hsm",
        "criticality": "critical",
        "owner": "Cards Team",
        "location": "DC2 — secure cage",
        "software": {"vendor": "Thales", "model": "payShield 10K", "firmware": "1.6"},
        "tags": ["crown-jewel", "hsm", "pci-dss", "fips-140-2", "dr"],
    },

    # ── Online banking ──────────────────────────────────────────────────────
    {
        "hostname": "ib-web-prod-01",
        "ip": "10.10.5.10",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "Digital Banking",
        "location": "DC1 — DMZ",
        "software": {"app": "Internet Banking", "stack": "Java 17 + Spring Boot"},
        "tags": ["internet-facing", "online-banking"],
    },
    {
        "hostname": "ib-web-prod-02",
        "ip": "10.10.5.11",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "Digital Banking",
        "location": "DC1 — DMZ",
        "software": {"app": "Internet Banking", "stack": "Java 17 + Spring Boot"},
        "tags": ["internet-facing", "online-banking", "ha"],
    },
    {
        "hostname": "ib-api-prod-01",
        "ip": "10.10.5.20",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "Digital Banking",
        "location": "DC1",
        "software": {"app": "Open Banking API Gateway", "vendor": "Kong", "version": "3.4"},
        "tags": ["online-banking", "psd2", "api-gateway"],
    },
    {
        "hostname": "mobile-api-prod-01",
        "ip": "10.10.5.30",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "Mobile Banking",
        "location": "DC1",
        "software": {"app": "Mobile Banking API", "stack": "Node 20"},
        "tags": ["online-banking", "mobile"],
    },
    {
        "hostname": "waf-prod-01",
        "ip": "10.10.5.1",
        "os": "Appliance firmware",
        "device_type": "appliance",
        "criticality": "high",
        "owner": "Network Security",
        "location": "DC1 — Edge",
        "software": {"vendor": "F5", "model": "BIG-IP ASM i4800", "version": "17.1"},
        "tags": ["edge", "waf", "internet-facing"],
    },

    # ── ATM network ─────────────────────────────────────────────────────────
    {
        "hostname": "atm-switch-prod-01",
        "ip": "10.10.4.10",
        "os": "Red Hat Enterprise Linux 8.10",
        "device_type": "server",
        "criticality": "critical",
        "owner": "ATM Ops",
        "location": "DC1",
        "software": {"app": "Postilion ATM Switch", "version": "9.0"},
        "tags": ["atm", "payments", "pci-dss"],
    },
    {
        "hostname": "atm-monitor-prod-01",
        "ip": "10.10.4.20",
        "os": "Microsoft Windows Server 2019",
        "device_type": "server",
        "criticality": "medium",
        "owner": "ATM Ops",
        "location": "DC1",
        "software": {"app": "ATM Monitoring Console", "vendor": "Diebold Nixdorf"},
        "tags": ["atm", "monitoring"],
    },
    {
        "hostname": "atm-cbk-001-cas",
        "ip": "172.16.40.11",
        "os": "Microsoft Windows 10 IoT LTSC",
        "device_type": "atm",
        "criticality": "high",
        "owner": "ATM Ops",
        "location": "Branch — Casablanca Centre Ville",
        "software": {"vendor": "Diebold Nixdorf", "model": "CS5500"},
        "tags": ["atm", "endpoint", "branch"],
    },
    {
        "hostname": "atm-cbk-014-rab",
        "ip": "172.16.40.14",
        "os": "Microsoft Windows 10 IoT LTSC",
        "device_type": "atm",
        "criticality": "high",
        "owner": "ATM Ops",
        "location": "Branch — Rabat Agdal",
        "software": {"vendor": "NCR", "model": "SelfServ 84"},
        "tags": ["atm", "endpoint", "branch"],
    },
    {
        "hostname": "atm-cbk-027-tng",
        "ip": "172.16.40.27",
        "os": "Microsoft Windows 10 IoT LTSC",
        "device_type": "atm",
        "criticality": "high",
        "owner": "ATM Ops",
        "location": "Branch — Tangier Marina",
        "software": {"vendor": "NCR", "model": "SelfServ 84"},
        "tags": ["atm", "endpoint", "branch"],
    },

    # ── Identity & infrastructure ───────────────────────────────────────────
    {
        "hostname": "dc-prod-01.bma.local",
        "ip": "10.10.0.10",
        "os": "Microsoft Windows Server 2022",
        "device_type": "domain-controller",
        "criticality": "critical",
        "owner": "Platform Eng",
        "location": "DC1",
        "software": {"app": "Active Directory Domain Services"},
        "tags": ["crown-jewel", "identity", "ad"],
    },
    {
        "hostname": "dc-prod-02.bma.local",
        "ip": "10.10.0.11",
        "os": "Microsoft Windows Server 2022",
        "device_type": "domain-controller",
        "criticality": "critical",
        "owner": "Platform Eng",
        "location": "DC2",
        "software": {"app": "Active Directory Domain Services"},
        "tags": ["crown-jewel", "identity", "ad", "dr"],
    },
    {
        "hostname": "adfs-prod-01",
        "ip": "10.10.0.20",
        "os": "Microsoft Windows Server 2022",
        "device_type": "server",
        "criticality": "high",
        "owner": "Platform Eng",
        "location": "DC1",
        "software": {"app": "Active Directory Federation Services"},
        "tags": ["identity", "sso", "adfs"],
    },
    {
        "hostname": "pam-cyberark-01",
        "ip": "10.10.0.40",
        "os": "Red Hat Enterprise Linux 9",
        "device_type": "server",
        "criticality": "critical",
        "owner": "Security Eng",
        "location": "DC1",
        "software": {"app": "CyberArk PAM", "version": "13.2"},
        "tags": ["crown-jewel", "pam", "privileged-access"],
    },

    # ── Mail & collaboration ────────────────────────────────────────────────
    {
        "hostname": "exchange-prod-01",
        "ip": "10.10.6.10",
        "os": "Microsoft Windows Server 2022",
        "device_type": "server",
        "criticality": "high",
        "owner": "Messaging Team",
        "location": "DC1",
        "software": {"app": "Microsoft Exchange Server 2019 CU14"},
        "tags": ["mail", "exchange"],
    },
    {
        "hostname": "mailgw-proofpoint-01",
        "ip": "10.10.6.5",
        "os": "Appliance firmware",
        "device_type": "appliance",
        "criticality": "high",
        "owner": "Security Eng",
        "location": "DC1 — Edge",
        "software": {"vendor": "Proofpoint", "model": "Targeted Attack Protection"},
        "tags": ["mail-gateway", "anti-phishing"],
    },

    # ── Databases (non-T24) ─────────────────────────────────────────────────
    {
        "hostname": "db-oracle-prod-01",
        "ip": "10.10.7.10",
        "os": "Oracle Linux 8",
        "device_type": "database",
        "criticality": "critical",
        "owner": "DB Team",
        "location": "DC1",
        "software": {"engine": "Oracle Database 19c", "patch": "19.22"},
        "tags": ["crown-jewel", "database"],
    },
    {
        "hostname": "db-postgres-prod-01",
        "ip": "10.10.7.20",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "database",
        "criticality": "high",
        "owner": "DB Team",
        "location": "DC1",
        "software": {"engine": "PostgreSQL 15.6"},
        "tags": ["database"],
    },
    {
        "hostname": "db-mssql-crm-01",
        "ip": "10.10.7.30",
        "os": "Microsoft Windows Server 2019",
        "device_type": "database",
        "criticality": "high",
        "owner": "DB Team",
        "location": "DC1",
        "software": {"engine": "Microsoft SQL Server 2019", "app": "Salesforce on-prem CRM"},
        "tags": ["database", "crm"],
    },

    # ── SOC / Security ──────────────────────────────────────────────────────
    {
        "hostname": "siem-wazuh-mgr-01",
        "ip": "10.10.8.10",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "SOC",
        "location": "DC1",
        "software": {"app": "Wazuh Manager", "version": "4.7"},
        "tags": ["soc", "siem"],
    },
    {
        "hostname": "siem-elastic-01",
        "ip": "10.10.8.11",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "SOC",
        "location": "DC1",
        "software": {"app": "Elasticsearch", "version": "8.13"},
        "tags": ["soc", "siem", "log-storage"],
    },
    {
        "hostname": "edr-crowdstrike-mgr",
        "ip": "10.10.8.20",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "high",
        "owner": "SOC",
        "location": "DC1",
        "software": {"app": "CrowdStrike Falcon Console (mirror)"},
        "tags": ["soc", "edr"],
    },

    # ── Network & firewalls ─────────────────────────────────────────────────
    {
        "hostname": "fw-perimeter-fortigate-01",
        "ip": "10.10.0.1",
        "os": "FortiOS 7.4",
        "device_type": "firewall",
        "criticality": "critical",
        "owner": "Network Security",
        "location": "DC1 — Edge",
        "software": {"vendor": "Fortinet", "model": "FortiGate 1500D"},
        "tags": ["edge", "firewall", "perimeter"],
    },
    {
        "hostname": "fw-perimeter-fortigate-02",
        "ip": "10.10.0.2",
        "os": "FortiOS 7.4",
        "device_type": "firewall",
        "criticality": "critical",
        "owner": "Network Security",
        "location": "DC1 — Edge",
        "software": {"vendor": "Fortinet", "model": "FortiGate 1500D"},
        "tags": ["edge", "firewall", "perimeter", "ha"],
    },
    {
        "hostname": "fw-internal-paloalto-01",
        "ip": "10.10.0.3",
        "os": "PAN-OS 11.1",
        "device_type": "firewall",
        "criticality": "critical",
        "owner": "Network Security",
        "location": "DC1 — Core",
        "software": {"vendor": "Palo Alto", "model": "PA-5410"},
        "tags": ["firewall", "internal-segmentation"],
    },
    {
        "hostname": "vpn-globalprotect-01",
        "ip": "10.10.0.4",
        "os": "PAN-OS 11.1",
        "device_type": "vpn",
        "criticality": "high",
        "owner": "Network Security",
        "location": "DC1 — Edge",
        "software": {"vendor": "Palo Alto", "model": "GlobalProtect"},
        "tags": ["vpn", "remote-access", "internet-facing"],
    },
    {
        "hostname": "switch-core-nexus-01",
        "ip": "10.10.0.5",
        "os": "NX-OS 10.3",
        "device_type": "switch",
        "criticality": "critical",
        "owner": "Network Eng",
        "location": "DC1 — Core",
        "software": {"vendor": "Cisco", "model": "Nexus 9504"},
        "tags": ["network", "core"],
    },

    # ── Cloud workloads ─────────────────────────────────────────────────────
    {
        "hostname": "aws-prod-vpc-bastion-01",
        "ip": "13.36.0.42",
        "os": "Amazon Linux 2023",
        "device_type": "server",
        "criticality": "medium",
        "owner": "Cloud Eng",
        "location": "AWS eu-west-3 (Paris)",
        "software": {"app": "Bastion / Session Manager"},
        "tags": ["cloud", "aws", "bastion"],
    },
    {
        "hostname": "azure-prod-app-01",
        "ip": "40.74.0.10",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "medium",
        "owner": "Cloud Eng",
        "location": "Azure West Europe",
        "software": {"app": "Marketing CMS", "stack": "Strapi"},
        "tags": ["cloud", "azure", "low-trust"],
    },

    # ── Workstations ────────────────────────────────────────────────────────
    {
        "hostname": "ws-cto-ahmed",
        "ip": "10.30.5.21",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "high",
        "owner": "Ahmed El Mahjoub (CTO)",
        "location": "HQ — Floor 12",
        "software": {"office": "Microsoft 365 Apps"},
        "tags": ["workstation", "executive"],
    },
    {
        "hostname": "ws-ciso-leila",
        "ip": "10.30.5.22",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "high",
        "owner": "Leila Bensouda (CISO)",
        "location": "HQ — Floor 12",
        "software": {"office": "Microsoft 365 Apps"},
        "tags": ["workstation", "executive"],
    },
    {
        "hostname": "ws-soc-l1-01",
        "ip": "10.30.10.11",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "medium",
        "owner": "SOC L1 — Shift A",
        "location": "HQ — SOC room",
        "software": {"office": "Microsoft 365 Apps", "browser": "Edge / Firefox"},
        "tags": ["workstation", "soc"],
    },
    {
        "hostname": "ws-soc-l1-02",
        "ip": "10.30.10.12",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "medium",
        "owner": "SOC L1 — Shift B",
        "location": "HQ — SOC room",
        "software": {"office": "Microsoft 365 Apps"},
        "tags": ["workstation", "soc"],
    },
    {
        "hostname": "ws-soc-l2-yassine",
        "ip": "10.30.10.13",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "medium",
        "owner": "Yassine Bouazza (SOC L2)",
        "location": "HQ — SOC room",
        "software": {"office": "Microsoft 365 Apps", "browser": "Edge"},
        "tags": ["workstation", "soc"],
    },
    {
        "hostname": "ws-ti-amira",
        "ip": "10.30.10.14",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "medium",
        "owner": "Amira Tazi (TI Analyst)",
        "location": "HQ — SOC room",
        "software": {"office": "Microsoft 365 Apps"},
        "tags": ["workstation", "ti"],
    },
    {
        "hostname": "ws-finance-001",
        "ip": "10.30.20.5",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "medium",
        "owner": "Finance / Treasury",
        "location": "HQ — Floor 8",
        "software": {"office": "Microsoft 365 Apps"},
        "tags": ["workstation", "treasury"],
    },
    {
        "hostname": "ws-treasury-001",
        "ip": "10.30.20.6",
        "os": "Microsoft Windows 11 Enterprise",
        "device_type": "workstation",
        "criticality": "high",
        "owner": "Treasury Dealer",
        "location": "HQ — Floor 8 dealing room",
        "software": {"office": "Microsoft 365 Apps", "app": "Bloomberg Terminal"},
        "tags": ["workstation", "dealing-room", "high-value"],
    },

    # ── Branch infra (representative) ───────────────────────────────────────
    {
        "hostname": "branch-cas-router-01",
        "ip": "172.16.40.1",
        "os": "Cisco IOS XE 17.9",
        "device_type": "router",
        "criticality": "high",
        "owner": "Network Eng",
        "location": "Branch — Casablanca Centre Ville",
        "software": {"vendor": "Cisco", "model": "ISR 4451"},
        "tags": ["network", "branch", "wan"],
    },
    {
        "hostname": "branch-rab-router-01",
        "ip": "172.16.50.1",
        "os": "Cisco IOS XE 17.9",
        "device_type": "router",
        "criticality": "high",
        "owner": "Network Eng",
        "location": "Branch — Rabat Agdal",
        "software": {"vendor": "Cisco", "model": "ISR 4451"},
        "tags": ["network", "branch", "wan"],
    },
    {
        "hostname": "branch-tng-router-01",
        "ip": "172.16.60.1",
        "os": "Cisco IOS XE 17.9",
        "device_type": "router",
        "criticality": "high",
        "owner": "Network Eng",
        "location": "Branch — Tangier Marina",
        "software": {"vendor": "Cisco", "model": "ISR 4451"},
        "tags": ["network", "branch", "wan"],
    },

    # ── Misc / web frontends ────────────────────────────────────────────────
    {
        "hostname": "www-corporate-prod",
        "ip": "196.200.0.10",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "low",
        "owner": "Marketing",
        "location": "DC1 — DMZ",
        "software": {"app": "Corporate website", "stack": "WordPress 6.5"},
        "tags": ["internet-facing", "marketing", "low-trust"],
    },
    {
        "hostname": "careers-portal-prod",
        "ip": "196.200.0.11",
        "os": "Ubuntu Server 22.04 LTS",
        "device_type": "server",
        "criticality": "low",
        "owner": "HR",
        "location": "DC1 — DMZ",
        "software": {"app": "Careers portal", "stack": "Drupal 10"},
        "tags": ["internet-facing", "hr"],
    },
    {
        "hostname": "jump-prod-01",
        "ip": "10.10.0.50",
        "os": "Microsoft Windows Server 2022",
        "device_type": "server",
        "criticality": "high",
        "owner": "Platform Eng",
        "location": "DC1",
        "software": {"app": "Bastion / Jump host"},
        "tags": ["bastion", "privileged-access"],
    },

    # ── Backup / DR ─────────────────────────────────────────────────────────
    {
        "hostname": "backup-veeam-01",
        "ip": "10.10.9.10",
        "os": "Microsoft Windows Server 2022",
        "device_type": "server",
        "criticality": "high",
        "owner": "Backup Ops",
        "location": "DC1",
        "software": {"app": "Veeam Backup & Replication", "version": "12.1"},
        "tags": ["backup", "dr"],
    },
    {
        "hostname": "backup-veeam-02",
        "ip": "10.20.9.10",
        "os": "Microsoft Windows Server 2022",
        "device_type": "server",
        "criticality": "high",
        "owner": "Backup Ops",
        "location": "DC2",
        "software": {"app": "Veeam Backup & Replication", "version": "12.1"},
        "tags": ["backup", "dr", "secondary"],
    },
]


COMPANY_PROFILE: dict[str, Any] = {
    "identity": {
        "name": "Banque Maghreb Atlantique",
        "sector": "finance",
        "sub_sector": "retail-banking",
        "employee_count_range": "500-1000",
        "hq_country": "MA",
        "countries_of_operation": ["MA", "TN", "SN", "CI"],
        "public_domains": ["bma-bank.ma", "bma-bank.com", "bma-online.ma", "bma-careers.ma"],
        "public_ip_ranges": ["196.200.0.0/22", "196.205.16.0/24"],
        "asn_numbers": ["AS37705", "AS37054"],
        "language": "fr",
    },
    "technology": {
        "operating_systems": [
            "Red Hat Enterprise Linux 8.10",
            "Red Hat Enterprise Linux 7.9",
            "Microsoft Windows Server 2022",
            "Microsoft Windows Server 2019",
            "Ubuntu Server 22.04 LTS",
            "Oracle Linux 8",
        ],
        "endpoint_os": [
            "Microsoft Windows 11 Enterprise",
            "Microsoft Windows 10 Enterprise",
            "Microsoft Windows 10 IoT LTSC",
        ],
        "software": [
            "Temenos T24 R22",
            "SWIFT Alliance Access 7.7",
            "Way4 Card Management",
            "Oracle Database 19c",
            "Microsoft SQL Server 2019",
            "PostgreSQL 15",
            "Microsoft Exchange Server 2019",
            "Microsoft 365 Apps",
            "Veeam Backup & Replication 12",
            "CyberArk PAM 13",
            "Wazuh 4.7",
            "Postilion ATM Switch 9",
        ],
        "network_devices": ["Fortinet FortiGate 1500D", "Palo Alto PA-5410", "Cisco Nexus 9504", "Cisco ISR 4451", "F5 BIG-IP ASM"],
        "cloud_providers": ["AWS", "Azure"],
        "identity_providers": ["Active Directory", "ADFS", "Microsoft Entra ID"],
        "remote_access": ["Palo Alto GlobalProtect VPN", "CyberArk PSM"],
        "security_tools": ["Wazuh", "CrowdStrike Falcon", "Proofpoint TAP", "Thales payShield 10K HSM"],
        "industrial_ot": False,
    },
    "exposure": {
        "internet_facing_services": [
            "Internet banking (web + mobile API)",
            "Open banking PSD2 gateway",
            "Corporate website",
            "Careers portal",
            "GlobalProtect VPN",
            "Mail (Exchange via Proofpoint gateway)",
        ],
        "mobile_workforce": True,
        "third_party_access": True,
        "supply_chain_vendors": [
            "Temenos",
            "SWIFT",
            "Diebold Nixdorf",
            "NCR",
            "Microsoft",
            "Fortinet",
            "Palo Alto Networks",
            "CrowdStrike",
            "Proofpoint",
            "Thales",
        ],
        "critical_data_types": ["pii", "cardholder-data", "transaction-data", "credentials"],
    },
    "compliance": {
        "regulatory_frameworks": ["BAM Directive 2/G/2020", "PCI DSS v4.0", "GDPR-equivalent (Morocco Law 09-08)", "SWIFT CSP"],
        "certifications": ["ISO/IEC 27001:2022", "PCI DSS v4.0 — Level 1"],
        "data_residency_requirements": ["MA", "EU"],
    },
    "geopolitical": {
        "geopolitical_regions": ["North Africa", "West Africa", "Mediterranean basin"],
        "conflict_adjacent": False,
        "notable_partnerships": ["BCEAO settlement", "SWIFT", "Mastercard", "Visa"],
        "sanctions_exposure": False,
    },
    "risk": {
        "risk_appetite": "low",
        "crown_jewels": [
            "Temenos T24 core banking",
            "SWIFT Alliance gateway",
            "Way4 card management",
            "Thales HSM cluster",
            "Active Directory forest",
            "CyberArk PAM vault",
        ],
        "previous_incidents": [
            "2023-Q2: phishing campaign targeting executives (contained)",
            "2024-Q1: ATM jackpotting attempt at Casablanca Centre Ville (blocked by Postilion)",
        ],
        "threat_concerns": [
            "Ransomware against ATM switch / SWIFT terminal",
            "Supply-chain compromise of Temenos / SWIFT updates",
            "Credential theft via phishing → SWIFT operator account",
            "PSD2 API abuse / token replay",
            "Card data exfiltration via PoS / e-commerce skimmer",
        ],
    },
}


async def _login(client: httpx.AsyncClient) -> str:
    print(f"[cmdb-mock] login as {ADMIN_USER}")
    r = await client.post(
        f"{AUTH_URL}/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def _existing_hostnames(client: httpx.AsyncClient, token: str) -> set[str]:
    r = await client.get(
        f"{CMDB_URL}/assets",
        params={"limit": 500},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"[cmdb-mock] WARN could not list existing assets: HTTP {r.status_code}")
        return set()
    payload = r.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    return {a.get("hostname") for a in (items or []) if a.get("hostname")}


async def _create_asset(client: httpx.AsyncClient, token: str, asset: dict[str, Any]) -> bool:
    r = await client.post(
        f"{CMDB_URL}/assets",
        json=asset,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code in (200, 201):
        return True
    print(f"[cmdb-mock] FAIL {asset['hostname']} -> HTTP {r.status_code}: {r.text[:200]}")
    return False


async def _maybe_patch_profile(client: httpx.AsyncClient, token: str) -> None:
    r = await client.get(
        f"{CMDB_URL}/profile/latest",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    profile_present = False
    if r.status_code == 200:
        payload = r.json()
        ident = (payload or {}).get("identity") or {}
        # Heuristic: if identity has BMA-ish fields populated already, skip overwrite
        if ident.get("name") and ident.get("hq_country"):
            profile_present = True
    if profile_present:
        print("[cmdb-mock] company profile already populated; not overwriting")
        return

    r = await client.patch(
        f"{CMDB_URL}/profile",
        json=COMPANY_PROFILE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"[cmdb-mock] company profile seeded (version={r.json().get('version')})")
    else:
        print(f"[cmdb-mock] WARN profile patch HTTP {r.status_code}: {r.text[:200]}")


async def main() -> int:
    async with httpx.AsyncClient() as client:
        try:
            token = await _login(client)
        except httpx.HTTPStatusError as exc:
            print(f"[cmdb-mock] login failed: {exc}")
            return 1

        await _maybe_patch_profile(client, token)

        existing = await _existing_hostnames(client, token)
        print(f"[cmdb-mock] {len(existing)} assets already in CMDB; skipping matching hostnames")

        created = 0
        skipped = 0
        failed = 0
        for asset in ASSETS:
            if asset["hostname"] in existing:
                skipped += 1
                continue
            if await _create_asset(client, token, asset):
                created += 1
            else:
                failed += 1
        print(f"[cmdb-mock] done: created={created} skipped={skipped} failed={failed} total_in_catalog={len(ASSETS)}")
        return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
