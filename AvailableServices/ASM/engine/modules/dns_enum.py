"""DNS enumeration module"""

import dns.resolver
import dns.reversename
import logging
from typing import Dict, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger('recon_tool')

class DNSEnumerator:
    """Enumerate DNS records for domains"""
    
    # DNS record types to query
    RECORD_TYPES = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SOA', 'PTR']
    
    def __init__(self, threads: int = 10):
        self.threads = threads
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 5
    
    def enumerate(self, domains: Set[str]) -> Dict[str, Dict]:
        """Enumerate DNS records for a list of domains"""
        logger.info(f"Enumerating DNS records for {len(domains)} domains...")
        
        dns_data = {}
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._query_domain, domain): domain for domain in domains}
            
            completed = 0
            for future in as_completed(futures):
                domain = futures[future]
                try:
                    result = future.result()
                    if result:
                        dns_data[domain] = result
                    completed += 1
                    if completed % 10 == 0:
                        logger.debug(f"Progress: {completed}/{len(domains)} domains processed")
                except Exception as e:
                    logger.debug(f"Error processing {domain}: {e}")
        
        logger.info(f"DNS enumeration completed for {len(dns_data)} domains")
        return dns_data
    
    def _query_domain(self, domain: str) -> Dict:
        """Query all DNS record types for a domain"""
        records = {
            'domain': domain,
            'A': [],
            'AAAA': [],
            'CNAME': [],
            'MX': [],
            'NS': [],
            'TXT': [],
            'SOA': None,
            'PTR': []
        }
        
        # Query each record type
        for record_type in self.RECORD_TYPES:
            try:
                if record_type == 'PTR':
                    # PTR records need special handling
                    a_records = records.get('A', [])
                    for ip in a_records:
                        ptr = self._query_ptr(ip)
                        if ptr:
                            records['PTR'].extend(ptr)
                else:
                    answers = self.resolver.resolve(domain, record_type)
                    
                    if record_type == 'A':
                        records['A'] = [str(rdata) for rdata in answers]
                    elif record_type == 'AAAA':
                        records['AAAA'] = [str(rdata) for rdata in answers]
                    elif record_type == 'CNAME':
                        records['CNAME'] = [str(rdata.target) for rdata in answers]
                    elif record_type == 'MX':
                        records['MX'] = [
                            {'priority': rdata.preference, 'server': str(rdata.exchange)}
                            for rdata in answers
                        ]
                    elif record_type == 'NS':
                        records['NS'] = [str(rdata.target) for rdata in answers]
                    elif record_type == 'TXT':
                        records['TXT'] = [str(rdata) for rdata in answers]
                    elif record_type == 'SOA':
                        if answers:
                            soa = answers[0]
                            records['SOA'] = {
                                'mname': str(soa.mname),
                                'rname': str(soa.rname),
                                'serial': soa.serial,
                                'refresh': soa.refresh,
                                'retry': soa.retry,
                                'expire': soa.expire,
                                'minimum': soa.minimum
                            }
            except dns.resolver.NoAnswer:
                logger.debug(f"No {record_type} record for {domain}")
            except dns.resolver.NXDOMAIN:
                logger.debug(f"Domain does not exist: {domain}")
                return None
            except dns.resolver.NoNameservers:
                logger.debug(f"No nameservers for {domain}")
            except dns.exception.Timeout:
                logger.debug(f"Timeout querying {record_type} for {domain}")
            except Exception as e:
                logger.debug(f"Error querying {record_type} for {domain}: {e}")
        
        return records
    
    def _query_ptr(self, ip: str) -> List[str]:
        """Query PTR record for an IP address"""
        try:
            rev_name = dns.reversename.from_address(ip)
            answers = self.resolver.resolve(rev_name, 'PTR')
            return [str(rdata.target) for rdata in answers]
        except Exception as e:
            logger.debug(f"PTR query failed for {ip}: {e}")
            return []
    
    def get_ip_addresses(self, dns_data: Dict) -> Set[str]:
        """Extract all IP addresses from DNS data"""
        ips = set()
        for domain, records in dns_data.items():
            if records and 'A' in records:
                ips.update(records['A'])
            if records and 'AAAA' in records:
                ips.update(records['AAAA'])
        return ips
