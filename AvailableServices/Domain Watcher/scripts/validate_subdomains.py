"""Focused validation for subdomain DNS enrichment and wildcard detection.

Usage:
    # Run built-in self-tests only
    python scripts/validate_subdomains.py

    # Also run a live enrichment for a specific domain
    python scripts/validate_subdomains.py --domain example.com

Each test prints PASS / FAIL with a short reason.
"""

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.checkdomain import _normalize_domain_data, _query_record_typed, enrich_subdomain  # noqa: E402

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

_PASS = "PASS"
_FAIL = "FAIL"


def _check(label: str, condition: bool, reason: str = "") -> bool:
    status = _PASS if condition else _FAIL
    suffix = f" — {reason}" if reason else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


# ---------------------------------------------------------------------------
#  Test cases
# ---------------------------------------------------------------------------


def test_real_subdomain():
    """www.google.com should resolve with at least one A record and no error."""
    print("\n[1] Real public subdomain — www.google.com")
    result = enrich_subdomain("www.google.com", "google.com")

    a = json.loads(result["a_records_json"])
    ok = True
    ok &= _check("has A records", bool(a), f"got {a!r}")
    ok &= _check("is_resolving=True", result["is_resolving"])
    ok &= _check("last_error is None", result["last_error"] is None, f"got {result['last_error']!r}")
    ok &= _check("wildcard_match=False", not result["wildcard_match"])
    return ok


def test_nonexistent_subdomain():
    """totally-invalid-label.example.com should be NXDOMAIN."""
    print("\n[2] Non-existent subdomain — totally-invalid-label.example.com")
    result = enrich_subdomain("totally-invalid-label.example.com", "example.com")

    ok = True
    ok &= _check("is_resolving=False", not result["is_resolving"])
    ok &= _check("last_error set", result["last_error"] is not None, f"got {result['last_error']!r}")
    return ok


def test_typed_query_nxdomain():
    """_query_record_typed must return ('NXDOMAIN', []) for a guaranteed non-existent name."""
    print("\n[3] _query_record_typed NXDOMAIN detection")
    records, err = _query_record_typed("this-label-cannot-possibly-exist-xyzzy.invalid", "A")
    ok = True
    ok &= _check("records empty", records == [], f"got {records!r}")
    ok &= _check("error is NXDOMAIN or similar", err is not None, f"got {err!r}")
    return ok


def test_typed_query_noerror_nodata():
    """A valid domain queried for a record type it doesn't have should return ([], None)."""
    print("\n[4] _query_record_typed NOERROR/NODATA — A record for TXT-only label")
    # _dmarc.google.com has TXT but no A
    records, err = _query_record_typed("_dmarc.google.com", "A")
    ok = True
    ok &= _check("records empty", records == [], f"got {records!r}")
    ok &= _check("error is None (NoAnswer is not fatal)", err is None, f"got {err!r}")
    return ok


def test_delegated_zone():
    """A delegated child zone (e.g. docs.google.com) should have NS records."""
    print("\n[5] Delegated zone detection — docs.google.com")
    result = enrich_subdomain("docs.google.com", "google.com")
    ns = json.loads(result["ns_records_json"])
    # docs.google.com may or may not be delegated depending on Google's config.
    # We only assert that the flag is consistent with the NS list.
    ok = True
    delegated_flag = result["is_delegated"]
    ok &= _check(
        "is_delegated consistent with ns_records",
        (delegated_flag and bool(ns)) or (not delegated_flag and not ns),
        f"is_delegated={delegated_flag}, ns={ns!r}",
    )
    return ok


def test_enrichment_return_shape():
    """enrich_subdomain must always return all required keys."""
    print("\n[6] Return-shape completeness — any domain")
    required_keys = {
        "subdomain", "a_records_json", "aaaa_records_json", "cname_target",
        "ns_records_json", "soa_record", "is_delegated", "is_resolving",
        "wildcard_match", "last_error",
    }
    result = enrich_subdomain("mail.example.com", "example.com")
    missing = required_keys - result.keys()
    ok = _check("all required keys present", not missing, f"missing={missing!r}")
    return ok


def test_domain_data_normalization_stability():
    """Equivalent domain payloads with reordered answers must serialize identically."""
    print("\n[7] Domain-data normalization stability")
    payload_a = {
        "domain": "example.com",
        "registrar": "Example Registrar",
        "status": ["active"],
        "creation_date": "2024-01-01T00:00:00Z",
        "expiration_date": "2027-01-01T00:00:00Z",
        "updated_date": "2025-01-01T00:00:00Z",
        "main_ips": {
            "ipv4": ["172.67.179.99", "104.21.88.130"],
            "ipv6": ["2606:4700:3033::6815:5882", "2606:4700:3035::ac43:b363"],
        },
        "nameservers": [
            {"host": "b.ns.example.net", "ips": {"ipv4": ["2.2.2.2", "1.1.1.1"], "ipv6": []}},
            {"host": "a.ns.example.net", "ips": {"ipv4": ["4.4.4.4", "3.3.3.3"], "ipv6": []}},
        ],
        "mx_records": [
            {"priority": 20, "host": "mx2.example.com", "null_mx": False, "ips": {"ipv4": ["8.8.8.8"], "ipv6": []}},
            {"priority": 10, "host": "mx1.example.com", "null_mx": False, "ips": {"ipv4": ["6.6.6.6", "5.5.5.5"], "ipv6": []}},
        ],
    }
    payload_b = {
        "domain": "example.com",
        "registrar": "Example Registrar",
        "status": ["active"],
        "creation_date": "2024-01-01T00:00:00Z",
        "expiration_date": "2027-01-01T00:00:00Z",
        "updated_date": "2025-01-01T00:00:00Z",
        "main_ips": {
            "ipv4": ["104.21.88.130", "172.67.179.99"],
            "ipv6": ["2606:4700:3035::ac43:b363", "2606:4700:3033::6815:5882"],
        },
        "nameservers": [
            {"host": "a.ns.example.net", "ips": {"ipv4": ["3.3.3.3", "4.4.4.4"], "ipv6": []}},
            {"host": "b.ns.example.net", "ips": {"ipv4": ["1.1.1.1", "2.2.2.2"], "ipv6": []}},
        ],
        "mx_records": [
            {"priority": 10, "host": "mx1.example.com", "null_mx": False, "ips": {"ipv4": ["5.5.5.5", "6.6.6.6"], "ipv6": []}},
            {"priority": 20, "host": "mx2.example.com", "null_mx": False, "ips": {"ipv4": ["8.8.8.8"], "ipv6": []}},
        ],
    }

    normalized_a = json.dumps(_normalize_domain_data(payload_a), sort_keys=True)
    normalized_b = json.dumps(_normalize_domain_data(payload_b), sort_keys=True)
    return _check("normalized JSON matches", normalized_a == normalized_b)


def test_live(domain: str):
    """Live enrichment — discover crt.sh subdomains and enrich first 5."""
    print(f"\n[LIVE] Enriching first 5 subdomains of {domain} via crt.sh + DNS")
    from scripts.subdomains import get_subdomains_from_crtsh

    subs = get_subdomains_from_crtsh(domain)
    if not subs:
        print("  No subdomains returned by crt.sh — skipping live test.")
        return True

    sample = subs[:5]
    ok = True
    for sub in sample:
        result = enrich_subdomain(sub, domain)
        a = json.loads(result["a_records_json"])
        ns = json.loads(result["ns_records_json"])
        flag_str = " ".join(
            f for f, v in [
                ("resolving", result["is_resolving"]),
                ("delegated", result["is_delegated"]),
                ("wildcard", result["wildcard_match"]),
            ] if v
        ) or "no-dns-answer"
        err_str = f" error={result['last_error']}" if result["last_error"] else ""
        print(f"    {sub:<50} [{flag_str}]{err_str}")
        if a:
            print(f"      A: {', '.join(a)}")
        if ns:
            print(f"      NS: {', '.join(ns)}")

    return ok


# ---------------------------------------------------------------------------
#  Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate subdomain enrichment logic.")
    parser.add_argument("--domain", metavar="DOMAIN", help="Also run live enrichment for this domain.")
    args = parser.parse_args()

    print("=" * 60)
    print("  DomainWatch — Subdomain Enrichment Validation")
    print("=" * 60)

    results = [
        test_real_subdomain(),
        test_nonexistent_subdomain(),
        test_typed_query_nxdomain(),
        test_typed_query_noerror_nodata(),
        test_delegated_zone(),
        test_enrichment_return_shape(),
        test_domain_data_normalization_stability(),
    ]

    if args.domain:
        results.append(test_live(args.domain))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Result: {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
