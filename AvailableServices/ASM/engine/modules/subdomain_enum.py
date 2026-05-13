"""Subdomain enumeration module"""

import subprocess
import requests
import logging
from typing import Set, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from modules.utils import clean_domain, is_valid_subdomain, resolve_domain

# Suppress SSL warnings for specific sources with certificate issues
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('recon_tool')

class SubdomainEnumerator:
    """Enumerate subdomains using various techniques"""
    
    def __init__(self, domain: str, threads: int = 10):
        self.domain = clean_domain(domain)
        self.threads = threads
        self.subdomains = set()
    
    def passive_enum(self) -> Set[str]:
        """Perform passive subdomain enumeration"""
        logger.info("Starting passive enumeration...")
        
        # Combine results from multiple sources
        sources = [
            self._enum_crtsh,
            self._enum_hackertarget,
            self._enum_threatcrowd,
            self._enum_virustotal,
            self._enum_dnsdumpster,
            self._enum_rapiddns,
            self._enum_wayback,
            self._enum_anubisdb,
            self._enum_urlscan,
            self._enum_github,
            self._enum_commoncrawl,
            self._enum_censys,
        ]
        
        for source in sources:
            try:
                found = source()
                self.subdomains.update(found)
                logger.debug(f"Source {source.__name__} found {len(found)} domains")
            except Exception as e:
                logger.warning(f"Error in {source.__name__}: {e}")
        
        return self.subdomains
    
    def _enum_crtsh(self) -> Set[str]:
        """Query crt.sh for subdomains"""
        url = f"https://crt.sh/?q=%.{self.domain}&output=json"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                for entry in data:
                    name = entry.get('name_value', '')
                    # Handle wildcard and newline separated entries
                    for domain in name.split('\n'):
                        domain = clean_domain(domain.replace('*', ''))
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                return domains
        except Exception as e:
            logger.debug(f"crt.sh error: {e}")
        return set()
    
    def _enum_hackertarget(self) -> Set[str]:
        """Query HackerTarget API"""
        url = f"https://api.hackertarget.com/hostsearch/?q={self.domain}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                domains = set()
                for line in response.text.split('\n'):
                    if line and ',' in line:
                        domain = clean_domain(line.split(',')[0])
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                return domains
        except Exception as e:
            logger.debug(f"HackerTarget error: {e}")
        return set()
    
    def _enum_threatcrowd(self) -> Set[str]:
        """Query ThreatCrowd API"""
        url = f"https://www.threatcrowd.org/searchApi/v2/domain/report/?domain={self.domain}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            # Disable SSL verification for ThreatCrowd due to cert issues
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            if response.status_code == 200:
                data = response.json()
                subdomains = data.get('subdomains', [])
                domains = set()
                for domain in subdomains:
                    domain = clean_domain(domain)
                    if domain and is_valid_subdomain(domain, self.domain):
                        domains.add(domain)
                return domains
        except requests.exceptions.SSLError:
            logger.debug(f"ThreatCrowd SSL error - skipping")
        except Exception as e:
            logger.debug(f"ThreatCrowd error: {e}")
        return set()
    
    def _enum_virustotal(self) -> Set[str]:
        """Query VirusTotal (public endpoint - limited)"""
        # Note: This is a basic implementation
        # For better results, use API key in config
        url = f"https://www.virustotal.com/ui/domains/{self.domain}/subdomains"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                for item in data.get('data', []):
                    domain = clean_domain(item.get('id', ''))
                    if domain and is_valid_subdomain(domain, self.domain):
                        domains.add(domain)
                return domains
        except Exception as e:
            logger.debug(f"VirusTotal error: {e}")
        return set()
    
    def active_enum(self, wordlist: str) -> Set[str]:
        """Perform active subdomain enumeration using wordlist"""
        logger.info(f"Starting active enumeration with wordlist: {wordlist}")
        
        try:
            with open(wordlist, 'r') as f:
                words = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"Wordlist not found: {wordlist}")
            return set()
        
        found_domains = set()
        
        # Use thread pool for concurrent DNS resolution
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = []
            for word in words:
                subdomain = f"{word}.{self.domain}"
                futures.append(executor.submit(self._check_subdomain, subdomain))
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    found_domains.add(result)
                    logger.debug(f"Found: {result}")
        
        return found_domains
    
    def _check_subdomain(self, subdomain: str) -> str:
        """Check if subdomain resolves"""
        if resolve_domain(subdomain):
            return subdomain
        return None
    
    def brute_with_ffuf(self, wordlist: str) -> Set[str]:
        """Use ffuf for subdomain bruteforcing"""
        logger.info("Using ffuf for subdomain enumeration...")
        
        try:
            # Check if ffuf is available
            subprocess.run(['ffuf', '-h'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffuf not found. Install with: go install github.com/ffuf/ffuf@latest")
            return set()
        
        output_file = f"ffuf_output_{self.domain}.json"
        cmd = [
            'ffuf',
            '-w', wordlist,
            '-u', f'http://FUZZ.{self.domain}',
            '-mc', '200,301,302,403',
            '-o', output_file,
            '-of', 'json',
            '-t', str(self.threads),
            '-sf'  # Stop on errors
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=300)
            
            # Parse ffuf output
            import json
            with open(output_file, 'r') as f:
                data = json.load(f)
                domains = set()
                for result in data.get('results', []):
                    subdomain = f"{result['input']['FUZZ']}.{self.domain}"
                    domains.add(subdomain)
                return domains
        except Exception as e:
            logger.warning(f"ffuf execution error: {e}")
        
        return set()
    
    def _enum_dnsdumpster(self) -> Set[str]:
        """Query DNSDumpster for subdomains"""
        try:
            from bs4 import BeautifulSoup
            import time
            session = requests.Session()
            
            # Get CSRF token with retry
            url = 'https://dnsdumpster.com/'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = session.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple methods to find CSRF token
            csrf_token = None
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            if csrf_input and 'value' in csrf_input.attrs:
                csrf_token = csrf_input['value']
            
            if not csrf_token:
                logger.debug("DNSDumpster: CSRF token not found")
                return set()
            
            # Small delay to avoid rate limiting
            time.sleep(1)
            
            # Submit form
            data = {
                'csrfmiddlewaretoken': csrf_token,
                'targetip': self.domain,
                'user': 'free'
            }
            headers['Referer'] = url
            headers['Cookie'] = f"csrftoken={csrf_token}"
            
            response = session.post(url, data=data, headers=headers, timeout=25)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse results - multiple table formats
            domains = set()
            
            # Method 1: Standard table rows
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if cells and len(cells) >= 1:
                    domain_text = cells[0].get_text(strip=True)
                    if domain_text:
                        domain = clean_domain(domain_text.split()[0])
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
            
            # Method 2: Look for specific DNS record table
            for td in soup.find_all('td', class_='col-md-4'):
                domain_text = td.get_text(strip=True)
                if domain_text:
                    domain = clean_domain(domain_text.split()[0])
                    if domain and is_valid_subdomain(domain, self.domain):
                        domains.add(domain)
            
            return domains
        except ImportError:
            logger.debug("BeautifulSoup not installed. Install with: pip install beautifulsoup4")
        except Exception as e:
            logger.debug(f"DNSDumpster error: {e}")
        return set()
    
    def _enum_rapiddns(self) -> Set[str]:
        """Query RapidDNS for subdomains"""
        url = f"https://rapiddns.io/subdomain/{self.domain}?full=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            from bs4 import BeautifulSoup
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                domains = set()
                
                # Find all table rows
                for row in soup.find_all('tr'):
                    cells = row.find_all('td')
                    if cells and len(cells) >= 1:
                        domain_text = cells[0].get_text(strip=True)
                        domain = clean_domain(domain_text)
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                
                return domains
        except ImportError:
            logger.debug("BeautifulSoup not installed")
        except Exception as e:
            logger.debug(f"RapidDNS error: {e}")
        return set()
    
    def _enum_wayback(self) -> Set[str]:
        """Query Wayback Machine CDX API"""
        url = f"http://web.archive.org/cdx/search/cdx?url=*.{self.domain}/*&output=json&fl=original&collapse=urlkey&limit=1000"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            # Increase timeout and add retry logic
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                
                for item in data[1:]:  # Skip header
                    if item:
                        url_str = item[0]
                        # Extract domain from URL
                        from urllib.parse import urlparse
                        try:
                            parsed = urlparse(url_str if url_str.startswith('http') else f'http://{url_str}')
                            domain = clean_domain(parsed.netloc)
                            if domain and is_valid_subdomain(domain, self.domain):
                                domains.add(domain)
                        except:
                            continue
                
                return domains
        except requests.exceptions.Timeout:
            logger.debug(f"Wayback Machine timeout - try reducing scope or run again later")
        except Exception as e:
            logger.debug(f"Wayback Machine error: {e}")
        return set()
    
    def _enum_anubisdb(self) -> Set[str]:
        """Query Anubis-DB for subdomains"""
        url = f"https://jldc.me/anubis/subdomains/{self.domain}"
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                
                for subdomain in data:
                    domain = clean_domain(subdomain)
                    if domain and is_valid_subdomain(domain, self.domain):
                        domains.add(domain)
                
                return domains
        except Exception as e:
            logger.debug(f"Anubis-DB error: {e}")
        return set()
    
    def _enum_urlscan(self) -> Set[str]:
        """Query URLScan.io for domains"""
        url = f"https://urlscan.io/api/v1/search/?q=domain:{self.domain}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                
                for result in data.get('results', []):
                    page_domain = result.get('page', {}).get('domain', '')
                    if page_domain:
                        domain = clean_domain(page_domain)
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                    
                    # Also check task domain
                    task_domain = result.get('task', {}).get('domain', '')
                    if task_domain:
                        domain = clean_domain(task_domain)
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                
                return domains
        except Exception as e:
            logger.debug(f"URLScan.io error: {e}")
        return set()
    
    def _enum_github(self) -> Set[str]:
        """Search GitHub for domain references"""
        # Basic implementation - requires API key for better results
        import configparser
        from pathlib import Path
        
        config_path = Path('config.ini')
        api_token = None
        
        if config_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read('config.ini')
                if 'github' in config:
                    api_token = config['github'].get('api_token')
            except Exception:
                pass
        
        if not api_token or api_token == 'YOUR_GITHUB_TOKEN_HERE':
            logger.debug("GitHub API token not configured, skipping")
            return set()
        
        url = f"https://api.github.com/search/code?q={self.domain}+in:file"
        headers = {
            'Authorization': f'token {api_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                domains = set()
                
                # This is basic - would need more sophisticated parsing
                import re
                subdomain_pattern = re.compile(rf'([a-zA-Z0-9][-a-zA-Z0-9]*\.)*{re.escape(self.domain)}')
                
                for item in data.get('items', [])[:10]:  # Limit to 10 files
                    # Would need to fetch file content for thorough search
                    text = item.get('name', '') + ' ' + item.get('path', '')
                    matches = subdomain_pattern.findall(text)
                    for match in matches:
                        domain = clean_domain(match[0] if isinstance(match, tuple) else match)
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                
                return domains
        except Exception as e:
            logger.debug(f"GitHub search error: {e}")
        return set()
    
    def _enum_commoncrawl(self) -> Set[str]:
        """Query CommonCrawl index"""
        # Get latest index
        try:
            index_response = requests.get('https://index.commoncrawl.org/collinfo.json', timeout=15)
            if index_response.status_code == 200:
                indexes = index_response.json()
                if indexes:
                    latest_index = indexes[0]['cdx-api']
                    
                    # Query index
                    url = f"{latest_index}?url=*.{self.domain}&output=json&fl=url"
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        domains = set()
                        from urllib.parse import urlparse
                        
                        for line in response.text.split('\n'):
                            if line.strip():
                                try:
                                    data = requests.utils.json.loads(line)
                                    url_str = data.get('url', '')
                                    if url_str:
                                        parsed = urlparse(url_str)
                                        domain = clean_domain(parsed.netloc)
                                        if domain and is_valid_subdomain(domain, self.domain):
                                            domains.add(domain)
                                except:
                                    pass
                        
                        return domains
        except Exception as e:
            logger.debug(f"CommonCrawl error: {e}")
        return set()
    
    def _enum_censys(self) -> Set[str]:
        """Query Censys Platform API v3 using PAT Bearer authentication"""
        import configparser
        from pathlib import Path
        import os
        
        # Get config path relative to this file's location (engine/modules -> engine/config.ini)
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        config_path = current_dir.parent / 'config.ini'
        pat = None
        enabled = False
        
        if config_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(config_path)
                if 'censys' in config:
                    # Check if Censys is enabled (requires Starter/Enterprise plan)
                    enabled = config['censys'].get('enabled', 'false').lower() == 'true'
                    pat = config['censys'].get('pat')
            except Exception as e:
                logger.debug(f"Censys: Config load error: {e}")
        
        if not enabled:
            logger.debug("Censys: Disabled in config (requires Starter/Enterprise plan)")
            return set()
        
        if not pat or pat == 'YOUR_CENSYS_PAT_HERE':
            logger.debug("Censys PAT not configured, skipping")
            return set()
        
        logger.info(f"Censys: Querying hosts for {self.domain}...")
        # Censys Platform API v3 - search query endpoint
        url = "https://api.platform.censys.io/v3/global/search/query"
        headers = {
            'Authorization': f'Bearer {pat}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        # POST request with query body - search for hosts with this domain in DNS names
        body = {
            'query': f'dns.names: {self.domain}',
            'page_size': 100
        }
        
        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            logger.debug(f"Censys: Response status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                domains = set()
                
                # Handle v3 response format - hosts with DNS names
                hits = data.get('hits', []) or data.get('result', {}).get('hits', [])
                for host in hits:
                    # Get DNS names from host
                    dns_names = host.get('dns', {}).get('names', [])
                    for name in dns_names:
                        domain = clean_domain(name.replace('*', ''))
                        if domain and is_valid_subdomain(domain, self.domain):
                            domains.add(domain)
                    # Also check services for hostnames
                    services = host.get('services', [])
                    for svc in services:
                        cert = svc.get('tls', {}).get('certificate', {})
                        names = cert.get('names', [])
                        for name in names:
                            domain = clean_domain(name.replace('*', ''))
                            if domain and is_valid_subdomain(domain, self.domain):
                                domains.add(domain)
                
                logger.info(f"Censys: Found {len(domains)} domains")
                return domains
            else:
                logger.debug(f"Censys: Error response: {response.text[:300]}")
        except Exception as e:
            logger.debug(f"Censys error: {e}")
        return set()
