import requests

_MAX_CT_ENTRIES = 5000  # cap to prevent memory issues on popular domains


def get_subdomains_from_crtsh(domain: str) -> list[str]:
    """Query certificate transparency logs via crt.sh for subdomains."""
    try:
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return []
    except Exception:
        return []

    found = set()

    for entry in data[:_MAX_CT_ENTRIES]:
        name_value = entry.get("name_value", "")
        for name in name_value.splitlines():
            name = name.strip().lower()
            if name.endswith("." + domain) and name != domain:
                found.add(name)

    return sorted(found)


