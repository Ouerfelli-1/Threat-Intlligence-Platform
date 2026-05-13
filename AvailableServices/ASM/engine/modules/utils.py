"""Utility functions for the recon tool"""

import logging
import re
import socket
from typing import Optional

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger('recon_tool')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ch.setFormatter(formatter)
    
    logger.addHandler(ch)
    return logger

def validate_target(target: str) -> bool:
    """Validate if target is a valid domain or IP"""
    # Check if it's a valid domain
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    
    # Check if it's a valid IP
    ip_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    return bool(domain_pattern.match(target) or ip_pattern.match(target))

def is_valid_subdomain(domain: str, base_domain: str) -> bool:
    """Check if a subdomain is valid for the base domain"""
    return domain.endswith(base_domain) or domain == base_domain

def resolve_domain(domain: str) -> Optional[str]:
    """Resolve domain to IP address"""
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror:
        return None

def clean_domain(domain: str) -> str:
    """Clean and normalize domain name"""
    domain = domain.lower().strip()
    # Remove common prefixes
    domain = domain.replace('http://', '').replace('https://', '')
    domain = domain.replace('www.', '')
    # Remove trailing slashes and ports
    domain = domain.split('/')[0].split(':')[0]
    return domain
