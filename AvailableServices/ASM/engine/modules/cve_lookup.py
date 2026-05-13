"""CVE Lookup Module using NVD (National Vulnerability Database)

This module checks service versions against the NVD database to find
known vulnerabilities (CVEs) associated with detected software.
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

logger = logging.getLogger('recon_tool')

# NVD API base URL
NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


@dataclass
class CVEResult:
    """Represents a CVE finding"""
    cve_id: str
    description: str
    severity: str
    cvss_score: float
    cvss_version: str
    published_date: str
    last_modified: str
    references: List[str]
    cpe_match: str
    exploitability_score: Optional[float] = None
    impact_score: Optional[float] = None


class CVELookup:
    """Lookup CVEs for software versions using NVD API"""
    
    # Rate limiting: NVD allows 5 requests per 30 seconds without API key
    # With API key: 50 requests per 30 seconds
    RATE_LIMIT_DELAY = 6.0  # seconds between requests (without API key)
    RATE_LIMIT_DELAY_WITH_KEY = 0.6  # seconds with API key
    
    def __init__(self, api_key: str = None, threads: int = 3, config_file: str = None):
        """
        Initialize CVE Lookup
        
        Args:
            api_key: NVD API key (optional, but recommended for higher rate limits)
            threads: Number of parallel lookup threads
            config_file: Path to config file (optional)
        """
        self.api_key = api_key
        self.threads = threads
        self.session = requests.Session()
        self.last_request_time = 0
        self.max_results = 20
        
        # Load configuration from file if not provided
        self._load_config(config_file)
        
        # Override with explicit parameters
        if api_key:
            self.api_key = api_key
        
        # Set headers
        self.headers = {
            'User-Agent': 'ReconTool-CVELookup/1.0'
        }
        if self.api_key:
            self.headers['apiKey'] = self.api_key
    
    def _load_config(self, config_file: str = None):
        """Load configuration from config.ini file"""
        import configparser
        from pathlib import Path
        import os
        
        # Get config path relative to this file's location
        if config_file is None:
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            config_path = current_dir.parent / 'config.ini'
        else:
            config_path = Path(config_file)
        
        logger.debug(f"CVELookup: Looking for config at {config_path}")
        
        if not config_path.exists():
            logger.debug(f"CVELookup: Config file not found: {config_path}")
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            
            if 'nvd' in config:
                api_key = config['nvd'].get('api_key', '')
                if api_key and api_key != 'YOUR_API_KEY_HERE':
                    self.api_key = api_key
                    logger.info(f"NVD API key loaded from config (key: {api_key[:8]}...)")
                
                self.max_results = config['nvd'].getint('max_results', self.max_results)
        except Exception as e:
            logger.warning(f"Error loading CVE config: {e}")
    
    def is_configured(self) -> bool:
        """Check if CVE lookup is configured (has API key for better rate limits)"""
        return self.api_key is not None
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        delay = self.RATE_LIMIT_DELAY_WITH_KEY if self.api_key else self.RATE_LIMIT_DELAY
        elapsed = time.time() - self.last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request_time = time.time()
    
    def _build_cpe_string(self, vendor: str, product: str, version: str = None) -> str:
        """
        Build a CPE 2.3 string for querying NVD
        
        Args:
            vendor: Software vendor (e.g., 'apache')
            product: Product name (e.g., 'http_server')
            version: Version string (e.g., '2.4.51')
        
        Returns:
            CPE 2.3 formatted string
        """
        # Normalize strings
        vendor = vendor.lower().replace(' ', '_').replace('-', '_')
        product = product.lower().replace(' ', '_').replace('-', '_')
        
        if version:
            version = version.replace(' ', '_')
            return f"cpe:2.3:a:{vendor}:{product}:{version}:*:*:*:*:*:*:*"
        else:
            return f"cpe:2.3:a:{vendor}:{product}:*:*:*:*:*:*:*:*"
    
    def _parse_service_info(self, service: Dict) -> Dict:
        """
        Parse service info from Nmap result to extract vendor/product/version
        
        Args:
            service: Service dictionary from Nmap scan
        
        Returns:
            Dictionary with vendor, product, version
        """
        product = service.get('product', '').lower()
        version = service.get('version', '')
        name = service.get('name', '').lower()
        cpe = service.get('cpe', '')
        
        # Try to extract from CPE first (most accurate)
        if cpe:
            cpe_parts = cpe.split(':')
            if len(cpe_parts) >= 5:
                return {
                    'vendor': cpe_parts[3] if len(cpe_parts) > 3 else '',
                    'product': cpe_parts[4] if len(cpe_parts) > 4 else '',
                    'version': cpe_parts[5] if len(cpe_parts) > 5 and cpe_parts[5] != '*' else version,
                    'cpe': cpe
                }
        
        # Map common service names to vendor/product
        service_mappings = {
            'apache': ('apache', 'http_server'),
            'nginx': ('nginx', 'nginx'),
            'openssh': ('openbsd', 'openssh'),
            'ssh': ('openbsd', 'openssh'),
            'mysql': ('oracle', 'mysql'),
            'mariadb': ('mariadb', 'mariadb'),
            'postgresql': ('postgresql', 'postgresql'),
            'microsoft-ds': ('microsoft', 'windows'),
            'ftp': ('vsftpd', 'vsftpd') if 'vsftpd' in product else ('proftpd', 'proftpd'),
            'http': ('apache', 'http_server') if 'apache' in product else ('nginx', 'nginx'),
            'iis': ('microsoft', 'internet_information_services'),
            'tomcat': ('apache', 'tomcat'),
            'redis': ('redis', 'redis'),
            'mongodb': ('mongodb', 'mongodb'),
            'elasticsearch': ('elastic', 'elasticsearch'),
            'docker': ('docker', 'docker'),
            'kubernetes': ('kubernetes', 'kubernetes'),
            'jenkins': ('jenkins', 'jenkins'),
            'grafana': ('grafana', 'grafana'),
            'prometheus': ('prometheus', 'prometheus'),
            'rabbitmq': ('vmware', 'rabbitmq'),
            'memcached': ('memcached', 'memcached'),
            'postfix': ('postfix', 'postfix'),
            'exim': ('exim', 'exim'),
            'dovecot': ('dovecot', 'dovecot'),
            'bind': ('isc', 'bind'),
            'proftpd': ('proftpd', 'proftpd'),
            'vsftpd': ('vsftpd', 'vsftpd'),
            'pure-ftpd': ('pureftpd', 'pure-ftpd'),
            'samba': ('samba', 'samba'),
            'cups': ('apple', 'cups'),
            'squid': ('squid-cache', 'squid'),
            'haproxy': ('haproxy', 'haproxy'),
            'varnish': ('varnish', 'varnish'),
            'lighttpd': ('lighttpd', 'lighttpd'),
        }
        
        # Try to match product name
        vendor, prod = None, None
        for key, (v, p) in service_mappings.items():
            if key in product or key in name:
                vendor, prod = v, p
                break
        
        # Fallback: use product as both vendor and product
        if not vendor and product:
            vendor = product.split()[0] if ' ' in product else product
            prod = product.replace(' ', '_')
        
        return {
            'vendor': vendor or 'unknown',
            'product': prod or name or 'unknown',
            'version': version,
            'cpe': ''
        }
    
    def lookup_cves_by_cpe(self, cpe_string: str, max_results: int = 20) -> List[CVEResult]:
        """
        Query NVD for CVEs matching a CPE string
        
        Args:
            cpe_string: CPE 2.3 formatted string
            max_results: Maximum number of results to return
        
        Returns:
            List of CVEResult objects
        """
        self._rate_limit()
        
        try:
            params = {
                'cpeName': cpe_string,
                'resultsPerPage': max_results
            }
            
            response = self.session.get(
                NVD_API_BASE,
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 403:
                logger.warning("NVD API rate limit exceeded, waiting...")
                time.sleep(30)
                return []
            
            response.raise_for_status()
            data = response.json()
            
            return self._parse_nvd_response(data, cpe_string)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"NVD API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing NVD response: {e}")
            return []
    
    def lookup_cves_by_keyword(self, keyword: str, version: str = None, max_results: int = 10) -> List[CVEResult]:
        """
        Query NVD for CVEs by keyword search
        
        Args:
            keyword: Product name to search
            version: Optional version to include in search
            max_results: Maximum number of results
        
        Returns:
            List of CVEResult objects
        """
        self._rate_limit()
        
        try:
            search_term = f"{keyword} {version}" if version else keyword
            
            params = {
                'keywordSearch': search_term,
                'resultsPerPage': max_results
            }
            
            response = self.session.get(
                NVD_API_BASE,
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 403:
                logger.warning("NVD API rate limit exceeded")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            return self._parse_nvd_response(data, keyword)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"NVD API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing NVD response: {e}")
            return []
    
    def _parse_nvd_response(self, data: Dict, search_term: str) -> List[CVEResult]:
        """Parse NVD API response into CVEResult objects"""
        results = []
        
        vulnerabilities = data.get('vulnerabilities', [])
        
        for vuln in vulnerabilities:
            cve = vuln.get('cve', {})
            
            # Extract CVE ID
            cve_id = cve.get('id', '')
            
            # Extract description
            descriptions = cve.get('descriptions', [])
            description = ''
            for desc in descriptions:
                if desc.get('lang') == 'en':
                    description = desc.get('value', '')
                    break
            
            # Extract CVSS scores (try v3.1, v3.0, then v2)
            metrics = cve.get('metrics', {})
            cvss_score = 0.0
            severity = 'UNKNOWN'
            cvss_version = ''
            exploitability_score = None
            impact_score = None
            
            if 'cvssMetricV31' in metrics:
                cvss_data = metrics['cvssMetricV31'][0]
                cvss = cvss_data.get('cvssData', {})
                cvss_score = cvss.get('baseScore', 0.0)
                severity = cvss.get('baseSeverity', 'UNKNOWN')
                cvss_version = '3.1'
                exploitability_score = cvss_data.get('exploitabilityScore')
                impact_score = cvss_data.get('impactScore')
            elif 'cvssMetricV30' in metrics:
                cvss_data = metrics['cvssMetricV30'][0]
                cvss = cvss_data.get('cvssData', {})
                cvss_score = cvss.get('baseScore', 0.0)
                severity = cvss.get('baseSeverity', 'UNKNOWN')
                cvss_version = '3.0'
                exploitability_score = cvss_data.get('exploitabilityScore')
                impact_score = cvss_data.get('impactScore')
            elif 'cvssMetricV2' in metrics:
                cvss_data = metrics['cvssMetricV2'][0]
                cvss = cvss_data.get('cvssData', {})
                cvss_score = cvss.get('baseScore', 0.0)
                severity = self._cvss2_to_severity(cvss_score)
                cvss_version = '2.0'
                exploitability_score = cvss_data.get('exploitabilityScore')
                impact_score = cvss_data.get('impactScore')
            
            # Extract references
            references = []
            for ref in cve.get('references', []):
                references.append(ref.get('url', ''))
            
            # Extract dates
            published = cve.get('published', '')
            modified = cve.get('lastModified', '')
            
            results.append(CVEResult(
                cve_id=cve_id,
                description=description[:500] if description else '',  # Truncate long descriptions
                severity=severity,
                cvss_score=cvss_score,
                cvss_version=cvss_version,
                published_date=published[:10] if published else '',
                last_modified=modified[:10] if modified else '',
                references=references[:5],  # Limit references
                cpe_match=search_term,
                exploitability_score=exploitability_score,
                impact_score=impact_score
            ))
        
        return results
    
    def _cvss2_to_severity(self, score: float) -> str:
        """Convert CVSS v2 score to severity string"""
        if score >= 7.0:
            return 'HIGH'
        elif score >= 4.0:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def check_service_vulnerabilities(self, service: Dict) -> List[CVEResult]:
        """
        Check a single service for known vulnerabilities
        
        Args:
            service: Service dictionary from Nmap scan
        
        Returns:
            List of CVEResult objects
        """
        parsed = self._parse_service_info(service)
        
        if parsed['vendor'] == 'unknown' or parsed['product'] == 'unknown':
            logger.debug(f"Cannot lookup CVEs: unknown vendor/product for {service}")
            return []
        
        results = []
        
        # Try CPE lookup first if we have a CPE
        if parsed.get('cpe'):
            results = self.lookup_cves_by_cpe(parsed['cpe'])
        
        # If no CPE or no results, try building one
        if not results and parsed['version']:
            cpe = self._build_cpe_string(parsed['vendor'], parsed['product'], parsed['version'])
            results = self.lookup_cves_by_cpe(cpe)
        
        # Fallback to keyword search
        if not results:
            keyword = f"{parsed['vendor']} {parsed['product']}"
            results = self.lookup_cves_by_keyword(keyword, parsed['version'])
        
        return results
    
    def check_multiple_services(self, services: List[Dict]) -> Dict[str, List[CVEResult]]:
        """
        Check multiple services for vulnerabilities
        
        Args:
            services: List of service dictionaries from Nmap scan
        
        Returns:
            Dictionary mapping service identifiers to CVE results
        """
        all_results = {}
        
        for service in services:
            port = service.get('port', 'unknown')
            name = service.get('name', 'unknown')
            product = service.get('product', '')
            version = service.get('version', '')
            
            service_key = f"{port}/{name}"
            if product:
                service_key += f" ({product} {version})"
            
            logger.info(f"Checking CVEs for: {service_key}")
            
            cves = self.check_service_vulnerabilities(service)
            
            if cves:
                all_results[service_key] = cves
                logger.info(f"Found {len(cves)} CVEs for {service_key}")
            else:
                logger.debug(f"No CVEs found for {service_key}")
        
        return all_results
    
    def check_nmap_results(self, nmap_results: Dict[str, Dict]) -> Dict[str, Dict[str, List[CVEResult]]]:
        """
        Check all hosts from Nmap scan results for vulnerabilities
        
        Args:
            nmap_results: Dictionary of Nmap scan results (host -> scan data)
        
        Returns:
            Dictionary mapping hosts to their service CVE results
        """
        all_host_cves = {}
        
        for host, data in nmap_results.items():
            logger.info(f"Checking CVEs for host: {host}")
            
            services = data.get('services', [])
            if not services:
                logger.debug(f"No services found for {host}")
                continue
            
            host_cves = self.check_multiple_services(services)
            
            if host_cves:
                all_host_cves[host] = host_cves
                total_cves = sum(len(cves) for cves in host_cves.values())
                logger.info(f"Found {total_cves} total CVEs for {host}")
        
        return all_host_cves
    
    def format_cve_results(self, host_cves: Dict[str, Dict[str, List[CVEResult]]]) -> str:
        """Format CVE results as readable string"""
        output = []
        
        for host, services in host_cves.items():
            output.append(f"\n{'='*60}")
            output.append(f"Host: {host}")
            output.append('='*60)
            
            for service_key, cves in services.items():
                output.append(f"\n  Service: {service_key}")
                output.append(f"  Found {len(cves)} CVEs:")
                output.append('-'*50)
                
                # Sort by CVSS score (highest first)
                sorted_cves = sorted(cves, key=lambda x: x.cvss_score, reverse=True)
                
                for cve in sorted_cves[:10]:  # Show top 10
                    severity_color = {
                        'CRITICAL': '🔴',
                        'HIGH': '🟠',
                        'MEDIUM': '🟡',
                        'LOW': '🟢',
                        'UNKNOWN': '⚪'
                    }.get(cve.severity, '⚪')
                    
                    output.append(f"    {severity_color} {cve.cve_id} (CVSS {cve.cvss_score} - {cve.severity})")
                    output.append(f"       {cve.description[:100]}...")
        
        return '\n'.join(output)


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Create lookup instance
    cve_lookup = CVELookup()
    
    # Example service from Nmap
    test_service = {
        'port': 22,
        'name': 'ssh',
        'product': 'OpenSSH',
        'version': '7.4',
        'cpe': 'cpe:/a:openbsd:openssh:7.4'
    }
    
    # Check for vulnerabilities
    cves = cve_lookup.check_service_vulnerabilities(test_service)
    
    for cve in cves:
        print(f"{cve.cve_id}: {cve.severity} ({cve.cvss_score})")
        print(f"  {cve.description[:100]}...")
