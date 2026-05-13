"""Certificate Transparency enumeration module"""

import requests
import logging
from typing import Set
from modules.utils import clean_domain, is_valid_subdomain

logger = logging.getLogger('recon_tool')

class CertificateEnumerator:
    """Enumerate domains from Certificate Transparency logs"""
    
    def __init__(self):
        self.ct_sources = [
            'https://crt.sh/?q=%.{domain}&output=json',
            'https://certspotter.com/api/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names',
        ]
    
    def enumerate(self, domain: str) -> Set[str]:
        """Query CT logs for domain certificates"""
        logger.info("Querying Certificate Transparency logs...")
        
        domains = set()
        domains.add(domain)  # Add the main domain
        
        # Query crt.sh
        domains.update(self._query_crtsh(domain))
        
        # Query certspotter
        domains.update(self._query_certspotter(domain))
        
        logger.info(f"Found {len(domains)} unique domains from CT logs")
        return domains
    
    def _query_crtsh(self, domain: str) -> Set[str]:
        """Query crt.sh Certificate Transparency logs"""
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        domains = set()
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                
                for entry in data:
                    # Get common name
                    common_name = entry.get('common_name', '')
                    if common_name:
                        clean_cn = clean_domain(common_name.replace('*', ''))
                        if clean_cn and is_valid_subdomain(clean_cn, domain):
                            domains.add(clean_cn)
                    
                    # Get name_value which can contain multiple domains
                    name_value = entry.get('name_value', '')
                    for name in name_value.split('\n'):
                        clean_name = clean_domain(name.replace('*', ''))
                        if clean_name and is_valid_subdomain(clean_name, domain):
                            domains.add(clean_name)
                
                logger.debug(f"crt.sh found {len(domains)} domains")
        except requests.RequestException as e:
            logger.warning(f"Error querying crt.sh: {e}")
        except Exception as e:
            logger.warning(f"Error parsing crt.sh response: {e}")
        
        return domains
    
    def _query_certspotter(self, domain: str) -> Set[str]:
        """Query Certspotter API"""
        url = f"https://certspotter.com/api/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"
        domains = set()
        
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                data = response.json()
                
                for entry in data:
                    dns_names = entry.get('dns_names', [])
                    for name in dns_names:
                        clean_name = clean_domain(name.replace('*', ''))
                        if clean_name and is_valid_subdomain(clean_name, domain):
                            domains.add(clean_name)
                
                logger.debug(f"Certspotter found {len(domains)} domains")
        except requests.RequestException as e:
            logger.debug(f"Error querying Certspotter: {e}")
        except Exception as e:
            logger.debug(f"Error parsing Certspotter response: {e}")
        
        return domains
    
    def get_certificate_info(self, domain: str) -> dict:
        """Get detailed certificate information for a domain"""
        url = f"https://crt.sh/?q={domain}&output=json"
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                if data:
                    # Get the most recent certificate
                    cert = data[0]
                    return {
                        'issuer': cert.get('issuer_name', 'Unknown'),
                        'common_name': cert.get('common_name', ''),
                        'not_before': cert.get('not_before', ''),
                        'not_after': cert.get('not_after', ''),
                        'serial': cert.get('serial_number', ''),
                    }
        except Exception as e:
            logger.debug(f"Error getting certificate info for {domain}: {e}")
        
        return {}
