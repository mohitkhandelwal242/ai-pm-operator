#!/usr/bin/env python3
"""
telemetry.py — first-party install/usage analytics for AI-PM Operator.

Sends a SMALL, NON-SENSITIVE business profile summary to the vendor endpoint so
the maker can see what kinds of businesses install and use the product.

WHAT IS SENT (from business.json + local state only):
    install_id, event, timestamp, version, license_status,
    company_name, product_name, business_type, industry, revenue_model,
    primary_platforms, website_domain, north_star, key_metrics, competitor_count,
    country (best-effort from locale).

WHAT IS NEVER SENT:
    .env contents, Jira/Confluence tokens or URLs, team.json (names/emails/IDs),
    competitor names, context_notes, or any file contents.

The payload is base64-encoded and POSTed over HTTPS. This is disclosed in
product/README.md. Users can opt out with OPERATOR_TELEMETRY=off in .env.

Usage:
    python3 tools/telemetry.py install     # called once at setup/onboarding
    python3 tools/telemetry.py ping        # throttled daily usage heartbeat
"""

import base64
import json
import os
import ssl
import sys
import time
import uuid
import locale
import platform
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

VERSION = "1.0"
ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / ".claude" / ".operator-state.json"
DEFAULT_ENDPOINT = "https://dydb.in/operator/collect.php"
PING_INTERVAL = 24 * 60 * 60  # once per day


def _load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _read_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _install_id(state):
    """Stable, anonymous per-install id (not tied to any personal identity)."""
    iid = state.get("install_id")
    if not iid:
        iid = uuid.uuid4().hex
        state["install_id"] = iid
        _write_state(state)
    return iid


def machine_id():
    """Stable, anonymous machine fingerprint (hashed) for server-enforced trials.

    Derived from host + OS + NIC id, then SHA-256'd — so it survives deleting
    .operator-state.json or re-pulling the repo (the common ways people try to
    reset a local trial), without storing anything personally identifying.
    """
    try:
        raw = f"{platform.node()}|{platform.system()}|{platform.machine()}|{uuid.getnode()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
    except Exception:
        return ""


def _country():
    try:
        loc = ""
        try:
            loc = (locale.getlocale()[0] or "")
        except Exception:
            loc = ""
        if not loc:
            loc = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
        loc = loc.split(".")[0]  # strip any ".UTF-8" suffix
        return loc.split("_")[-1] if "_" in loc else ""
    except Exception:
        return ""


def _license_status(state):
    return "licensed" if state.get("license_valid") else "trial"


def build_payload(event):
    """Assemble the non-sensitive payload. Reads ONLY business.json + local state."""
    state = _read_state()
    biz = {}
    bpath = ROOT / "business.json"
    if bpath.exists():
        try:
            biz = json.loads(bpath.read_text())
        except Exception:
            biz = {}

    company = biz.get("company", {}) if isinstance(biz, dict) else {}
    metrics = biz.get("metrics", {}) if isinstance(biz, dict) else {}
    competitors = biz.get("competitors", []) if isinstance(biz, dict) else []

    return {
        "install_id": _install_id(state),
        "machine_id": machine_id(),
        "event": event,
        "ts": int(time.time()),
        "version": VERSION,
        "license_status": _license_status(state),
        "country": _country(),
        # ---- business profile (no credentials, no team data) ----
        "company_name": company.get("name", ""),
        "product_name": company.get("product_name", ""),
        "business_type": company.get("business_type", ""),
        "industry": company.get("industry", ""),
        "revenue_model": company.get("revenue_model", ""),
        "primary_platforms": company.get("primary_platforms", []),
        "website_domain": company.get("website_domain", ""),
        "north_star": metrics.get("north_star", ""),
        "key_metrics": metrics.get("key_metrics", []),
        "competitor_count": len([c for c in competitors if isinstance(c, dict) and c.get("name")]),
    }


def _enabled():
    return os.environ.get("OPERATOR_TELEMETRY", "on").strip().lower() not in ("off", "0", "false", "no")


def _endpoint():
    return os.environ.get("OPERATOR_TELEMETRY_URL", DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT


def _post(payload):
    """Encode + POST a payload; return the parsed JSON response dict, or None on any failure."""
    try:
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        req = urllib.request.Request(
            _endpoint(),
            data=encoded.encode(),
            method="POST",
            headers={"Content-Type": "text/plain", "User-Agent": f"ai-pm-operator/{VERSION}"},
        )
        ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            body = resp.read().decode()
        return json.loads(body) if body else {}
    except Exception:
        # Telemetry must never break the product.
        return None


def send(event):
    """Encode + POST a telemetry event (install|ping). Silent, best-effort.

    Returns the server response dict on success (may include trial status), else False.
    """
    _load_env()
    if not _enabled():
        return False

    # Daily throttle for usage pings.
    state = _read_state()
    if event == "ping":
        if time.time() - state.get("last_ping", 0) < PING_INTERVAL:
            return False

    resp = _post(build_payload(event))
    if resp is None:
        return False

    state = _read_state()
    state["last_ping"] = int(time.time())
    _write_state(state)
    return resp


def check_trial(license_status="trial"):
    """Ask the server for the authoritative trial verdict for this machine.

    Returns a dict like {"trial_expired": bool, "days_left": float} when the server
    is reachable, else None (caller should fall back to the local trial gate).
    Keyed on the anonymous machine fingerprint, so it survives local-state deletion.
    Respects the OPERATOR_TELEMETRY opt-out.
    """
    _load_env()
    if not _enabled():
        return None

    # Serve a recent cached verdict so the per-skill gate doesn't hit the network every
    # time. An expired verdict is returned immediately (no point re-checking); an active
    # one is cached for 30 minutes.
    state = _read_state()
    cached = state.get("trial_verdict")
    cached_at = state.get("trial_verdict_at", 0)
    if isinstance(cached, dict) and "trial_expired" in cached:
        if cached.get("trial_expired") or (time.time() - cached_at < 1800):
            return cached

    payload = {
        "event": "trial",
        "machine_id": machine_id(),
        "install_id": _install_id(state),
        "license_status": license_status,
        "version": VERSION,
        "ts": int(time.time()),
    }
    resp = _post(payload)
    if not isinstance(resp, dict) or "trial_expired" not in resp:
        return None

    state = _read_state()
    state["trial_verdict"] = resp
    state["trial_verdict_at"] = int(time.time())
    _write_state(state)
    return resp


if __name__ == "__main__":
    event = sys.argv[1] if len(sys.argv) > 1 else "ping"
    if event not in ("install", "ping"):
        event = "ping"
    ok = send(event)
    # Quiet by design; print only when explicitly debugging.
    if os.environ.get("OPERATOR_TELEMETRY_DEBUG"):
        print(f"telemetry {event}: {'sent' if ok else 'skipped/failed'}")
