"""
Mock responses for the MISP REST API.
"""

SEARCH_EVENTS_RESPONSE = {
    "response": [
        {
            "Event": {
                "id": "42",
                "uuid": "5f8a2c3d-4b6e-7a8b-9c0d-1e2f3a4b5c6d",
                "info": "CVE-2023-25690 affects ubuntu-web",
                "threat_level_id": "1",
                "Attribute": [
                    {"type": "ip-dst", "value": "10.0.1.10"},
                    {"type": "vulnerability", "value": "CVE-2023-25690"},
                ],
            }
        }
    ]
}

CREATE_EVENT_RESPONSE = {
    "Event": {
        "id": "99",
        "uuid": "aabbccdd-1122-3344-5566-778899aabbcc",
        "info": "Test event from TIP",
        "threat_level_id": "1",
    }
}

ADD_ATTRIBUTE_RESPONSE = {
    "Attribute": {
        "id": "500",
        "event_id": "99",
        "type": "ip-dst",
        "value": "10.0.1.10",
    }
}

SEARCH_ATTRIBUTES_RESPONSE = {
    "response": {
        "Attribute": [
            {"id": "500", "type": "ip-dst", "value": "10.0.1.10", "event_id": "42"},
            {"id": "501", "type": "vulnerability", "value": "CVE-2023-25690", "event_id": "42"},
        ]
    }
}
