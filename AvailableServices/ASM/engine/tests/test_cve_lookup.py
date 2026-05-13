"""
Unit tests for the CVE Lookup Module

This module tests the CVELookup class functionality including:
- Initialization and configuration
- Config file loading
- CPE string building
- Service info parsing
- NVD API interaction (mocked)
- CVE result parsing
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
import tempfile
import os

# Import the module under test
from modules.cve_lookup import CVELookup, CVEResult


class TestCVELookupInit(unittest.TestCase):
    """Test CVELookup initialization"""
    
    def test_default_initialization(self):
        """Test default initialization without API key"""
        lookup = CVELookup()
        
        self.assertIsNone(lookup.api_key)
        self.assertEqual(lookup.threads, 3)
        self.assertIsNotNone(lookup.session)
    
    def test_initialization_with_api_key(self):
        """Test initialization with API key"""
        lookup = CVELookup(api_key='test-api-key')
        
        self.assertEqual(lookup.api_key, 'test-api-key')
        self.assertIn('apiKey', lookup.headers)
    
    def test_is_configured_with_key(self):
        """Test is_configured returns True with API key"""
        lookup = CVELookup(api_key='test-api-key')
        self.assertTrue(lookup.is_configured())
    
    def test_is_configured_without_key(self):
        """Test is_configured returns False without API key"""
        lookup = CVELookup()
        self.assertFalse(lookup.is_configured())


class TestCVELookupConfig(unittest.TestCase):
    """Test configuration loading"""
    
    def test_load_config_nonexistent_file(self):
        """Test loading config from non-existent file"""
        lookup = CVELookup(config_file='/nonexistent/path/config.ini')
        # Should not raise, just use defaults
        self.assertIsNone(lookup.api_key)
    
    def test_load_config_from_file(self):
        """Test loading config from a valid config file"""
        config_content = """
[nvd]
api_key = nvd_test_key_12345
max_results = 50
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            lookup = CVELookup(config_file=config_path)
            self.assertEqual(lookup.api_key, 'nvd_test_key_12345')
            self.assertEqual(lookup.max_results, 50)
        finally:
            os.unlink(config_path)
    
    def test_load_config_placeholder_key(self):
        """Test that placeholder API key is ignored"""
        config_content = """
[nvd]
api_key = YOUR_API_KEY_HERE
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            lookup = CVELookup(config_file=config_path)
            self.assertIsNone(lookup.api_key)
        finally:
            os.unlink(config_path)


class TestCPEStringBuilding(unittest.TestCase):
    """Test CPE string building"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    def test_build_cpe_with_version(self):
        """Test building CPE string with version"""
        cpe = self.lookup._build_cpe_string('apache', 'http_server', '2.4.51')
        
        self.assertEqual(cpe, 'cpe:2.3:a:apache:http_server:2.4.51:*:*:*:*:*:*:*')
    
    def test_build_cpe_without_version(self):
        """Test building CPE string without version"""
        cpe = self.lookup._build_cpe_string('nginx', 'nginx')
        
        self.assertEqual(cpe, 'cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*')
    
    def test_build_cpe_normalizes_vendor(self):
        """Test that vendor is normalized"""
        cpe = self.lookup._build_cpe_string('Apache Software', 'HTTP Server', '2.4')
        
        self.assertIn('apache_software', cpe)
        self.assertIn('http_server', cpe)


class TestServiceInfoParsing(unittest.TestCase):
    """Test service info parsing"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    def test_parse_service_with_cpe(self):
        """Test parsing service with CPE string (new 2.3 format)"""
        service = {
            'port': 22,
            'name': 'ssh',
            'product': 'OpenSSH',
            'version': '8.2',
            'cpe': 'cpe:2.3:a:openbsd:openssh:8.2:*:*:*:*:*:*:*'
        }
        
        parsed = self.lookup._parse_service_info(service)
        
        self.assertEqual(parsed['vendor'], 'openbsd')
        self.assertEqual(parsed['product'], 'openssh')
        self.assertEqual(parsed['version'], '8.2')
    
    def test_parse_service_apache(self):
        """Test parsing Apache service"""
        service = {
            'port': 80,
            'name': 'http',
            'product': 'Apache httpd',
            'version': '2.4.51'
        }
        
        parsed = self.lookup._parse_service_info(service)
        
        self.assertEqual(parsed['vendor'], 'apache')
        self.assertEqual(parsed['product'], 'http_server')
    
    def test_parse_service_nginx(self):
        """Test parsing nginx service"""
        service = {
            'port': 80,
            'name': 'http',
            'product': 'nginx',
            'version': '1.18.0'
        }
        
        parsed = self.lookup._parse_service_info(service)
        
        self.assertEqual(parsed['vendor'], 'nginx')
        self.assertEqual(parsed['product'], 'nginx')
    
    def test_parse_service_openssh(self):
        """Test parsing OpenSSH service"""
        service = {
            'port': 22,
            'name': 'ssh',
            'product': 'OpenSSH',
            'version': '7.4'
        }
        
        parsed = self.lookup._parse_service_info(service)
        
        self.assertEqual(parsed['vendor'], 'openbsd')
        self.assertEqual(parsed['product'], 'openssh')


class TestCVSSConversion(unittest.TestCase):
    """Test CVSS score to severity conversion"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    def test_cvss2_high(self):
        """Test HIGH severity conversion"""
        severity = self.lookup._cvss2_to_severity(8.5)
        self.assertEqual(severity, 'HIGH')
    
    def test_cvss2_medium(self):
        """Test MEDIUM severity conversion"""
        severity = self.lookup._cvss2_to_severity(5.0)
        self.assertEqual(severity, 'MEDIUM')
    
    def test_cvss2_low(self):
        """Test LOW severity conversion"""
        severity = self.lookup._cvss2_to_severity(2.5)
        self.assertEqual(severity, 'LOW')


class TestNVDResponseParsing(unittest.TestCase):
    """Test NVD API response parsing"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    def test_parse_empty_response(self):
        """Test parsing empty response"""
        data = {'vulnerabilities': []}
        
        results = self.lookup._parse_nvd_response(data, 'test')
        
        self.assertEqual(results, [])
    
    def test_parse_cve_with_cvss31(self):
        """Test parsing CVE with CVSS v3.1"""
        data = {
            'vulnerabilities': [{
                'cve': {
                    'id': 'CVE-2021-44228',
                    'descriptions': [{'lang': 'en', 'value': 'Log4j vulnerability'}],
                    'metrics': {
                        'cvssMetricV31': [{
                            'cvssData': {
                                'baseScore': 10.0,
                                'baseSeverity': 'CRITICAL'
                            },
                            'exploitabilityScore': 3.9,
                            'impactScore': 6.0
                        }]
                    },
                    'references': [{'url': 'https://example.com'}],
                    'published': '2021-12-10T00:00:00.000',
                    'lastModified': '2022-01-01T00:00:00.000'
                }
            }]
        }
        
        results = self.lookup._parse_nvd_response(data, 'log4j')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].cve_id, 'CVE-2021-44228')
        self.assertEqual(results[0].severity, 'CRITICAL')
        self.assertEqual(results[0].cvss_score, 10.0)
        self.assertEqual(results[0].cvss_version, '3.1')


class TestMultipleServicesCheck(unittest.TestCase):
    """Test checking multiple services"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    @patch.object(CVELookup, 'check_service_vulnerabilities')
    def test_check_multiple_services(self, mock_check):
        """Test checking multiple services"""
        mock_check.return_value = []
        
        services = [
            {'port': 22, 'name': 'ssh', 'product': 'OpenSSH', 'version': '7.4'},
            {'port': 80, 'name': 'http', 'product': 'Apache', 'version': '2.4'}
        ]
        
        results = self.lookup.check_multiple_services(services)
        
        self.assertEqual(mock_check.call_count, 2)


class TestCVEResult(unittest.TestCase):
    """Test CVEResult dataclass"""
    
    def test_cve_result_creation(self):
        """Test creating CVEResult"""
        cve = CVEResult(
            cve_id='CVE-2021-44228',
            description='Test vulnerability',
            severity='CRITICAL',
            cvss_score=10.0,
            cvss_version='3.1',
            published_date='2021-12-10',
            last_modified='2022-01-01',
            references=['https://example.com'],
            cpe_match='cpe:2.3:a:apache:log4j:*'
        )
        
        self.assertEqual(cve.cve_id, 'CVE-2021-44228')
        self.assertEqual(cve.severity, 'CRITICAL')
        self.assertEqual(cve.cvss_score, 10.0)


class TestNmapResultsCheck(unittest.TestCase):
    """Test checking Nmap scan results"""
    
    def setUp(self):
        self.lookup = CVELookup()
    
    @patch.object(CVELookup, 'check_multiple_services')
    def test_check_nmap_results(self, mock_check):
        """Test checking Nmap results for multiple hosts"""
        mock_check.return_value = {}
        
        nmap_results = {
            '192.168.1.1': {
                'services': [
                    {'port': 22, 'name': 'ssh', 'product': 'OpenSSH'}
                ]
            },
            '192.168.1.2': {
                'services': [
                    {'port': 80, 'name': 'http', 'product': 'nginx'}
                ]
            }
        }
        
        results = self.lookup.check_nmap_results(nmap_results)
        
        # Should be called twice (once per host)
        self.assertEqual(mock_check.call_count, 2)


# Run tests if executed directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(verbosity=2)
