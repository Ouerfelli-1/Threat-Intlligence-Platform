"""
Unit tests for the Nmap Enumeration Module

This module tests the NmapEnumerator class functionality including:
- Initialization and configuration
- Config file loading
- Host scanning
- Service detection
- Result parsing and formatting
- CVE integration

Note: Tests mock nmap.PortScanner to avoid requiring nmap installation
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
import tempfile
import os


class TestNmapEnumeratorInit(unittest.TestCase):
    """Test NmapEnumerator initialization"""
    
    @patch('nmap.PortScanner')
    def test_default_initialization(self, mock_scanner):
        """Test default initialization parameters"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator()
        
        self.assertEqual(enumerator.threads, 5)
        self.assertEqual(enumerator.timeout, 300)
        self.assertEqual(enumerator.scan_type, 'default')
        self.assertEqual(enumerator.arguments, '-sV -sC')
    
    @patch('nmap.PortScanner')
    def test_fast_scan_type(self, mock_scanner):
        """Test fast scan type configuration"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator(scan_type='fast')
        
        self.assertEqual(enumerator.scan_type, 'fast')
        self.assertEqual(enumerator.arguments, '-sV -F')
    
    @patch('nmap.PortScanner')
    def test_full_scan_type(self, mock_scanner):
        """Test full scan type configuration"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator(scan_type='full')
        
        self.assertEqual(enumerator.scan_type, 'full')
        self.assertEqual(enumerator.arguments, '-sV -sC -p-')
    
    @patch('nmap.PortScanner')
    def test_custom_parameters(self, mock_scanner):
        """Test custom parameter initialization"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator(threads=10, timeout=600, scan_type='fast')
        
        self.assertEqual(enumerator.threads, 10)
        self.assertEqual(enumerator.timeout, 600)
    
    @patch('nmap.PortScanner')
    def test_cve_lookup_disabled(self, mock_scanner):
        """Test initialization with CVE lookup disabled"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator(check_cves=False)
        
        self.assertFalse(enumerator.check_cves)
        self.assertIsNone(enumerator.cve_lookup)


class TestNmapEnumeratorConfig(unittest.TestCase):
    """Test configuration loading"""
    
    @patch('nmap.PortScanner')
    def test_load_config_nonexistent_file(self, mock_scanner):
        """Test loading config from non-existent file"""
        from modules.nmap_enum import NmapEnumerator
        enumerator = NmapEnumerator(config_file='/nonexistent/path/config.ini')
        # Should not raise, just use defaults
        self.assertEqual(enumerator.threads, 5)
    
    @patch('nmap.PortScanner')
    def test_load_config_from_file(self, mock_scanner):
        """Test loading config from a valid config file"""
        config_content = """
[nmap]
scan_type = fast
threads = 8
timeout = 120

[nvd]
api_key = test_api_key_12345
max_results = 30
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(config_content)
            config_path = f.name
        
        try:
            from modules.nmap_enum import NmapEnumerator
            enumerator = NmapEnumerator(config_file=config_path)
            # Config values should be loaded
            self.assertEqual(enumerator.scan_type, 'fast')
            self.assertEqual(enumerator.threads, 8)
            self.assertEqual(enumerator.timeout, 120)
            self.assertEqual(enumerator.nvd_api_key, 'test_api_key_12345')
        finally:
            os.unlink(config_path)
    
    @patch('nmap.PortScanner')
    def test_is_configured_true(self, mock_scanner_class):
        """Test is_configured returns True when nmap is available"""
        from modules.nmap_enum import NmapEnumerator
        mock_scanner_class.return_value.nmap_version.return_value = (7, 94)
        
        enumerator = NmapEnumerator()
        
        self.assertTrue(enumerator.is_configured())
    
    @patch('nmap.PortScanner')
    def test_is_configured_false(self, mock_scanner_class):
        """Test is_configured returns False when nmap not available"""
        from modules.nmap_enum import NmapEnumerator
        mock_instance = MagicMock()
        mock_instance.nmap_version.side_effect = Exception("Nmap not installed")
        mock_scanner_class.return_value = mock_instance
        
        enumerator = NmapEnumerator()
        
        self.assertFalse(enumerator.is_configured())


class TestNmapEnumeratorHelpers(unittest.TestCase):
    """Test helper methods"""
    
    @patch('nmap.PortScanner')
    def setUp(self, mock_scanner):
        from modules.nmap_enum import NmapEnumerator
        self.enumerator = NmapEnumerator()
    
    def test_build_banner_full(self):
        """Test banner building with all fields"""
        port_info = {
            'product': 'Apache httpd',
            'version': '2.4.51',
            'extrainfo': 'Ubuntu'
        }
        
        banner = self.enumerator._build_banner(port_info)
        self.assertEqual(banner, 'Apache httpd 2.4.51 (Ubuntu)')
    
    def test_build_banner_partial(self):
        """Test banner building with partial fields"""
        port_info = {
            'product': 'nginx',
            'version': '1.18.0'
        }
        
        banner = self.enumerator._build_banner(port_info)
        self.assertEqual(banner, 'nginx 1.18.0')
    
    def test_build_banner_empty(self):
        """Test banner building with no fields"""
        port_info = {}
        
        banner = self.enumerator._build_banner(port_info)
        self.assertEqual(banner, '')
    
    def test_get_open_ports(self):
        """Test extracting open ports from scan result"""
        scan_result = {
            'open_ports': [22, 80, 443, 8080],
            'services': []
        }
        
        ports = self.enumerator.get_open_ports(scan_result)
        self.assertEqual(ports, [22, 80, 443, 8080])
    
    def test_get_open_ports_empty(self):
        """Test extracting ports from empty result"""
        scan_result = {}
        
        ports = self.enumerator.get_open_ports(scan_result)
        self.assertEqual(ports, [])
    
    def test_get_services(self):
        """Test extracting services from scan result"""
        scan_result = {
            'services': [
                {'port': 80, 'name': 'http', 'product': 'nginx'},
                {'port': 443, 'name': 'https', 'product': 'nginx'}
            ]
        }
        
        services = self.enumerator.get_services(scan_result)
        self.assertEqual(len(services), 2)
        self.assertEqual(services[0]['name'], 'http')
    
    def test_get_service_by_port(self):
        """Test getting service by specific port"""
        scan_result = {
            'services': [
                {'port': 22, 'name': 'ssh', 'product': 'OpenSSH'},
                {'port': 80, 'name': 'http', 'product': 'Apache'},
                {'port': 443, 'name': 'https', 'product': 'nginx'}
            ]
        }
        
        service = self.enumerator.get_service_by_port(scan_result, 80)
        self.assertIsNotNone(service)
        self.assertEqual(service['name'], 'http')
        self.assertEqual(service['product'], 'Apache')
    
    def test_get_service_by_port_not_found(self):
        """Test getting service for non-existent port"""
        scan_result = {
            'services': [
                {'port': 22, 'name': 'ssh'}
            ]
        }
        
        service = self.enumerator.get_service_by_port(scan_result, 8080)
        self.assertIsNone(service)


class TestNmapEnumeratorScanning(unittest.TestCase):
    """Test scanning functionality with mocks"""
    
    @patch('nmap.PortScanner')
    def setUp(self, mock_scanner):
        from modules.nmap_enum import NmapEnumerator
        self.enumerator = NmapEnumerator()
    
    def test_scan_host_success(self):
        """Test successful host scan"""
        # Setup mock
        mock_scanner = MagicMock()
        self.enumerator.nm = mock_scanner
        
        # Mock scan results
        mock_scanner.scan.return_value = None
        mock_scanner.all_hosts.return_value = ['192.168.1.1']
        
        # Mock host info
        mock_host_info = MagicMock()
        mock_host_info.state.return_value = 'up'
        mock_host_info.hostnames.return_value = [{'name': 'test.local'}]
        mock_host_info.all_protocols.return_value = ['tcp']
        mock_host_info.__getitem__ = lambda self, key: {
            'tcp': {
                22: {'state': 'open', 'name': 'ssh', 'product': 'OpenSSH', 'version': '8.2'},
                80: {'state': 'open', 'name': 'http', 'product': 'nginx', 'version': '1.18.0'}
            }
        }.get(key, {})
        
        mock_scanner.__getitem__ = lambda self, key: mock_host_info
        mock_scanner.scaninfo.return_value = {'tcp': {'elapsed': '5.00'}}
        
        # Perform scan
        result = self.enumerator._scan_host('192.168.1.1')
        
        # Verify scan was called
        mock_scanner.scan.assert_called_once()
        
        # Check result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['host'], '192.168.1.1')
        self.assertEqual(result['state'], 'up')
    
    def test_scan_host_no_results(self):
        """Test scan with no results"""
        mock_scanner = MagicMock()
        self.enumerator.nm = mock_scanner
        
        mock_scanner.scan.return_value = None
        mock_scanner.all_hosts.return_value = []
        
        result = self.enumerator._scan_host('192.168.1.1')
        
        self.assertIsNone(result)


class TestNmapEnumeratorFormatting(unittest.TestCase):
    """Test result formatting"""
    
    @patch('nmap.PortScanner')
    def setUp(self, mock_scanner):
        from modules.nmap_enum import NmapEnumerator
        self.enumerator = NmapEnumerator()
    
    def test_format_results(self):
        """Test formatting scan results"""
        scan_results = {
            '192.168.1.1': {
                'host': '192.168.1.1',
                'hostname': 'server.local',
                'state': 'up',
                'open_ports': [22, 80],
                'services': [
                    {'port': 22, 'protocol': 'tcp', 'name': 'ssh', 'banner': 'OpenSSH 8.2'},
                    {'port': 80, 'protocol': 'tcp', 'name': 'http', 'banner': 'nginx 1.18.0'}
                ],
                'os_detection': {'name': 'Linux 5.x', 'accuracy': '95'}
            }
        }
        
        formatted = self.enumerator.format_results(scan_results)
        
        # Check that key information is present
        self.assertIn('192.168.1.1', formatted)
        self.assertIn('server.local', formatted)
        self.assertIn('ssh', formatted)
        self.assertIn('http', formatted)
        self.assertIn('OpenSSH 8.2', formatted)
        self.assertIn('nginx 1.18.0', formatted)
        self.assertIn('Linux 5.x', formatted)
    
    def test_format_results_with_cves(self):
        """Test formatting scan results with CVE data"""
        scan_results = {
            '192.168.1.1': {
                'host': '192.168.1.1',
                'hostname': 'server.local',
                'state': 'up',
                'open_ports': [22],
                'services': [
                    {
                        'port': 22, 
                        'protocol': 'tcp', 
                        'name': 'ssh', 
                        'banner': 'OpenSSH 7.4',
                        'product': 'OpenSSH',
                        'version': '7.4',
                        'cves': [
                            {
                                'cve_id': 'CVE-2021-41617',
                                'severity': 'HIGH',
                                'cvss_score': 7.0,
                                'cvss_version': '3.1',
                                'description': 'Test vulnerability',
                                'published_date': '2021-09-26',
                                'references': []
                            }
                        ]
                    }
                ],
                'os_detection': None,
                'cve_summary': {'total': 1, 'critical': 0, 'high': 1, 'medium': 0, 'low': 0}
            }
        }
        
        formatted = self.enumerator.format_results(scan_results)
        
        # Check CVE information is present
        self.assertIn('CVE-2021-41617', formatted)
        self.assertIn('HIGH', formatted)
        self.assertIn('CVE Summary', formatted)


class TestNmapEnumeratorCVEMethods(unittest.TestCase):
    """Test CVE-related methods"""
    
    @patch('nmap.PortScanner')
    def setUp(self, mock_scanner):
        from modules.nmap_enum import NmapEnumerator
        self.enumerator = NmapEnumerator(check_cves=False)  # Disable actual CVE lookup
    
    def test_get_all_cves(self):
        """Test extracting all CVEs from scan results"""
        scan_results = {
            '192.168.1.1': {
                'services': [
                    {
                        'port': 22,
                        'name': 'ssh',
                        'product': 'OpenSSH',
                        'version': '7.4',
                        'cves': [
                            {'cve_id': 'CVE-2021-1', 'severity': 'HIGH', 'cvss_score': 7.5},
                            {'cve_id': 'CVE-2021-2', 'severity': 'MEDIUM', 'cvss_score': 5.0}
                        ]
                    }
                ]
            },
            '192.168.1.2': {
                'services': [
                    {
                        'port': 80,
                        'name': 'http',
                        'product': 'Apache',
                        'version': '2.4',
                        'cves': [
                            {'cve_id': 'CVE-2021-3', 'severity': 'CRITICAL', 'cvss_score': 9.8}
                        ]
                    }
                ]
            }
        }
        
        all_cves = self.enumerator.get_all_cves(scan_results)
        
        self.assertEqual(len(all_cves), 3)
        # Should be sorted by CVSS score (highest first)
        self.assertEqual(all_cves[0]['cve_id'], 'CVE-2021-3')
        self.assertEqual(all_cves[0]['cvss_score'], 9.8)
    
    def test_get_critical_cves(self):
        """Test getting only critical/high CVEs"""
        scan_results = {
            '192.168.1.1': {
                'services': [
                    {
                        'port': 22,
                        'name': 'ssh',
                        'product': 'OpenSSH',
                        'version': '7.4',
                        'cves': [
                            {'cve_id': 'CVE-2021-1', 'severity': 'CRITICAL', 'cvss_score': 9.0},
                            {'cve_id': 'CVE-2021-2', 'severity': 'LOW', 'cvss_score': 2.0},
                            {'cve_id': 'CVE-2021-3', 'severity': 'HIGH', 'cvss_score': 7.0}
                        ]
                    }
                ]
            }
        }
        
        critical_cves = self.enumerator.get_critical_cves(scan_results)
        
        self.assertEqual(len(critical_cves), 2)
        # Should only have CRITICAL and HIGH
        severities = [c['severity'] for c in critical_cves]
        self.assertIn('CRITICAL', severities)
        self.assertIn('HIGH', severities)
        self.assertNotIn('LOW', severities)
    
    def test_get_all_cves_empty(self):
        """Test get_all_cves with no CVEs"""
        scan_results = {
            '192.168.1.1': {
                'services': [{'port': 22, 'name': 'ssh', 'cves': []}]
            }
        }
        
        all_cves = self.enumerator.get_all_cves(scan_results)
        self.assertEqual(len(all_cves), 0)


class TestNmapEnumeratorIntegration(unittest.TestCase):
    """Integration tests - require actual nmap installation"""
    
    @pytest.mark.skipif(True, reason="Requires nmap installed and network access")
    def test_real_scan_localhost(self):
        """Test actual scan against localhost (skip by default)"""
        enumerator = NmapEnumerator(scan_type='fast')
        
        # Scan localhost
        results = enumerator.enumerate({'127.0.0.1'})
        
        # Should get some result
        self.assertIsInstance(results, dict)


# Run tests if executed directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main(verbosity=2)
