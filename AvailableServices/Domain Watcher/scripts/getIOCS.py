import json
import os
from pathlib import Path

from OTXv2 import OTXv2, IndicatorTypes


def _load_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_iocs(domain: str) -> list[dict]:
    """Fetch IOCs (pulses, IPs, URLs, hashes) from AlienVault OTX."""
    _MAX_IOC_VALUE_LEN = 2048  # cap individual IOC values
    _MAX_IOCS = 5000  # cap total IOCs per domain

    config = _load_config()
    api_key = os.environ.get("DOMAINWATCH_OTX_API_KEY") or config.get("otx_api_key", "")
    if not api_key:
        return []

    otx = OTXv2(api_key)

    try:
        result = otx.get_indicator_details_full(IndicatorTypes.DOMAIN, domain)
    except Exception:
        return []

    iocs = []
    seen = set()

    def _add(ioc_type: str, value: str):
        if not value or len(iocs) >= _MAX_IOCS:
            return
        value = value[:_MAX_IOC_VALUE_LEN]
        key = (ioc_type, value)
        if key not in seen:
            seen.add(key)
            iocs.append({"ioc_value": value, "ioc_type": ioc_type})

    # Pulses
    general = result.get("general", {})
    for pulse in general.get("pulse_info", {}).get("pulses", []):
        _add("pulse", pulse.get("id", ""))

    # Passive DNS IPs
    for record in result.get("passive_dns", {}).get("passive_dns", []):
        _add("ip", record.get("address", ""))

    # URLs
    for entry in result.get("url_list", {}).get("url_list", []):
        _add("url", entry.get("url", ""))

    # Malware hashes
    for entry in result.get("malware", {}).get("data", []):
        _add("hash", entry.get("hash", ""))

    return iocs
