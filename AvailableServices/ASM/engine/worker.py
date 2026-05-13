"""
Reconnaissance Engine Worker
Consumes jobs from Redis queue and executes recon tasks
"""
import os
import json
import redis
import time
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict, Any, List

# Import recon modules
from modules.subdomain_enum import SubdomainEnumerator
from modules.dns_enum import DNSEnumerator
from modules.cert_enum import CertificateEnumerator
from modules.shodan_enum import ShodanEnumerator
from modules.nmap_enum import NmapEnumerator
from modules.cve_lookup import CVELookup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReconWorker:
    """Worker that processes reconnaissance jobs"""
    
    def __init__(self):
        # Redis connection
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            decode_responses=True
        )
        
        # Database connection - use DATABASE_URL or construct from parts
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            db_user = os.getenv('POSTGRES_USER', 'recon')
            db_pass = os.getenv('POSTGRES_PASSWORD', 'changeme')
            db_host = os.getenv('POSTGRES_HOST', 'database')
            db_name = os.getenv('POSTGRES_DB', 'recon_manager')
            self.db_url = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
        
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Queue name
        self.job_queue = 'recon_jobs'
        
        db_host = os.getenv('POSTGRES_HOST', 'database')
        logger.info(f"Worker initialized - Redis: {self.redis_host}:{self.redis_port}, DB: {db_host}")
    
    def update_job_status(self, job_id: str, status: str, error: str = None, findings_count: int = 0):
        """Update job status in database"""
        logger.info(f"Job {job_id} status: {status}" + (f" - {error}" if error else ""))
        try:
            from sqlalchemy import text
            # PostgreSQL enum is uppercase
            status_upper = status.upper()
            with self.engine.connect() as conn:
                if status == 'running':
                    query = text("""
                        UPDATE jobs 
                        SET status = CAST(:status AS jobstatusenum), started_at = NOW()
                        WHERE id = :job_id
                    """)
                    conn.execute(query, {"job_id": job_id, "status": status_upper})
                elif status == 'completed':
                    query = text("""
                        UPDATE jobs 
                        SET status = CAST(:status AS jobstatusenum), completed_at = NOW(), findings_count = :findings_count
                        WHERE id = :job_id
                    """)
                    conn.execute(query, {"job_id": job_id, "status": status_upper, "findings_count": findings_count})
                elif status == 'failed':
                    query = text("""
                        UPDATE jobs 
                        SET status = CAST(:status AS jobstatusenum), completed_at = NOW()
                        WHERE id = :job_id
                    """)
                    conn.execute(query, {"job_id": job_id, "status": status_upper})
                else:
                    query = text("""
                        UPDATE jobs 
                        SET status = CAST(:status AS jobstatusenum)
                        WHERE id = :job_id
                    """)
                    conn.execute(query, {"job_id": job_id, "status": status_upper})
                conn.commit()
                logger.info(f"Updated job {job_id} status to {status} in database")
        except Exception as e:
            logger.error(f"Failed to update job status in database: {e}")
    
    def get_scope_config(self, scope_id: str) -> Dict[str, Any]:
        """Get scope configuration from database"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                query = text("SELECT config FROM scopes WHERE id = :id")
                result = conn.execute(query, {"id": scope_id}).fetchone()
                if result and result[0]:
                    return result[0]  # config is stored as JSON
        except Exception as e:
            logger.error(f"Failed to get scope config: {e}")
        return {}
    
    def get_target_info(self, target_id: int) -> Dict[str, Any]:
        """Get target information from database"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                query = text("SELECT target_type, value FROM targets WHERE id = :id")
                result = conn.execute(query, {"id": target_id}).fetchone()
                if result:
                    return {
                        'type': result[0],
                        'value': result[1]
                    }
        except Exception as e:
            logger.error(f"Failed to get target info: {e}")
        return {}
    
    def get_enabled_sources(self, scope_id: int) -> List[str]:
        """Get list of enabled data sources for scope"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                query = text("SELECT name FROM data_sources WHERE scope_id = :scope_id AND enabled = true")
                result = conn.execute(query, {"scope_id": scope_id}).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get enabled sources: {e}")
        return []
    
    def get_api_keys(self, scope_id: str) -> Dict[str, str]:
        """Get API keys for scope"""
        try:
            import base64
            from sqlalchemy import text
            with self.engine.connect() as conn:
                query = text("""
                    SELECT ds.name, ak.key_value_encrypted 
                    FROM api_keys ak
                    JOIN data_sources ds ON ak.source_id = ds.id
                    WHERE ak.scope_id = :scope_id AND ak.enabled = true
                """)
                result = conn.execute(query, {"scope_id": scope_id}).fetchall()
                # Decrypt keys (simple base64 decoding)
                return {
                    row[0]: base64.b64decode(row[1].encode()).decode()
                    for row in result
                }
        except Exception as e:
            logger.error(f"Failed to get API keys: {e}")
        return {}
    
    def save_subdomain_finding(self, job_id: str, scope_id: str, domain: str, source: str):
        """Save subdomain finding to database"""
        logger.info(f"[FINDING] Subdomain: {domain} (source: {source})")
        self.findings_count += 1
        try:
            import uuid
            from sqlalchemy import text
            finding_id = str(uuid.uuid4())
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO recon_findings (id, time, scope_id, job_id, finding_type, value, source, first_seen, last_seen)
                    VALUES (:id, NOW(), :scope_id, :job_id, 'subdomain', :value, :source, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """)
                conn.execute(query, {
                    "id": finding_id,
                    "scope_id": scope_id,
                    "job_id": job_id,
                    "value": domain,
                    "source": source
                })
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save subdomain finding: {e}")
    
    def save_dns_record(self, job_id: str, scope_id: str, domain: str, record_type: str, value: str):
        """Save DNS record to database"""
        logger.info(f"[FINDING] DNS {record_type}: {domain} -> {value}")
        self.findings_count += 1
        try:
            import uuid
            from sqlalchemy import text
            finding_id = str(uuid.uuid4())
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO recon_findings (id, time, scope_id, job_id, finding_type, value, source, extra_data, first_seen, last_seen)
                    VALUES (:id, NOW(), :scope_id, :job_id, :finding_type, :value, 'dns_enum', :extra_data, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """)
                conn.execute(query, {
                    "id": finding_id,
                    "scope_id": scope_id,
                    "job_id": job_id,
                    "finding_type": f"dns_{record_type.lower()}",
                    "value": f"{domain}: {value}",
                    "extra_data": json.dumps({"domain": domain, "record_type": record_type, "record_value": value})
                })
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save DNS record: {e}")
    
    def save_shodan_finding(self, job_id: str, scope_id: str, ip: str, finding_type: str, value):
        """Save Shodan finding to database"""
        self.findings_count += 1
        try:
            import uuid
            from sqlalchemy import text
            finding_id = str(uuid.uuid4())
            # Convert dict values to JSON string for storage
            if isinstance(value, dict):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO recon_findings (id, time, scope_id, job_id, finding_type, value, source, extra_data, first_seen, last_seen)
                    VALUES (:id, NOW(), :scope_id, :job_id, :finding_type, :value, 'shodan', :extra_data, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """)
                conn.execute(query, {
                    "id": finding_id,
                    "scope_id": scope_id,
                    "job_id": job_id,
                    "finding_type": f"shodan_{finding_type}",
                    "value": value_str,
                    "extra_data": json.dumps({"ip": ip, "type": finding_type})
                })
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save Shodan finding: {e}")
    
    def save_nmap_finding(self, job_id: str, scope_id: str, host: str, finding_type: str, value: Dict):
        """Save Nmap finding to database"""
        self.findings_count += 1
        try:
            import uuid
            from sqlalchemy import text
            finding_id = str(uuid.uuid4())
            
            # Build value string based on finding type
            if finding_type == 'port':
                value_str = f"{host}:{value.get('port')}/{value.get('protocol', 'tcp')}"
            elif finding_type == 'service':
                value_str = f"{value.get('name', 'unknown')} {value.get('version', '')}".strip()
            else:
                value_str = json.dumps(value) if isinstance(value, dict) else str(value)
            
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO recon_findings (id, time, scope_id, job_id, finding_type, value, source, extra_data, first_seen, last_seen)
                    VALUES (:id, NOW(), :scope_id, :job_id, :finding_type, :value, 'nmap', :extra_data, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """)
                conn.execute(query, {
                    "id": finding_id,
                    "scope_id": scope_id,
                    "job_id": job_id,
                    "finding_type": f"nmap_{finding_type}",
                    "value": value_str,
                    "extra_data": json.dumps({"host": host, **value})
                })
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save Nmap finding: {e}")
    
    def save_cve_finding(self, job_id: str, scope_id: str, host: str, port: int, 
                         service_name: str, cve_data: Dict):
        """Save CVE finding to database"""
        self.findings_count += 1
        try:
            import uuid
            from sqlalchemy import text
            finding_id = str(uuid.uuid4())
            
            cve_id = cve_data.get('cve_id', 'UNKNOWN')
            severity = cve_data.get('severity', 'UNKNOWN')
            cvss_score = cve_data.get('cvss_score', 0.0)
            
            # Build value string
            value_str = f"{cve_id} ({severity}, CVSS {cvss_score})"
            
            with self.engine.connect() as conn:
                query = text("""
                    INSERT INTO recon_findings (id, time, scope_id, job_id, finding_type, value, source, extra_data, first_seen, last_seen)
                    VALUES (:id, NOW(), :scope_id, :job_id, :finding_type, :value, 'nvd', :extra_data, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """)
                conn.execute(query, {
                    "id": finding_id,
                    "scope_id": scope_id,
                    "job_id": job_id,
                    "finding_type": "cve",
                    "value": value_str,
                    "extra_data": json.dumps({
                        "host": host,
                        "port": port,
                        "service": service_name,
                        "cve_id": cve_id,
                        "severity": severity,
                        "cvss_score": cvss_score,
                        "cvss_version": cve_data.get('cvss_version', ''),
                        "description": cve_data.get('description', '')[:500],
                        "published_date": cve_data.get('published_date', ''),
                        "references": cve_data.get('references', [])[:3]
                    })
                })
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save CVE finding: {e}")
    
    def get_scope_targets(self, scope_id: str) -> List[Dict[str, Any]]:
        """Get all enabled targets for a scope"""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                query = text("SELECT id, type, value FROM targets WHERE scope_id = :scope_id AND enabled = true")
                result = conn.execute(query, {"scope_id": scope_id}).fetchall()
                return [{'id': row[0], 'type': str(row[1]), 'value': row[2]} for row in result]
        except Exception as e:
            logger.error(f"Failed to get scope targets: {e}")
        return []
    
    def execute_job(self, job_data: Dict[str, Any]):
        """Execute a reconnaissance job"""
        job_id = job_data['job_id']
        scope_id = job_data['scope_id']
        mode = job_data.get('mode', 'passive')
        
        logger.info(f"Executing job {job_id} for scope {scope_id}, mode {mode}")
        
        # Track findings count
        self.findings_count = 0
        
        try:
            # Update status to running
            self.update_job_status(job_id, 'running')
            
            # Get all targets for this scope
            targets = self.get_scope_targets(scope_id)
            if not targets:
                logger.warning(f"No targets found for scope {scope_id}")
                self.update_job_status(job_id, 'completed', findings_count=0)
                return
            
            logger.info(f"Found {len(targets)} targets to scan")
            
            # Get configuration
            scope_config = self.get_scope_config(scope_id)
            api_keys = self.get_api_keys(scope_id)
            
            for target in targets:
                target_value = target['value']
                target_type = target['type']
                
                logger.info(f"Scanning target: {target_type} - {target_value}")
                
                # Execute passive recon
                if mode == 'passive':
                    self.run_passive_recon(job_id, scope_id, target_value, scope_config, api_keys)
                # Execute active recon (includes nmap scanning)
                elif mode == 'active':
                    # First run passive recon to collect IPs
                    collected_ips = self.run_passive_recon(job_id, scope_id, target_value, scope_config, api_keys)
                    # Then run active nmap scanning on collected IPs
                    self.run_active_recon(job_id, scope_id, target_value, collected_ips, scope_config)
            
            # Mark job as completed with findings count
            self.update_job_status(job_id, 'completed', findings_count=self.findings_count)
            logger.info(f"Job {job_id} completed successfully with {self.findings_count} findings")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            self.update_job_status(job_id, 'failed', str(e))
    
    def run_passive_recon(self, job_id: str, scope_id: str, target: str, config: Dict, api_keys: Dict) -> set:
        """Run passive reconnaissance on a target
        
        Returns:
            Set of collected IP addresses for active scanning
        """
        logger.info(f"Running passive recon on {target}")
        
        # Track collected IPs for active recon
        collected_ips = set()
        
        # Subdomain enumeration using all sources
        try:
            logger.info("Running subdomain enumeration...")
            subdomain_enum = SubdomainEnumerator(target)
            subdomains = subdomain_enum.passive_enum()  # Correct method name
            logger.info(f"Found {len(subdomains)} subdomains")
            
            for subdomain in subdomains:
                self.save_subdomain_finding(job_id, scope_id, subdomain, 'passive_enum')
        except Exception as e:
            logger.error(f"Subdomain enumeration error: {e}")
        
        # DNS enumeration
        try:
            logger.info("Running DNS enumeration...")
            dns_enum = DNSEnumerator()
            dns_data = dns_enum._query_domain(target)
            if dns_data:
                for record_type in ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS']:
                    records = dns_data.get(record_type, [])
                    for record in records:
                        self.save_dns_record(job_id, scope_id, target, record_type, str(record))
                        logger.info(f"[FINDING] DNS {record_type}: {target} -> {record}")
                        # Collect IPs for Shodan and active scanning
                        if record_type in ['A', 'AAAA']:
                            collected_ips.add(str(record))
        except Exception as e:
            logger.error(f"DNS enumeration error: {e}")
        
        # Shodan IP enumeration (uses collected IPs from DNS)
        if collected_ips:
            try:
                logger.info(f"Running Shodan enumeration for {len(collected_ips)} IPs...")
                shodan_enum = ShodanEnumerator()
                shodan_results = shodan_enum.enumerate(list(collected_ips))
                logger.info(f"Shodan returned data for {len(shodan_results)} IPs")
                
                for ip, data in shodan_results.items():
                    # Save port/service findings
                    ports = data.get('ports', [])
                    services = data.get('services', [])
                    vulns = data.get('vulns', [])
                    hostnames = data.get('hostnames', [])
                    
                    # Save ports as findings
                    for port in ports:
                        self.save_shodan_finding(job_id, scope_id, ip, 'port', str(port))
                        logger.info(f"[FINDING] Shodan port: {ip}:{port}")
                    
                    # Save services
                    for service in services:
                        self.save_shodan_finding(job_id, scope_id, ip, 'service', service)
                        logger.info(f"[FINDING] Shodan service: {ip} -> {service}")
                    
                    # Save vulnerabilities
                    for vuln in vulns:
                        self.save_shodan_finding(job_id, scope_id, ip, 'vulnerability', vuln)
                        logger.info(f"[FINDING] Shodan vuln: {ip} -> {vuln}")
                    
                    # Save hostnames
                    for hostname in hostnames:
                        self.save_shodan_finding(job_id, scope_id, ip, 'hostname', hostname)
                        logger.info(f"[FINDING] Shodan hostname: {ip} -> {hostname}")
                    
                    # Save org/ASN as metadata
                    org = data.get('org', '')
                    asn = data.get('asn', '')
                    if org:
                        self.save_shodan_finding(job_id, scope_id, ip, 'organization', org)
                    if asn:
                        self.save_shodan_finding(job_id, scope_id, ip, 'asn', asn)
            except Exception as e:
                logger.error(f"Shodan enumeration error: {e}")
        
        # Certificate transparency
        try:
            logger.info("Running certificate transparency...")
            cert_enum = CertificateEnumerator()
            domains = cert_enum.enumerate(target)  # Correct method name
            logger.info(f"Certificate transparency found {len(domains)} domains")
            
            for domain in domains:
                self.save_subdomain_finding(job_id, scope_id, domain, 'certificate_transparency')
        except Exception as e:
            logger.error(f"Certificate transparency error: {e}")
        
        # Return collected IPs for active scanning
        return collected_ips
    
    def run_active_recon(self, job_id: str, scope_id: str, target: str, collected_ips: set, config: Dict):
        """Run active reconnaissance on collected IPs using Nmap with CVE lookup
        
        Args:
            job_id: Current job ID
            scope_id: Current scope ID
            target: Original target domain
            collected_ips: Set of IP addresses to scan
            config: Scope configuration
        """
        if not collected_ips:
            logger.info("No IPs collected for active scanning")
            return
        
        logger.info(f"Running active recon (Nmap + CVE lookup) on {len(collected_ips)} IPs...")
        
        try:
            # Get nmap configuration from scope config
            nmap_config = config.get('nmap', {})
            scan_type = nmap_config.get('scan_type', 'default')
            ports = nmap_config.get('ports', None)
            threads = nmap_config.get('threads', 5)
            timeout = nmap_config.get('timeout', 300)
            check_cves = nmap_config.get('check_cves', True)
            nvd_api_key = nmap_config.get('nvd_api_key', None)
            
            # Initialize Nmap scanner with CVE checking enabled
            nmap_enum = NmapEnumerator(
                threads=threads,
                timeout=timeout,
                scan_type=scan_type,
                check_cves=check_cves,
                nvd_api_key=nvd_api_key
            )
            
            # Perform the scan (CVE lookup happens automatically if enabled)
            scan_results = nmap_enum.enumerate(collected_ips, ports=ports)
            logger.info(f"Nmap scan completed for {len(scan_results)} hosts")
            
            # Process and save results
            total_cves_found = 0
            for host, data in scan_results.items():
                # Save host state
                host_state = data.get('state', 'unknown')
                hostname = data.get('hostname', '')
                
                logger.info(f"[NMAP] Host: {host} ({hostname}) - State: {host_state}")
                
                # Log CVE summary for this host
                cve_summary = data.get('cve_summary', {})
                if cve_summary.get('total', 0) > 0:
                    logger.info(f"[CVE SUMMARY] {host}: {cve_summary['total']} CVEs "
                               f"(Critical: {cve_summary.get('critical', 0)}, "
                               f"High: {cve_summary.get('high', 0)})")
                
                # Save each open port
                for port in data.get('open_ports', []):
                    port_data = {'port': port, 'protocol': 'tcp', 'state': 'open'}
                    self.save_nmap_finding(job_id, scope_id, host, 'port', port_data)
                    logger.info(f"[FINDING] Nmap port: {host}:{port}")
                
                # Save service details and CVEs
                for service in data.get('services', []):
                    service_data = {
                        'port': service.get('port'),
                        'protocol': service.get('protocol', 'tcp'),
                        'name': service.get('name', 'unknown'),
                        'product': service.get('product', ''),
                        'version': service.get('version', ''),
                        'extrainfo': service.get('extrainfo', ''),
                        'cpe': service.get('cpe', ''),
                        'banner': service.get('banner', '')
                    }
                    self.save_nmap_finding(job_id, scope_id, host, 'service', service_data)
                    
                    service_str = f"{service.get('name', 'unknown')}"
                    if service.get('product'):
                        service_str += f" ({service.get('product')} {service.get('version', '')})"
                    logger.info(f"[FINDING] Nmap service: {host}:{service.get('port')} -> {service_str}")
                    
                    # Save CVEs for this service
                    service_cves = service.get('cves', [])
                    for cve in service_cves:
                        self.save_cve_finding(
                            job_id, 
                            scope_id, 
                            host, 
                            service.get('port'),
                            service.get('name', 'unknown'),
                            cve
                        )
                        severity = cve.get('severity', 'UNKNOWN')
                        cvss = cve.get('cvss_score', 0)
                        logger.info(f"[FINDING] CVE: {host}:{service.get('port')} -> "
                                   f"{cve.get('cve_id')} ({severity}, CVSS {cvss})")
                        total_cves_found += 1
                
                # Save OS detection if available
                os_info = data.get('os_detection')
                if os_info:
                    self.save_nmap_finding(job_id, scope_id, host, 'os', os_info)
                    logger.info(f"[FINDING] Nmap OS: {host} -> {os_info.get('name', 'unknown')}")
            
            # Log total CVEs found
            if total_cves_found > 0:
                logger.info(f"[CVE TOTAL] Found {total_cves_found} CVEs across all hosts")
                    
        except Exception as e:
            logger.error(f"Nmap enumeration error: {e}")

    def run(self):
        """Main worker loop"""
        logger.info("Worker started, waiting for jobs...")
        
        while True:
            try:
                # Block and wait for job (BRPOP with timeout)
                result = self.redis_client.brpop(self.job_queue, timeout=5)
                
                if result:
                    queue_name, job_json = result
                    job_data = json.loads(job_json)
                    
                    logger.info(f"Received job: {job_data}")
                    self.execute_job(job_data)
                
            except KeyboardInterrupt:
                logger.info("Worker shutting down...")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)


if __name__ == "__main__":
    worker = ReconWorker()
    worker.run()
