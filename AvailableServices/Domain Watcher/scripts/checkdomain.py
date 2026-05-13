import hashlib
import json
import re
import secrets

import dns.resolver
import requests
from bs4 import BeautifulSoup, Comment


# ---------------------------------------------------------------------------
#  DNS helpers
# ---------------------------------------------------------------------------


def query_record(name: str, rtype: str):
    """Return DNS answers for *name*/*rtype*, or an empty list on any failure."""
    records, _ = _query_record_typed(name, rtype)
    return records


def _query_record_typed(name: str, rtype: str) -> tuple:
    """Return (records, error_str | None).

    error_str is None on success or NOERROR-with-no-data.
    Values: 'NXDOMAIN', 'TIMEOUT', 'NO_NAMESERVERS', 'DNS_ERROR:<cls>', 'ERROR:<cls>'.
    """
    try:
        answers = dns.resolver.resolve(name, rtype, lifetime=5)
        return [r.to_text() for r in answers], None
    except dns.resolver.NXDOMAIN:
        return [], "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return [], None          # NOERROR with no data — not a hard error
    except dns.resolver.Timeout:
        return [], "TIMEOUT"
    except dns.resolver.NoNameservers:
        return [], "NO_NAMESERVERS"
    except dns.exception.DNSException as exc:
        return [], f"DNS_ERROR:{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return [], f"ERROR:{type(exc).__name__}"


def resolve_ips(hostname: str):
    return {
        "ipv4": query_record(hostname, "A"),
        "ipv6": query_record(hostname, "AAAA"),
    }


def _normalize_hostname(value: str) -> str:
    return value.strip().rstrip(".").lower()


def _normalize_records(records) -> list[str]:
    return sorted({_normalize_hostname(record) for record in records if record})


def _normalize_ip_map(ip_map: dict | None) -> dict:
    ip_map = ip_map or {}
    return {
        "ipv4": _normalize_records(ip_map.get("ipv4", [])),
        "ipv6": _normalize_records(ip_map.get("ipv6", [])),
    }


def _normalize_nameservers(nameservers: list[dict]) -> list[dict]:
    normalized = []
    for item in nameservers:
        host = _normalize_hostname(item.get("host", "")) if item.get("host") else ""
        if not host:
            continue
        normalized.append({
            "host": host,
            "ips": _normalize_ip_map(item.get("ips")),
        })
    return sorted(normalized, key=lambda entry: entry["host"])


def _normalize_domain_data(domain_data: dict) -> dict:
    normalized = dict(domain_data)
    normalized["main_ips"] = _normalize_ip_map(domain_data.get("main_ips"))
    normalized["nameservers"] = _normalize_nameservers(domain_data.get("nameservers", []))
    normalized["mx_records"] = sorted(domain_data.get("mx_records", []), key=lambda entry: (
        entry.get("priority", 0),
        entry.get("host") or "",
        bool(entry.get("null_mx", False)),
    ))
    return normalized


def _wildcard_signature(domain: str) -> dict:
    probe = f"{secrets.token_hex(8)}.{domain}"
    a, _ = _query_record_typed(probe, "A")
    aaaa, _ = _query_record_typed(probe, "AAAA")
    cname, _ = _query_record_typed(probe, "CNAME")
    return {
        "a_records": _normalize_records(a),
        "aaaa_records": _normalize_records(aaaa),
        "cname_target": next(iter(_normalize_records(cname)), None),
    }


def enrich_subdomain(subdomain: str, parent_domain: str) -> dict:
    a_raw, a_err = _query_record_typed(subdomain, "A")
    aaaa_raw, aaaa_err = _query_record_typed(subdomain, "AAAA")
    cname_raw, cname_err = _query_record_typed(subdomain, "CNAME")
    ns_raw, ns_err = _query_record_typed(subdomain, "NS")
    soa_raw, soa_err = _query_record_typed(subdomain, "SOA")

    a_records = _normalize_records(a_raw)
    aaaa_records = _normalize_records(aaaa_raw)
    cname_target = next(iter(_normalize_records(cname_raw)), None)
    ns_records = _normalize_records(ns_raw)
    soa_record = next(iter(_normalize_records(soa_raw)), None)

    # Aggregate meaningful errors (ignore NoAnswer == None)
    errors = [e for e in (a_err, aaaa_err, cname_err) if e and e != "NXDOMAIN"]
    # NXDOMAIN on A *and* AAAA is the authoritative "does not exist" signal
    nxdomain = a_err == "NXDOMAIN" and aaaa_err == "NXDOMAIN"
    if nxdomain:
        errors = ["NXDOMAIN"]
    last_error = errors[0] if errors else None

    wildcard_signature = _wildcard_signature(parent_domain)
    wildcard_match = (
        bool(a_records or aaaa_records or cname_target)
        and a_records == wildcard_signature["a_records"]
        and aaaa_records == wildcard_signature["aaaa_records"]
        and cname_target == wildcard_signature["cname_target"]
    )

    return {
        "subdomain": subdomain,
        "a_records_json": json.dumps(a_records),
        "aaaa_records_json": json.dumps(aaaa_records),
        "cname_target": cname_target,
        "ns_records_json": json.dumps(ns_records),
        "soa_record": soa_record,
        "is_delegated": bool(ns_records or soa_record),
        "is_resolving": bool(a_records or aaaa_records or cname_target),
        "wildcard_match": wildcard_match,
        "last_error": last_error,
    }


# ---------------------------------------------------------------------------
#  RDAP parsing helpers
# ---------------------------------------------------------------------------

def parse_rdap_events(events):
    creation_date = None
    expiration_date = None
    updated_date = None

    for event in events or []:
        action = event.get("eventAction")
        event_date = event.get("eventDate")

        if action == "registration":
            creation_date = event_date
        elif action == "expiration":
            expiration_date = event_date
        elif action == "last changed":
            updated_date = event_date

    return creation_date, expiration_date, updated_date


def extract_registrar(data):
    for entity in data.get("entities", []):
        if "registrar" in entity.get("roles", []):
            vcard = entity.get("vcardArray", [])
            if len(vcard) > 1:
                for item in vcard[1]:
                    if item[0] == "fn":
                        return item[3]
    return None


def extract_nameservers_from_rdap(data):
    result = []
    seen = set()

    for ns in data.get("nameservers", []):
        host = ns.get("ldhName")
        if not host:
            continue
        host = host.strip().rstrip(".").lower()
        if host and host not in seen:
            seen.add(host)
            result.append(host)

    return result


def parse_mx_records(domain: str):
    mx_records_raw = query_record(domain, "MX")
    mx_records = []

    for mx in mx_records_raw:
        parts = mx.split(maxsplit=1)
        if len(parts) != 2:
            mx_records.append({"raw": mx})
            continue

        priority, host = parts

        if host == ".":
            mx_records.append({
                "priority": int(priority),
                "host": None,
                "null_mx": True,
                "ips": {"ipv4": [], "ipv6": []}
            })
            continue

        host = host.rstrip(".").lower()
        ips = _normalize_ip_map(resolve_ips(host))
        mx_records.append({
            "priority": int(priority),
            "host": host,
            "null_mx": False,
            "ips": ips,
        })

    return sorted(mx_records, key=lambda entry: (
        entry.get("priority", 0),
        entry.get("host") or "",
        bool(entry.get("null_mx", False)),
    ))


# ---------------------------------------------------------------------------
#  Main RDAP + DNS fetch
# ---------------------------------------------------------------------------

def fetch_domain_data(domain: str) -> dict:
    rdap_url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
    response = requests.get(rdap_url, timeout=10)
    response.raise_for_status()
    rdap = response.json()

    registrar = extract_registrar(rdap)
    creation_date, expiration_date, updated_date = parse_rdap_events(rdap.get("events", []))
    status = rdap.get("status", [])

    a_records = _normalize_records(query_record(domain, "A"))
    aaaa_records = _normalize_records(query_record(domain, "AAAA"))

    nameserver_hosts = extract_nameservers_from_rdap(rdap)
    nameservers = []
    for host in nameserver_hosts:
        nameservers.append({
            "host": host,
            "ips": _normalize_ip_map(resolve_ips(host)),
        })

    main_ips = {
        "ipv4": a_records,
        "ipv6": aaaa_records
    }
    return _normalize_domain_data({
        "domain": domain,
        "registrar": registrar,
        "status": status,
        "creation_date": creation_date,
        "expiration_date": expiration_date,
        "updated_date": updated_date,
        "main_ips": main_ips,
        "nameservers": nameservers,
        "mx_records": parse_mx_records(domain)
    })


# ---------------------------------------------------------------------------
#  Content fetch & hashing
# ---------------------------------------------------------------------------

def fetch_and_hash_content(domain: str) -> tuple:
    """Fetch homepage HTML, strip dynamic content, compute SHA-256 hash."""
    html = ""
    MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5 MB cap
    for scheme in ("https", "http"):
        try:
            resp = requests.get(f"{scheme}://{domain}", timeout=15, allow_redirects=True,
                                headers={"User-Agent": "DomainWatch/1.0"}, stream=True)
            resp.raise_for_status()
            # Read in chunks to enforce the size cap regardless of Content-Length
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=65_536, decode_unicode=True):
                total += len(chunk)
                if total > MAX_CONTENT_SIZE:
                    resp.close()
                    return "", ""
                chunks.append(chunk)
            html = "".join(chunks)
            break
        except Exception:
            continue

    if not html:
        return "", ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    dynamic_attrs = ["nonce", "csrf", "token", "session", "data-csrf", "data-nonce"]
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if any(p in attr.lower() for p in dynamic_attrs):
                del tag[attr]

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, content_hash