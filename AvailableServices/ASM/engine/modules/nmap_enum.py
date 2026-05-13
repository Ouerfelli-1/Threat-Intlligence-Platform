"""Nmap port scanning and service enumeration module with CVE lookup"""

import nmap
import logging
from typing import Dict, List, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger('recon_tool')

# Import CVE lookup module (will be available after creation)
try:
    from modules.cve_lookup import CVELookup, CVEResult
    CVE_LOOKUP_AVAILABLE = True
except ImportError:
    CVE_LOOKUP_AVAILABLE = False
    logger.warning("CVE lookup module not available")


class NmapEnumerator:
    """Enumerate open ports, services, and versions using Nmap"""
    
    # Default scan arguments
    DEFAULT_ARGUMENTS = '-sV -sC'  # Service version detection + default scripts
    FAST_ARGUMENTS = '-sV -F'      # Fast scan with version detection
    FULL_ARGUMENTS = '-sV -sC -p-' # Full port range with version detection
    
    def __init__(self, threads: int = 5, timeout: int = 300, scan_type: str = 'default',
                 check_cves: bool = True, nvd_api_key: str = None, config_file: str = None):
        """
        Initialize NmapEnumerator
        
        Args:
            threads: Number of parallel scan threads
            timeout: Timeout for each scan in seconds
            scan_type: Type of scan - 'fast', 'default', or 'full'
            check_cves: Whether to check for CVEs after scanning
            nvd_api_key: NVD API key for higher rate limits (optional)
        """
        self.threads = threads
        self.timeout = timeout
        self.scan_type = scan_type
        self.nvd_api_key = nvd_api_key
        self.nm = nmap.PortScanner()
        
        # Load configuration from file if not provided
        self._load_config(config_file)
        
        # Override with explicit parameters
        if threads != 5:  # Non-default value was passed
            self.threads = threads
        if timeout != 300:
            self.timeout = timeout
        if scan_type != 'default':
            self.scan_type = scan_type
        if nvd_api_key:
            self.nvd_api_key = nvd_api_key
        
        self.check_cves = check_cves and CVE_LOOKUP_AVAILABLE
        
        # Initialize CVE lookup if enabled
        self.cve_lookup = None
        if self.check_cves:
            self.cve_lookup = CVELookup(api_key=self.nvd_api_key)
            logger.info("CVE lookup enabled")
        
        # Set scan arguments based on scan type
        if self.scan_type == 'fast':
            self.arguments = self.FAST_ARGUMENTS
        elif self.scan_type == 'full':
            self.arguments = self.FULL_ARGUMENTS
        else:
            self.arguments = self.DEFAULT_ARGUMENTS
    
    def _load_config(self, config_file: str = None):
        """Load configuration from config.ini file"""
        import configparser
        from pathlib import Path
        import os
        
        # Get config path relative to this file's location (engine/modules -> engine/config.ini)
        if config_file is None:
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            config_path = current_dir.parent / 'config.ini'
        else:
            config_path = Path(config_file)
        
        logger.debug(f"Nmap: Looking for config at {config_path}")
        
        if not config_path.exists():
            logger.debug(f"Nmap: Config file not found: {config_path}")
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            
            if 'nmap' in config:
                self.scan_type = config['nmap'].get('scan_type', self.scan_type)
                self.threads = config['nmap'].getint('threads', self.threads)
                self.timeout = config['nmap'].getint('timeout', self.timeout)
                logger.debug(f"Nmap: Loaded config - scan_type={self.scan_type}, threads={self.threads}")
            
            if 'nvd' in config and 'api_key' in config['nvd']:
                api_key = config['nvd']['api_key']
                if api_key and api_key != 'YOUR_API_KEY_HERE':
                    self.nvd_api_key = api_key
                    logger.info(f"NVD API key loaded from config (key: {api_key[:8]}...)")
        except Exception as e:
            logger.warning(f"Error loading Nmap config: {e}")
    
    def is_configured(self) -> bool:
        """Check if Nmap scanner is ready"""
        try:
            # Try to get nmap version to verify it's installed
            self.nm.nmap_version()
            return True
        except Exception:
            return False

    def enumerate(self, hosts: Set[str], ports: str = None, check_cves: bool = None) -> Dict[str, Dict]:
        """
        Scan multiple hosts for open ports and services, optionally checking for CVEs
        
        Args:
            hosts: Set of hostnames or IP addresses to scan
            ports: Optional port range (e.g., '22,80,443' or '1-1000')
            check_cves: Override instance setting for CVE checking
        
        Returns:
            Dictionary mapping hosts to their scan results (including CVEs if enabled)
        """
        logger.info(f"Starting Nmap scan for {len(hosts)} hosts...")
        
        scan_results = {}
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {
                executor.submit(self._scan_host, host, ports): host 
                for host in hosts
            }
            
            completed = 0
            for future in as_completed(futures):
                host = futures[future]
                try:
                    result = future.result()
                    if result:
                        scan_results[host] = result
                        logger.debug(f"Completed scan for {host}")
                    completed += 1
                    if completed % 5 == 0:
                        logger.info(f"Progress: {completed}/{len(hosts)} hosts scanned")
                except Exception as e:
                    logger.error(f"Error scanning {host}: {e}")
        
        logger.info(f"Nmap scan completed for {len(scan_results)} hosts")
        
        # Check for CVEs if enabled
        should_check_cves = check_cves if check_cves is not None else self.check_cves
        if should_check_cves and self.cve_lookup and scan_results:
            logger.info("Starting CVE lookup for discovered services...")
            scan_results = self._enrich_with_cves(scan_results)
        
        return scan_results
    
    def _enrich_with_cves(self, scan_results: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Enrich scan results with CVE information for each service
        
        Args:
            scan_results: Dictionary of scan results
        
        Returns:
            Enriched scan results with CVE data
        """
        for host, data in scan_results.items():
            services = data.get('services', [])
            if not services:
                continue
            
            logger.info(f"Checking CVEs for {len(services)} services on {host}...")
            
            # Check each service for CVEs
            for service in services:
                port = service.get('port')
                product = service.get('product', '')
                version = service.get('version', '')
                
                if not product:
                    logger.debug(f"Skipping CVE check for port {port}: no product info")
                    service['cves'] = []
                    continue
                
                try:
                    cves = self.cve_lookup.check_service_vulnerabilities(service)
                    
                    # Convert CVEResult objects to dictionaries
                    service['cves'] = [
                        {
                            'cve_id': cve.cve_id,
                            'severity': cve.severity,
                            'cvss_score': cve.cvss_score,
                            'cvss_version': cve.cvss_version,
                            'description': cve.description,
                            'published_date': cve.published_date,
                            'references': cve.references[:3]  # Limit references
                        }
                        for cve in cves
                    ]
                    
                    if cves:
                        # Sort by severity
                        critical_high = [c for c in cves if c.severity in ['CRITICAL', 'HIGH']]
                        logger.info(f"[CVE] {host}:{port} ({product} {version}) - "
                                   f"{len(cves)} CVEs found ({len(critical_high)} critical/high)")
                    
                except Exception as e:
                    logger.error(f"Error checking CVEs for {host}:{port}: {e}")
                    service['cves'] = []
            
            # Add summary to host data
            total_cves = sum(len(s.get('cves', [])) for s in services)
            critical_cves = sum(
                len([c for c in s.get('cves', []) if c.get('severity') == 'CRITICAL'])
                for s in services
            )
            high_cves = sum(
                len([c for c in s.get('cves', []) if c.get('severity') == 'HIGH'])
                for s in services
            )
            
            data['cve_summary'] = {
                'total': total_cves,
                'critical': critical_cves,
                'high': high_cves,
                'medium': sum(
                    len([c for c in s.get('cves', []) if c.get('severity') == 'MEDIUM'])
                    for s in services
                ),
                'low': sum(
                    len([c for c in s.get('cves', []) if c.get('severity') == 'LOW'])
                    for s in services
                )
            }
            
            if total_cves > 0:
                logger.info(f"[CVE SUMMARY] {host}: {total_cves} total CVEs "
                           f"({critical_cves} critical, {high_cves} high)")
        
        return scan_results
    
    def _scan_host(self, host: str, ports: str = None) -> Optional[Dict]:
        """
        Scan a single host for open ports and services
        
        Args:
            host: Hostname or IP address to scan
            ports: Optional port range
        
        Returns:
            Dictionary containing scan results or None if scan failed
        """
        try:
            logger.debug(f"Scanning host: {host}")
            
            # Build scan arguments
            arguments = self.arguments
            if ports:
                arguments = f"{arguments} -p {ports}"
            
            # Perform the scan
            self.nm.scan(hosts=host, arguments=arguments, timeout=self.timeout)
            
            # Check if host was scanned
            if host not in self.nm.all_hosts():
                # Try with the first resolved host
                scanned_hosts = self.nm.all_hosts()
                if not scanned_hosts:
                    logger.debug(f"No results for host: {host}")
                    return None
                host = scanned_hosts[0]
            
            host_info = self.nm[host]
            
            # Build result dictionary
            result = {
                'host': host,
                'hostname': self._get_hostname(host_info),
                'state': host_info.state(),
                'protocols': [],
                'open_ports': [],
                'services': [],
                'os_detection': self._get_os_info(host_info),
                'scan_time': self.nm.scaninfo().get('tcp', {}).get('elapsed', 'unknown')
            }
            
            # Process each protocol (tcp, udp)
            for protocol in host_info.all_protocols():
                result['protocols'].append(protocol)
                ports_list = host_info[protocol].keys()
                
                for port in sorted(ports_list):
                    port_info = host_info[protocol][port]
                    
                    port_data = {
                        'port': port,
                        'protocol': protocol,
                        'state': port_info['state'],
                        'service': port_info.get('name', 'unknown'),
                        'product': port_info.get('product', ''),
                        'version': port_info.get('version', ''),
                        'extrainfo': port_info.get('extrainfo', ''),
                        'cpe': port_info.get('cpe', '')
                    }
                    
                    # Add to open ports if state is open
                    if port_info['state'] == 'open':
                        result['open_ports'].append(port)
                        
                        # Build service info
                        service_info = {
                            'port': port,
                            'protocol': protocol,
                            'name': port_info.get('name', 'unknown'),
                            'product': port_info.get('product', ''),
                            'version': port_info.get('version', ''),
                            'extrainfo': port_info.get('extrainfo', ''),
                            'cpe': port_info.get('cpe', ''),
                            'banner': self._build_banner(port_info)
                        }
                        result['services'].append(service_info)
            
            logger.debug(f"Found {len(result['open_ports'])} open ports on {host}")
            return result
            
        except nmap.PortScannerError as e:
            logger.error(f"Nmap error for {host}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error scanning {host}: {e}")
            return None
    
    def _get_hostname(self, host_info) -> str:
        """Extract hostname from host info"""
        try:
            hostnames = host_info.hostnames()
            if hostnames:
                return hostnames[0].get('name', '')
        except Exception:
            pass
        return ''
    
    def _get_os_info(self, host_info) -> Optional[Dict]:
        """Extract OS detection information"""
        try:
            if 'osmatch' in host_info:
                os_matches = host_info['osmatch']
                if os_matches:
                    best_match = os_matches[0]
                    return {
                        'name': best_match.get('name', 'unknown'),
                        'accuracy': best_match.get('accuracy', '0'),
                        'os_family': best_match.get('osclass', [{}])[0].get('osfamily', 'unknown') if best_match.get('osclass') else 'unknown'
                    }
        except Exception:
            pass
        return None
    
    def _build_banner(self, port_info: Dict) -> str:
        """Build a banner string from port info"""
        parts = []
        if port_info.get('product'):
            parts.append(port_info['product'])
        if port_info.get('version'):
            parts.append(port_info['version'])
        if port_info.get('extrainfo'):
            parts.append(f"({port_info['extrainfo']})")
        return ' '.join(parts) if parts else ''
    
    def scan_single_host(self, host: str, ports: str = None) -> Optional[Dict]:
        """
        Convenience method to scan a single host
        
        Args:
            host: Hostname or IP address
            ports: Optional port range
        
        Returns:
            Scan results dictionary
        """
        return self._scan_host(host, ports)
    
    def get_open_ports(self, scan_result: Dict) -> List[int]:
        """Extract list of open ports from scan result"""
        return scan_result.get('open_ports', [])
    
    def get_services(self, scan_result: Dict) -> List[Dict]:
        """Extract list of services from scan result"""
        return scan_result.get('services', [])
    
    def get_service_by_port(self, scan_result: Dict, port: int) -> Optional[Dict]:
        """Get service information for a specific port"""
        for service in scan_result.get('services', []):
            if service['port'] == port:
                return service
        return None
    
    def format_results(self, scan_results: Dict[str, Dict]) -> str:
        """
        Format scan results as a readable string
        
        Args:
            scan_results: Dictionary of scan results
        
        Returns:
            Formatted string representation
        """
        output = []
        
        for host, data in scan_results.items():
            output.append(f"\n{'='*70}")
            output.append(f"Host: {host}")
            if data.get('hostname'):
                output.append(f"Hostname: {data['hostname']}")
            output.append(f"State: {data.get('state', 'unknown')}")
            
            if data.get('os_detection'):
                os_info = data['os_detection']
                output.append(f"OS: {os_info.get('name', 'unknown')} ({os_info.get('accuracy', '0')}% confidence)")
            
            # CVE Summary
            if data.get('cve_summary'):
                summary = data['cve_summary']
                output.append(f"\n🔒 CVE Summary: {summary['total']} vulnerabilities found")
                output.append(f"   🔴 Critical: {summary['critical']}  🟠 High: {summary['high']}  "
                            f"🟡 Medium: {summary['medium']}  🟢 Low: {summary['low']}")
            
            output.append(f"\nOpen Ports ({len(data.get('open_ports', []))}):")
            output.append("-" * 60)
            
            for service in data.get('services', []):
                port_str = f"{service['port']}/{service['protocol']}"
                service_str = service['name']
                version_str = service['banner'] or 'unknown version'
                output.append(f"  {port_str:<12} {service_str:<15} {version_str}")
                
                # Show CVEs for this service
                cves = service.get('cves', [])
                if cves:
                    output.append(f"    └─ {len(cves)} CVEs found:")
                    # Show top 5 by severity
                    sorted_cves = sorted(cves, key=lambda x: x.get('cvss_score', 0), reverse=True)
                    for cve in sorted_cves[:5]:
                        severity_icon = {
                            'CRITICAL': '🔴',
                            'HIGH': '🟠',
                            'MEDIUM': '🟡',
                            'LOW': '🟢'
                        }.get(cve.get('severity', ''), '⚪')
                        output.append(f"       {severity_icon} {cve['cve_id']} "
                                    f"(CVSS {cve['cvss_score']:.1f} - {cve['severity']})")
                    if len(cves) > 5:
                        output.append(f"       ... and {len(cves) - 5} more CVEs")
        
        return '\n'.join(output)
    
    def get_all_cves(self, scan_results: Dict[str, Dict]) -> List[Dict]:
        """
        Extract all CVEs from scan results
        
        Args:
            scan_results: Dictionary of scan results
        
        Returns:
            List of all CVE dictionaries with host/port context
        """
        all_cves = []
        
        for host, data in scan_results.items():
            for service in data.get('services', []):
                for cve in service.get('cves', []):
                    cve_with_context = {
                        **cve,
                        'host': host,
                        'port': service.get('port'),
                        'service_name': service.get('name'),
                        'product': service.get('product'),
                        'version': service.get('version')
                    }
                    all_cves.append(cve_with_context)
        
        # Sort by CVSS score (highest first)
        all_cves.sort(key=lambda x: x.get('cvss_score', 0), reverse=True)
        return all_cves
    
    def get_critical_cves(self, scan_results: Dict[str, Dict]) -> List[Dict]:
        """Get only critical and high severity CVEs"""
        all_cves = self.get_all_cves(scan_results)
        return [cve for cve in all_cves if cve.get('severity') in ['CRITICAL', 'HIGH']]


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Create enumerator with CVE checking enabled
    enumerator = NmapEnumerator(scan_type='fast', check_cves=True)
    
    # Scan a host
    results = enumerator.enumerate({'scanme.nmap.org'})
    
    # Print formatted results (includes CVEs)
    print(enumerator.format_results(results))
    
    # Get critical CVEs
    critical = enumerator.get_critical_cves(results)
    if critical:
        print(f"\n⚠️  Found {len(critical)} critical/high CVEs!")
        for cve in critical[:10]:
            print(f"  - {cve['cve_id']}: {cve['host']}:{cve['port']} ({cve['product']})")
