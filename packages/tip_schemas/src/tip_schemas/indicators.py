import ipaddress
import re
from enum import StrEnum
from urllib.parse import urlparse, urlunparse

import idna


class IndicatorType(StrEnum):
    IP = "ip"
    DOMAIN = "domain"
    URL = "url"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    EMAIL = "email"


_DEFANG = [
    (r"\[\.\]", "."),
    (r"\(\.\)", "."),
    (r"\{\.\}", "."),
    (r"\[:\]", ":"),
    (r"hxxp://", "http://"),
    (r"hxxps://", "https://"),
]


def _refang(value: str) -> str:
    out = value
    for pat, repl in _DEFANG:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def _norm_ip(value: str) -> str:
    addr = ipaddress.ip_address(value.strip())
    return str(addr)


def _norm_domain(value: str) -> str:
    raw = _refang(value.strip().lower().rstrip("."))
    try:
        return idna.encode(raw).decode("ascii")
    except idna.IDNAError as e:
        raise ValueError(f"invalid domain: {value}") from e


def _norm_url(value: str) -> str:
    refanged = _refang(value.strip())
    parsed = urlparse(refanged)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid url: {value}")
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    try:
        host = _norm_domain(host)
    except ValueError:
        host = host.lower()
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = host if port is None else f"{host}:{port}"
    return urlunparse((scheme, netloc, parsed.path or "/", "", parsed.query, ""))


_HEX_LENGTHS = {32: IndicatorType.MD5, 40: IndicatorType.SHA1, 64: IndicatorType.SHA256}


def _norm_hash(value: str, expected: IndicatorType) -> str:
    cleaned = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]+", cleaned):
        raise ValueError(f"invalid hex hash: {value}")
    detected = _HEX_LENGTHS.get(len(cleaned))
    if detected != expected:
        raise ValueError(f"hash length {len(cleaned)} does not match {expected}")
    return cleaned


def _norm_email(value: str) -> str:
    refanged = _refang(value.strip().lower())
    if "@" not in refanged:
        raise ValueError(f"invalid email: {value}")
    local, _, domain = refanged.rpartition("@")
    return f"{local}@{_norm_domain(domain)}"


def normalize_indicator(indicator_type: IndicatorType | str, raw_value: str) -> str:
    t = IndicatorType(indicator_type)
    if t is IndicatorType.IP:
        return _norm_ip(raw_value)
    if t is IndicatorType.DOMAIN:
        return _norm_domain(raw_value)
    if t is IndicatorType.URL:
        return _norm_url(raw_value)
    if t is IndicatorType.EMAIL:
        return _norm_email(raw_value)
    if t in (IndicatorType.MD5, IndicatorType.SHA1, IndicatorType.SHA256):
        return _norm_hash(raw_value, t)
    raise ValueError(f"unsupported indicator type: {t}")
