import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.database import get_db
from Notify.sendmail import send_alert
from scripts.checkdomain import (
    _normalize_domain_data,
    _normalize_ip_map,
    _normalize_records,
    enrich_subdomain,
    fetch_and_hash_content,
    fetch_domain_data,
)
from scripts.getIOCS import get_iocs
from scripts.subdomains import get_subdomains_from_crtsh
from scripts.takescreenshot import take_screenshot


# ---------------------------------------------------------------------------
#  Single-domain monitoring pipeline
# ---------------------------------------------------------------------------


def monitor_domain(domain_name: str, domain_id: int, case_id: str):
    """Run the full monitoring pipeline for a single domain."""
    now = datetime.now().isoformat()

    # ---- 1. Fetch DNS / WHOIS records ----
    try:
        domain_data = fetch_domain_data(domain_name)
        new_details_json = json.dumps(domain_data, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[DomainWatch] RDAP failed for {domain_name}: {e}, falling back to DNS")
        from scripts.checkdomain import query_record, resolve_ips, parse_mx_records
        a_records = _normalize_records(query_record(domain_name, "A"))
        aaaa_records = _normalize_records(query_record(domain_name, "AAAA"))
        ns_records = _normalize_records(query_record(domain_name, "NS"))
        nameservers = []
        for ns in ns_records:
            host = ns.rstrip(".").lower()
            nameservers.append({"host": host, "ips": _normalize_ip_map(resolve_ips(host))})
        domain_data = _normalize_domain_data({
            "domain": domain_name,
            "main_ips": {"ipv4": a_records, "ipv6": aaaa_records},
            "nameservers": nameservers,
            "mx_records": parse_mx_records(domain_name),
        })
        new_details_json = json.dumps(domain_data, ensure_ascii=False, default=str)

    # ---- 2. Take screenshot ----
    print(f"[DomainWatch] Checking {domain_name}...")
    screenshot_path = take_screenshot(domain_name)

    # ---- 3. Fetch & hash content ----
    _, new_content_hash = fetch_and_hash_content(domain_name)
    print(f"[DomainWatch] Content hash: {new_content_hash}")

    # ---- 4. Pull IOCs from OTX ----
    new_iocs = get_iocs(domain_name)
    print(f"[DomainWatch] Found {len(new_iocs)} IOCs from OTX")

    # ---- 5. Discover subdomains (crt.sh) ----
    new_subdomains = get_subdomains_from_crtsh(domain_name)
    print(f"[DomainWatch] Found {len(new_subdomains)} subdomains from crt.sh")

    # ---- Determine active / inactive ----
    main_ips = domain_data.get("main_ips", {})
    is_active = bool(main_ips.get("ipv4") or main_ips.get("ipv6"))
    domain_status = "active" if is_active else "inactive"

    # ---- 6. Load current state & detect changes ----
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()

        if not row:
            return

        old_status = row["status"]
        old_details_json = row["details_json"] or "{}"
        old_content_hash = row["content_hash"] or ""
        changed = False
        is_initial = old_status == "unknown"
        print(f"[DomainWatch] Previous status: {old_status}")

        # --- Insert IOCs into lookup table ---
        new_ioc_entries = []
        for ioc in new_iocs:
            existing = conn.execute(
                "SELECT id FROM domain_iocs WHERE domain_id = ? AND ioc_value = ? AND ioc_type = ?",
                (domain_id, ioc["ioc_value"], ioc["ioc_type"]),
            ).fetchone()
            if not existing:
                new_ioc_entries.append(ioc)
                conn.execute(
                    "INSERT INTO domain_iocs (domain_id, ioc_value, ioc_type, first_seen_at) VALUES (?, ?, ?, ?)",
                    (domain_id, ioc["ioc_value"], ioc["ioc_type"], now),
                )
                print(f"[DomainWatch] New IOC: {ioc['ioc_value']} ({ioc['ioc_type']})")

        # --- Insert subdomains into lookup table ---
        new_sub_entries = []
        for sub in new_subdomains:
            enrichment = enrich_subdomain(sub, domain_name)
            existing = conn.execute(
                "SELECT id FROM domain_subdomains WHERE domain_id = ? AND subdomain = ?",
                (domain_id, sub),
            ).fetchone()
            if not existing:
                new_sub_entries.append(sub)
                conn.execute(
                    """INSERT INTO domain_subdomains
                       (domain_id, subdomain, a_records_json, aaaa_records_json, cname_target,
                        ns_records_json, soa_record, is_delegated, is_resolving, wildcard_match,
                        last_checked_at, last_error, first_seen_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        domain_id,
                        sub,
                        enrichment["a_records_json"],
                        enrichment["aaaa_records_json"],
                        enrichment["cname_target"],
                        enrichment["ns_records_json"],
                        enrichment["soa_record"],
                        int(enrichment["is_delegated"]),
                        int(enrichment["is_resolving"]),
                        int(enrichment["wildcard_match"]),
                        now,
                        enrichment["last_error"],
                        now,
                    ),
                )
                print(f"[DomainWatch] New subdomain: {sub}")
                continue

            conn.execute(
                """UPDATE domain_subdomains
                   SET a_records_json = ?, aaaa_records_json = ?, cname_target = ?,
                       ns_records_json = ?, soa_record = ?, is_delegated = ?,
                       is_resolving = ?, wildcard_match = ?, last_checked_at = ?,
                       last_error = ?
                   WHERE id = ?""",
                (
                    enrichment["a_records_json"],
                    enrichment["aaaa_records_json"],
                    enrichment["cname_target"],
                    enrichment["ns_records_json"],
                    enrichment["soa_record"],
                    int(enrichment["is_delegated"]),
                    int(enrichment["is_resolving"]),
                    int(enrichment["wildcard_match"]),
                    now,
                    enrichment["last_error"],
                    existing["id"],
                ),
            )

        # --- Age-based refresh for stored subdomains not seen in crt.sh this run ---
        _SUBDOMAIN_REFRESH_HOURS = 24
        already_touched = set(new_subdomains)
        stale_rows = conn.execute(
            """SELECT id, subdomain FROM domain_subdomains
               WHERE domain_id = ?
                 AND (last_checked_at IS NULL
                      OR datetime(last_checked_at) < datetime('now', ?))""",
            (domain_id, f"-{_SUBDOMAIN_REFRESH_HOURS} hours"),
        ).fetchall()
        for stale in stale_rows:
            if stale["subdomain"] in already_touched:
                continue  # already refreshed in this run
            stale_enrichment = enrich_subdomain(stale["subdomain"], domain_name)
            conn.execute(
                """UPDATE domain_subdomains
                   SET a_records_json = ?, aaaa_records_json = ?, cname_target = ?,
                       ns_records_json = ?, soa_record = ?, is_delegated = ?,
                       is_resolving = ?, wildcard_match = ?, last_checked_at = ?,
                       last_error = ?
                   WHERE id = ?""",
                (
                    stale_enrichment["a_records_json"],
                    stale_enrichment["aaaa_records_json"],
                    stale_enrichment["cname_target"],
                    stale_enrichment["ns_records_json"],
                    stale_enrichment["soa_record"],
                    int(stale_enrichment["is_delegated"]),
                    int(stale_enrichment["is_resolving"]),
                    int(stale_enrichment["wildcard_match"]),
                    now,
                    stale_enrichment["last_error"],
                    stale["id"],
                ),
            )
            print(f"[DomainWatch] Refreshed stale subdomain: {stale['subdomain']}")

        # --- Initial entry (first check) — one combined history record ---
        alerts_to_send = []  # collect alerts, send AFTER commit
        if is_initial:
            changed = True
            initial_data = {
                "details": domain_data,
                "iocs": new_ioc_entries,
                "subdomains": new_sub_entries,
            }
            conn.execute(
                """INSERT INTO domain_history
                   (domain_id, change_type, old_value, new_value, screenshot_path, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (domain_id, "initial_entry", None,
                 json.dumps(initial_data, ensure_ascii=False, default=str),
                 screenshot_path, now),
            )
            alerts_to_send.append(("initial_entry", {
                "domain": domain_name,
                "case_id": case_id,
                "details": domain_data,
                "iocs": new_ioc_entries,
                "subdomains": new_sub_entries,
                "timestamp": now,
            }))
            print(f"[DomainWatch] Initial entry recorded for {domain_name}")
        else:
            # --- Records changed ---
            if new_details_json != old_details_json and new_details_json != "{}":
                changed = True
                conn.execute(
                    """INSERT INTO domain_history
                       (domain_id, change_type, old_value, new_value, screenshot_path, changed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (domain_id, "records_changed", old_details_json, new_details_json, screenshot_path, now),
                )
                alerts_to_send.append(("records_changed", {
                    "domain": domain_name,
                    "case_id": case_id,
                    "old_details": json.loads(old_details_json),
                    "new_details": domain_data,
                    "timestamp": now,
                }))
                print(f"[DomainWatch] Records changed for {domain_name}")

            # --- Content changed ---
            if new_content_hash and old_content_hash and new_content_hash != old_content_hash:
                changed = True
                conn.execute(
                    """INSERT INTO domain_history
                       (domain_id, change_type, old_value, new_value, screenshot_path, changed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (domain_id, "content_changed", old_content_hash, new_content_hash, screenshot_path, now),
                )
                alerts_to_send.append(("content_changed", {
                    "domain": domain_name,
                    "case_id": case_id,
                    "old_hash": old_content_hash,
                    "new_hash": new_content_hash,
                    "screenshot_path": screenshot_path,
                    "timestamp": now,
                }))
                print(f"[DomainWatch] Content changed for {domain_name}")

            # --- New IOCs ---
            if new_ioc_entries:
                changed = True
                conn.execute(
                    """INSERT INTO domain_history
                       (domain_id, change_type, old_value, new_value, screenshot_path, changed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (domain_id, "new_iocs", None,
                     json.dumps(new_ioc_entries, ensure_ascii=False), screenshot_path, now),
                )
                alerts_to_send.append(("new_iocs", {
                    "domain": domain_name,
                    "case_id": case_id,
                    "iocs": new_ioc_entries,
                    "new_iocs_count": len(new_ioc_entries),
                    "timestamp": now,
                }))

            # --- New subdomains ---
            if new_sub_entries:
                changed = True
                conn.execute(
                    """INSERT INTO domain_history
                       (domain_id, change_type, old_value, new_value, screenshot_path, changed_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (domain_id, "new_subdomains", None,
                     json.dumps(new_sub_entries, ensure_ascii=False), screenshot_path, now),
                )
                alerts_to_send.append(("new_subdomains", {
                    "domain": domain_name,
                    "case_id": case_id,
                    "new_subdomains": new_sub_entries,
                    "timestamp": now,
                }))

        # --- Update domain record ---
        conn.execute(
            """UPDATE domains
               SET details_json = ?, content_hash = ?, screenshot_path = ?,
                   status = ?, last_checked = ?, last_modified = ?
               WHERE id = ?""",
            (
                new_details_json if new_details_json != "{}" else row["details_json"],
                new_content_hash or old_content_hash,
                screenshot_path or row["screenshot_path"],
                domain_status,
                now,
                now if changed else row["last_modified"],
                domain_id,
            ),
        )

    # ---- Send alerts OUTSIDE the DB transaction ----
    for change_type, alert_data in alerts_to_send:
        try:
            send_alert(change_type, alert_data)
        except Exception as e:
            print(f"[DomainWatch] Alert send failed ({change_type}): {e}")


# ---------------------------------------------------------------------------
#  Bulk check (concurrent)
# ---------------------------------------------------------------------------

def check_all_domains():
    """Iterate all watched domains and run the monitoring pipeline concurrently."""
    with get_db() as conn:
        domains = conn.execute(
            "SELECT id, name, case_id FROM domains WHERE archived = 0 ORDER BY id"
        ).fetchall()

    def _run(domain):
        try:
            monitor_domain(domain["name"], domain["id"], domain["case_id"] or "")
        except Exception as e:
            print(f"[DomainWatch] Error checking {domain['name']}: {e}")

    with ThreadPoolExecutor(max_workers=min(10, len(domains) or 1)) as pool:
        futures = {pool.submit(_run, d): d["name"] for d in domains}
        for f in as_completed(futures):
            name = futures[f]
            try:
                f.result()
            except Exception as e:
                print(f"[DomainWatch] Uncaught error checking {name}: {e}")