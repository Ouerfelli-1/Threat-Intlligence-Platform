"""Shodan API integration module"""

import shodan
import logging
from typing import Dict, Set, List
import configparser
from pathlib import Path
import os

logger = logging.getLogger('recon_tool')

class ShodanEnumerator:
    """Enumerate information using Shodan API"""
    
    def __init__(self, config_file: str = None):
        self.api = None
        self.api_key = None
        self._load_config(config_file)
    
    def _load_config(self, config_file: str = None):
        """Load Shodan API key from config file"""
        # Get config path relative to this file's location (engine/modules -> engine/config.ini)
        if config_file is None:
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            config_path = current_dir.parent / 'config.ini'
        else:
            config_path = Path(config_file)
        
        logger.debug(f"Shodan: Looking for config at {config_path}")
        
        if not config_path.exists():
            logger.debug(f"Shodan: Config file not found: {config_path}")
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            
            if 'shodan' in config and 'api_key' in config['shodan']:
                self.api_key = config['shodan']['api_key']
                if self.api_key and self.api_key != 'YOUR_API_KEY_HERE':
                    self.api = shodan.Shodan(self.api_key)
                    logger.info(f"Shodan API initialized successfully (key: {self.api_key[:8]}...)")
                else:
                    logger.debug("Shodan: API key not configured or is placeholder")
        except Exception as e:
            logger.warning(f"Error loading Shodan config: {e}")
    
    def is_configured(self) -> bool:
        """Check if Shodan API is configured"""
        return self.api is not None
    
    def enumerate(self, ips: Set[str]) -> Dict[str, Dict]:
        """Query Shodan for information about IP addresses"""
        if not self.is_configured():
            logger.warning("Shodan API not configured")
            return {}
        
        logger.info(f"Querying Shodan for {len(ips)} IP addresses...")
        
        shodan_data = {}
        
        for ip in ips:
            try:
                info = self._query_ip(ip)
                if info:
                    shodan_data[ip] = info
                    logger.debug(f"Retrieved Shodan data for {ip}")
            except shodan.APIError as e:
                logger.debug(f"Shodan API error for {ip}: {e}")
            except Exception as e:
                logger.debug(f"Error querying {ip}: {e}")
        
        logger.info(f"Retrieved Shodan data for {len(shodan_data)} IPs")
        return shodan_data
    
    def _query_ip(self, ip: str) -> Dict:
        """Query Shodan for a specific IP"""
        try:
            host = self.api.host(ip)
            
            # Extract relevant information
            data = {
                'ip': ip,
                'hostnames': host.get('hostnames', []),
                'organization': host.get('org', 'Unknown'),
                'isp': host.get('isp', 'Unknown'),
                'asn': host.get('asn', 'Unknown'),
                'country': host.get('country_name', 'Unknown'),
                'city': host.get('city', 'Unknown'),
                'ports': host.get('ports', []),
                'vulns': host.get('vulns', []),
                'tags': host.get('tags', []),
                'os': host.get('os', None),
                'services': []
            }
            
            # Extract service information
            for item in host.get('data', []):
                service = {
                    'port': item.get('port'),
                    'protocol': item.get('transport', 'tcp'),
                    'service': item.get('product', item.get('_shodan', {}).get('module', 'Unknown')),
                    'version': item.get('version', ''),
                    'banner': item.get('data', '')[:200]  # Limit banner length
                }
                data['services'].append(service)
            
            return data
        except shodan.APIError as e:
            if 'No information available' in str(e):
                logger.debug(f"No Shodan data for {ip}")
            else:
                raise
        
        return None
    
    def search_domain(self, domain: str) -> List[Dict]:
        """Search Shodan for a domain"""
        if not self.is_configured():
            return []
        
        try:
            results = self.api.search(f'hostname:{domain}')
            
            hosts = []
            for result in results['matches']:
                host = {
                    'ip': result.get('ip_str'),
                    'port': result.get('port'),
                    'organization': result.get('org', 'Unknown'),
                    'hostnames': result.get('hostnames', []),
                    'product': result.get('product', ''),
                    'version': result.get('version', ''),
                    'data': result.get('data', '')[:200]
                }
                hosts.append(host)
            
            return hosts
        except shodan.APIError as e:
            logger.debug(f"Shodan search error: {e}")
        
        return []
    
    def get_api_info(self) -> Dict:
        """Get API usage information"""
        if not self.is_configured():
            return {}
        
        try:
            info = self.api.info()
            return {
                'query_credits': info.get('query_credits', 0),
                'scan_credits': info.get('scan_credits', 0),
                'plan': info.get('plan', 'Unknown')
            }
        except Exception as e:
            logger.debug(f"Error getting API info: {e}")
        
        return {}
