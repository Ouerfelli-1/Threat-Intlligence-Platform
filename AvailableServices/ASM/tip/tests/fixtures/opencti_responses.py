"""
Mock responses for the OpenCTI GraphQL API.
"""

CREATE_INDICATOR_RESPONSE = {
    "data": {
        "indicatorAdd": {
            "id": "indicator--aaa-bbb-ccc",
            "name": "IP: 10.0.1.10",
            "pattern": "[ipv4-addr:value = '10.0.1.10']",
            "pattern_type": "stix",
        }
    }
}

CREATE_VULNERABILITY_RESPONSE = {
    "data": {
        "vulnerabilityAdd": {
            "id": "vulnerability--ddd-eee-fff",
            "name": "CVE-2023-25690",
        }
    }
}

CREATE_REPORT_RESPONSE = {
    "data": {
        "reportAdd": {
            "id": "report--111-222-333",
            "name": "Test report from TIP",
        }
    }
}

SEARCH_INDICATORS_RESPONSE = {
    "data": {
        "indicators": {
            "edges": [
                {
                    "node": {
                        "id": "indicator--aaa-bbb-ccc",
                        "name": "IP: 10.0.1.10",
                        "pattern": "[ipv4-addr:value = '10.0.1.10']",
                    }
                }
            ]
        }
    }
}

CREATE_RELATIONSHIP_RESPONSE = {
    "data": {
        "stixCoreRelationshipAdd": {
            "id": "relationship--xxx-yyy-zzz",
            "relationship_type": "indicates",
        }
    }
}
