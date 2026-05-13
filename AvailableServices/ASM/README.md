# Recon Manager

A distributed reconnaissance platform for automated domain enumeration and asset discovery. Built with a microservices architecture using Docker, FastAPI, PostgreSQL/TimescaleDB, and Redis.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RECON MANAGER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │   Manager    │     │   Findings   │     │  Scheduler   │                 │
│  │  API :8000   │     │  API :8001   │     │   Service    │                 │
│  │   (FastAPI)  │     │   (FastAPI)  │     │ (APScheduler)│                 │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                 │
│         │                    │                    │                          │
│         ▼                    ▼                    ▼                          │
│  ┌────────────────────────────────────────────────────────────┐             │
│  │                      Redis (Queue)                          │             │
│  │                      Port: 6379                             │             │
│  └────────────────────────────────────────────────────────────┘             │
│         │                                        │                          │
│         ▼                                        ▼                          │
│  ┌──────────────┐                         ┌──────────────┐                  │
│  │    Engine    │◄────────────────────────│  TimescaleDB │                  │
│  │   (Worker)   │                         │  Port: 5432  │                  │
│  │              │─────────────────────────►              │                  │
│  └──────────────┘                         └──────────────┘                  │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────────────────────────┐                                   │
│  │         External APIs / Tools         │                                   │
│  │  • Shodan    • crt.sh    • DNS       │                                   │
│  │  • Censys*   • GitHub    • VirusTotal│                                   │
│  │  • Nmap (Active Scanning)            │                                   │
│  └──────────────────────────────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

* Censys requires Starter/Enterprise plan for API access
```

## 📦 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Manager API** | FastAPI (Python) | Orchestration, scope/target/job management |
| **Findings API** | FastAPI (Python) | Query interface for recon results |
| **Scheduler** | APScheduler | Cron-based automated job scheduling |
| **Engine** | Python Worker | Recon task execution and data collection |
| **Database** | TimescaleDB (PostgreSQL) | Time-series optimized storage for findings |
| **Queue** | Redis | Job queue for async task processing |
| **Dashboard** | Grafana | Attack surface visualization and monitoring |
| **Container** | Docker Compose | Service orchestration |

## 🔄 Data Flow

1. **Job Creation**: User creates a scope with targets via Manager API
2. **Job Queuing**: Job is pushed to Redis queue
3. **Job Processing**: Engine worker picks up job from queue
4. **Recon Execution**: 
   - Subdomain enumeration (crt.sh, HackerTarget, ThreatCrowd, Alienvault, BufferOver)
   - DNS resolution (A, AAAA, CNAME, MX, NS, TXT records)
   - Certificate transparency log queries
   - Shodan IP intelligence (ports, services, vulns)
   - **Active Mode**: Nmap port scanning and service detection on resolved IPs
5. **Data Storage**: Findings saved to TimescaleDB with timestamps
6. **Query Results**: Findings API provides access to stored data

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### Deployment

```bash
# Clone repository
git clone <repository-url>
cd MiniProj

# Start all services
docker-compose up -d

# Check service health
docker-compose ps
```

### Verify Deployment

```bash
# Manager API health check
curl http://localhost:8000/health

# Findings API health check
curl http://localhost:8001/health
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DB_PASSWORD=your_secure_password

# Security
SECRET_KEY=your-secret-key-change-me
```

### API Keys

Edit `engine/config.ini` to configure external API keys:

```ini
[shodan]
api_key = YOUR_SHODAN_API_KEY

[virustotal]
api_key = YOUR_VIRUSTOTAL_API_KEY

[censys]
# Requires Starter/Enterprise plan
enabled = false
pat = YOUR_CENSYS_PAT

[github]
api_token = YOUR_GITHUB_TOKEN
```

### Ports

| Service | Port | Description |
|---------|------|-------------|
| Manager API | 8000 | Orchestration API |
| Findings API | 8001 | Results query API |
| Grafana | 3000 | Dashboard UI |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Message queue |

## 📡 API Reference

### Manager API (Port 8000)

#### Scopes
```bash
# Create scope
POST /api/v1/scopes
{
  "name": "example-scope",
  "description": "Example target scope"
}

# List scopes
GET /api/v1/scopes

# Get scope
GET /api/v1/scopes/{scope_id}

# Enable/Disable scope
POST /api/v1/scopes/{scope_id}/enable
POST /api/v1/scopes/{scope_id}/disable
```

#### Targets
```bash
# Add target to scope
POST /api/v1/scopes/{scope_id}/targets
{
  "type": "domain",
  "value": "example.com"
}

# List targets
GET /api/v1/scopes/{scope_id}/targets
```

#### Jobs
```bash
# Trigger recon job
POST /api/v1/scopes/{scope_id}/jobs/trigger

# Get job status
GET /api/v1/jobs/{job_id}

# List jobs for scope
GET /api/v1/scopes/{scope_id}/jobs
```

#### Schedules
```bash
# Create schedule (cron-based)
POST /api/v1/scopes/{scope_id}/schedules
{
  "name": "daily-scan",
  "cron_expression": "0 2 * * *",
  "enabled": true
}

# List schedules
GET /api/v1/scopes/{scope_id}/schedules
```

### Findings API (Port 8001)

```bash
# Get summary of all findings
GET /api/v1/summary

# Get scope findings
GET /api/v1/scopes/{scope_id}/findings?finding_type=subdomain&page=1&page_size=50

# Get scope summary
GET /api/v1/scopes/{scope_id}/summary

# Get subdomains for scope
GET /api/v1/scopes/{scope_id}/subdomains

# Get DNS records for scope
GET /api/v1/scopes/{scope_id}/dns

# Get Shodan data for scope
GET /api/v1/scopes/{scope_id}/shodan

# Get job findings
GET /api/v1/jobs/{job_id}/findings

# Export findings as CSV
GET /api/v1/scopes/{scope_id}/export?format=csv
```

## 📁 Project Structure

```
MiniProj/
├── docker-compose.yml      # Service orchestration
├── database/
│   └── init.sql            # Database initialization
├── engine/
│   ├── Dockerfile
│   ├── config.ini          # API keys configuration
│   ├── requirements.txt
│   ├── worker.py           # Job processor
│   └── modules/
│       ├── subdomain_enum.py   # Subdomain discovery
│       ├── dns_enum.py         # DNS resolution
│       ├── cert_enum.py        # Certificate transparency
│       ├── shodan_enum.py      # Shodan integration
│       ├── nmap_enum.py        # Nmap port/service scanning
│       ├── cve_lookup.py       # CVE/NVD vulnerability lookup
│       └── utils.py            # Helper functions
├── manager/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api/
│   │   └── main.py         # Manager API endpoints
│   ├── database/
│   │   └── models.py       # SQLAlchemy models
│   ├── models/
│   │   └── schemas.py      # Pydantic schemas
│   └── services/           # Business logic
│       ├── scope_service.py
│       ├── target_service.py
│       ├── job_service.py
│       └── schedule_service.py
├── findings/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py             # Findings API endpoints
└── scheduler/
    ├── Dockerfile
    └── scheduler_service.py  # APScheduler service
```

## 🔍 Recon Modules

### Subdomain Enumeration
- **crt.sh**: Certificate transparency logs
- **HackerTarget**: DNS lookup service
- **ThreatCrowd**: Threat intelligence
- **AlienVault OTX**: Open threat exchange
- **BufferOver**: DNS enumeration
- **Censys**: Certificate search (requires paid plan)

### DNS Resolution
- A, AAAA records (IPv4/IPv6)
- CNAME records (aliases)
- MX records (mail servers)
- NS records (nameservers)
- TXT records (SPF, DKIM, etc.)
- SOA records (authority)

### Shodan Integration
- Open ports and services
- Software versions and banners
- Known vulnerabilities (CVEs)
- ASN and organization info
- Reverse DNS hostnames

### Nmap Active Scanning (Active Mode)
Active reconnaissance using Nmap for direct host scanning:

| Scan Type | Arguments | Description |
|-----------|-----------|-------------|
| `fast` | `-sV -F` | Quick scan of top 100 ports with version detection |
| `default` | `-sV -sC` | Version detection + default NSE scripts |
| `full` | `-sV -sC -p-` | All 65535 ports with version detection and scripts |

**Features:**
- Open port detection (TCP)
- Service identification (HTTP, SSH, FTP, etc.)
- Version detection (product name and version)
- Banner grabbing
- OS detection
- CPE identifiers for vulnerability mapping

**Configuration** (`engine/config.ini`):
```ini
[nmap]
scan_type = default
ports = 
threads = 5
timeout = 300
check_cves = true
```

**Usage**: Trigger active scans by setting `mode=active` when creating jobs.

**Note**: Active scanning requires Nmap to be installed in the Docker container.

### CVE Lookup (NVD Integration)
Automatic vulnerability detection for discovered services using the National Vulnerability Database (NVD) API.

**Features:**
- Automatic CVE lookup after Nmap scans
- CPE-based matching for accurate results
- Keyword fallback for services without CPE
- CVSS severity scoring (v2, v3.0, v3.1)
- Rate limiting to respect NVD API limits
- Support for multiple hosts/IPs in parallel

**Configuration** (`engine/config.ini`):
```ini
[nvd]
# Get your API key from https://nvd.nist.gov/developers/request-an-api-key
# Without API key: 5 requests per 30 seconds
# With API key: 50 requests per 30 seconds
api_key = YOUR_NVD_API_KEY
max_results = 20
```

**CVE Result Structure:**
```json
{
  "cve_id": "CVE-2021-44228",
  "severity": "CRITICAL",
  "cvss_score": 10.0,
  "cvss_version": "3.1",
  "description": "Apache Log4j2 vulnerability...",
  "published_date": "2021-12-10",
  "references": ["https://nvd.nist.gov/..."]
}
```

**Severity Levels:**
| Level | CVSS Score | Icon |
|-------|------------|------|
| CRITICAL | 9.0 - 10.0 | 🔴 |
| HIGH | 7.0 - 8.9 | 🟠 |
| MEDIUM | 4.0 - 6.9 | 🟡 |
| LOW | 0.1 - 3.9 | 🟢 |

## 🗄️ Database Schema

### Key Tables
- **scopes**: Target scope definitions
- **targets**: Individual targets (domains, IPs, CIDRs)
- **jobs**: Recon job tracking
- **schedules**: Cron-based schedules
- **recon_findings**: Time-series findings (TimescaleDB hypertable)

### Finding Types
- `subdomain`: Discovered subdomains
- `dns_a`, `dns_aaaa`, `dns_cname`, etc.: DNS records
- `shodan_port`: Open ports from Shodan
- `shodan_service`: Running services
- `shodan_vuln`: Known vulnerabilities
- `shodan_hostname`: Reverse DNS names
- `nmap_port`: Open ports from Nmap active scan
- `nmap_service`: Service details with version info
- `nmap_os`: Detected operating system
- `cve`: CVE vulnerabilities from NVD lookup
- `certificate`: SSL/TLS certificates

## 🛠️ Development

### Rebuild Services
```bash
# Rebuild specific service
docker-compose build engine
docker-compose up -d engine

# Rebuild all services
docker-compose build
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f engine
```

### Database Access
```bash
docker exec -it recon_database psql -U recon -d recon_manager
```

### Common Queries
```sql
-- Count findings by type
SELECT finding_type, COUNT(*) FROM recon_findings GROUP BY finding_type;

-- Recent subdomains
SELECT value, source, time FROM recon_findings 
WHERE finding_type = 'subdomain' 
ORDER BY time DESC LIMIT 20;

-- Shodan ports for a scope
SELECT value, extra_data->>'port' as port, extra_data->>'service' as service
FROM recon_findings 
WHERE scope_id = 'your-scope-id' AND finding_type = 'shodan_port';
```

## 📋 Example Workflow

```bash
# 1. Create a scope
curl -X POST http://localhost:8000/api/v1/scopes \
  -H "Content-Type: application/json" \
  -d '{"name": "acme-corp", "description": "ACME Corporation recon"}'

# 2. Add target domain (use scope_id from response)
curl -X POST http://localhost:8000/api/v1/scopes/{scope_id}/targets \
  -H "Content-Type: application/json" \
  -d '{"type": "domain", "value": "acme.com"}'

# 3. Trigger recon job
curl -X POST http://localhost:8000/api/v1/scopes/{scope_id}/jobs/trigger

# 4. Check job status
curl http://localhost:8000/api/v1/jobs/{job_id}

# 5. Query findings
curl http://localhost:8001/api/v1/scopes/{scope_id}/subdomains

# 6. Schedule daily scans
curl -X POST http://localhost:8000/api/v1/scopes/{scope_id}/schedules \
  -H "Content-Type: application/json" \
  -d '{"name": "daily", "cron_expression": "0 2 * * *", "enabled": true}'
```

## ⚠️ Notes

- **Censys API**: Requires Starter or Enterprise plan. Free tier can only access via web UI.
- **Rate Limits**: External APIs have rate limits. Consider adding delays for large scopes.
- **Resource Usage**: Shodan queries consume API credits.

## 📊 Grafana Dashboard

Access the Attack Surface Dashboard at **http://localhost:3000** (default credentials: `admin` / `admin`).

### Dashboard Features

| Panel | Description |
|-------|-------------|
| 🌐 **Subdomains** | Count of unique discovered subdomains |
| 🔌 **Open Ports** | Count of unique open ports found |
| 🚨 **CVEs Found** | Total CVE matches for detected services |
| ⚠️ **Critical/High CVEs** | Count of severe vulnerabilities |
| 🔧 **Services** | Unique services discovered |
| 📊 **Total Findings** | Overall findings count |

### Tables

| Table | Description |
|-------|-------------|
| **All Targets** | List of all configured targets with status |
| **Launched Targets** | Recent job executions with status and duration |
| **Scheduled Targets** | Upcoming scheduled scans with cron expressions |
| **CVE Details** | Full CVE list with severity, CVSS scores, and affected services |
| **Open Ports & Services** | Port scan results with service detection |
| **Discovered Subdomains** | Subdomain enumeration results |
| **Attack Surface Summary** | Per-target breakdown of findings |

### Visualizations

- **CVE Severity Distribution** - Pie chart showing Critical/High/Medium/Low breakdown
- **Findings by Type** - Donut chart of finding categories
- **Top Targets by Findings** - Bar chart ranking targets by discovery count

### Target Filtering

Use the **Target** dropdown at the top to filter all panels by specific domain:
- `All` - Show data across all targets
- `hackerone.com`, `bugcrowd.com`, `tesla.com`, etc. - Filter to specific target

### Dashboard Provisioning

The dashboard is auto-provisioned from:
```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── datasources.yml    # PostgreSQL connection
│   └── dashboards/
│       └── dashboards.yml     # Dashboard provider config
└── dashboards/
    └── attack-surface.json    # Dashboard definition
```


