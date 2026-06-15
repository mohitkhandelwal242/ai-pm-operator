#!/usr/bin/env python3
"""
jira-api.py — Fast, direct Jira REST API tool for Claude Code skills.

Subcommands:
    comment      PROJ-123 "text"           Add a comment
    create       --type Bug --summary "Login crash" [--labels mobile,backend] [--assignee-id ID] [--adf]
    edit         PROJ-123 --labels mobile,backend [--status "Done"]
    search       "project = PROJ AND ..."  JQL search
    lookup       "jane"                  Look up Jira account ID by name/email
    attach       PROJ-123 /path/to/file    Attach a file to an issue
    worklog      PROJ-123 2h [-c "desc"]   Log time spent
    worklog-list PROJ-123 [--since 2026-04-01]  List worklogs on an issue
    epic-time    PROJ-123 [--since 2026-04-01]  Aggregate time across epic children
    check-license                              Verify license/trial status
    verify-key   <KEY>                          Test a Gumroad key against the live API (no activation used)

Environment (from .env):
    JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT_KEY
"""

import argparse
import json
import mimetypes
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid
from base64 import b64encode
from pathlib import Path

# Try to import certifi, fallback to system certificates if unavailable
try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False


def load_env():
    """Load .env from project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


# ==============================================================================
# Gumroad licensing — set these for your product (see product/README.md).
#   GUMROAD_PRODUCT_PERMALINK : the "/l/<slug>" part of your product URL
#                               (e.g. pmoperator.gumroad.com/l/gfvonp -> "gfvonp").
#   GUMROAD_PRODUCT_ID        : optional; if set it takes precedence over the
#                               permalink. Find it via the Gumroad API; the
#                               permalink works fine on its own.
#   SUBSCRIBE_URL             : your checkout link, shown when the trial expires
#                               or a license is invalid.
# All can be overridden via environment variables of the same name.
# ==============================================================================
GUMROAD_PRODUCT_PERMALINK = os.environ.get("GUMROAD_PRODUCT_PERMALINK", "gfvonp")
GUMROAD_PRODUCT_ID = os.environ.get("GUMROAD_PRODUCT_ID", "Dyp8KL6VjWdE_d6MG7Lb0Q==")
SUBSCRIBE_URL = os.environ.get("OPERATOR_SUBSCRIBE_URL", "https://get.dydb.in")
GUMROAD_VERIFY_ENDPOINT = "https://api.gumroad.com/v2/licenses/verify"


def gumroad_verify_license(license_key, increment=False):
    """Verify a Gumroad license key via the public license API (no auth token needed).

    Returns (active: bool, detail: str). Raises on connectivity errors so callers
    can apply their offline-grace fallback. A 404 is treated as a definitive
    'invalid key' rather than a connectivity failure.
    """
    params = {
        "license_key": license_key,
        # Never bump the use-counter on routine runtime checks.
        "increment_uses_count": "true" if increment else "false",
    }
    # product_id takes precedence if provided; otherwise use the permalink.
    if GUMROAD_PRODUCT_ID:
        params["product_id"] = GUMROAD_PRODUCT_ID
    else:
        params["product_permalink"] = GUMROAD_PRODUCT_PERMALINK
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        GUMROAD_VERIFY_ENDPOINT, data=data, method="POST",
        headers={"Accept": "application/json"},
    )
    ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "License key not found for this product."
        raise  # 5xx / other -> let the caller treat as a connectivity error

    if not result.get("success"):
        return False, result.get("message", "License key is invalid.")

    purchase = result.get("purchase") or {}
    # A refund, chargeback, or dispute revokes access.
    for bad in ("refunded", "chargebacked", "disputed"):
        if purchase.get(bad):
            return False, f"Purchase was {bad}."
    # For subscription products, any of these being set means it has lapsed.
    for ended in ("subscription_cancelled_at", "subscription_ended_at", "subscription_failed_at"):
        if purchase.get(ended):
            return False, "Subscription is no longer active."
    return True, "active"


def verify_key_cli(license_key):
    """Diagnostic: verify a Gumroad license key against the LIVE API and print the full result.

    Does NOT increment the activation/uses counter, so it's safe to run repeatedly while
    testing. Use: python3 tools/jira-api.py verify-key <KEY>
    """
    load_env()
    key = (license_key or os.environ.get("OPERATOR_LICENSE_KEY", "")).strip()
    print("="*65)
    print("AI-PM Operator — Gumroad license verification (test mode)")
    print("="*65)
    print(f"Endpoint   : {GUMROAD_VERIFY_ENDPOINT}")
    print(f"Product ID : {GUMROAD_PRODUCT_ID or '(using permalink)'}")
    print(f"Permalink  : {GUMROAD_PRODUCT_PERMALINK}")
    print(f"Key        : {key or '(none provided)'}")
    print("-"*65)
    if not key:
        print("❌ No license key given. Pass one: python3 tools/jira-api.py verify-key <KEY>")
        sys.exit(2)

    params = {"license_key": key, "increment_uses_count": "false"}
    if GUMROAD_PRODUCT_ID:
        params["product_id"] = GUMROAD_PRODUCT_ID
    else:
        params["product_permalink"] = GUMROAD_PRODUCT_PERMALINK
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        GUMROAD_VERIFY_ENDPOINT, data=data, method="POST",
        headers={"Accept": "application/json"},
    )
    ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 404:
            print("❌ RESULT: INVALID — key not found for this product (HTTP 404).")
            print("   Check that GUMROAD_PRODUCT_ID / permalink matches the product the key was issued for.")
        else:
            print(f"❌ HTTP {e.code} from Gumroad: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Could not reach Gumroad: {e}")
        sys.exit(1)

    print("Raw Gumroad response:")
    print(json.dumps(result, indent=2))
    print("-"*65)
    active, detail = gumroad_verify_license(key)  # reuse the same logic the gate uses
    if active:
        purchase = result.get("purchase") or {}
        uses = result.get("uses")
        print("✅ RESULT: ACTIVE — this key would unlock the product.")
        print(f"   Buyer email : {purchase.get('email', 'n/a')}")
        print(f"   Product     : {purchase.get('product_name', 'n/a')}")
        if uses is not None:
            print(f"   Uses count  : {uses}")
    else:
        print(f"❌ RESULT: INACTIVE — {detail}")
        sys.exit(1)
    sys.exit(0)


def verify_license_and_trial(force_check_command=False):
    """Validate the Gumroad license key online, or fall back to a local 7-day trial."""
    load_env()
    license_key = os.environ.get("OPERATOR_LICENSE_KEY", "").strip()

    state_dir = Path(__file__).resolve().parent.parent / ".claude"
    state_file = state_dir / ".operator-state.json"
    state_dir.mkdir(parents=True, exist_ok=True)

    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            pass

    current_time = time.time()
    license_valid = state.get("license_valid", False)
    last_checked = state.get("last_checked", 0.0)
    cached_key = state.get("cached_key", "")

    # 1. Gumroad license validation
    if license_key:
        # Check cache if valid, not changed, and checked less than 24 hours ago
        if license_valid and cached_key == license_key and (current_time - last_checked < 86400):
            return True

        # Validate online via the Gumroad license API
        try:
            active, detail = gumroad_verify_license(license_key)
            if active:
                state["license_valid"] = True
                state["cached_key"] = license_key
                state["last_checked"] = current_time
                state_file.write_text(json.dumps(state, indent=2))
                return True
            else:
                # Invalidate if refunded, cancelled, lapsed, etc.
                state["license_valid"] = False
                state["cached_key"] = license_key
                state["last_checked"] = current_time
                state_file.write_text(json.dumps(state, indent=2))
                print("\n" + "="*65)
                print("❌ GUMROAD LICENSE INACTIVE OR INVALID.")
                print(f"Reason: {detail}")
                print(f"License key: {license_key}")
                print(f"Subscribe / manage your plan: {SUBSCRIBE_URL}")
                print("After subscribing, paste your new license key via:")
                print("  python3 tools/setup-wizard.py")
                print("="*65 + "\n")
                sys.exit(1)
        except Exception as e:
            # Offline fallback if already previously verified (within 3 days of offline tolerance)
            if license_valid and cached_key == license_key and (current_time - last_checked < 259200):
                return True
            print(f"\n⚠️ Offline connection warning: Could not verify license ({e}).")
            if not license_valid:
                # Fall through to trial check if not previously verified
                pass

    # 2. 7-day Free Trial gate
    def _trial_expired_block():
        print("\n" + "="*65)
        print("❌ 7-DAY FREE TRIAL EXPIRED.")
        print("Subscribe to keep using AI-PM Operator:")
        print(f"  {SUBSCRIBE_URL}")
        print("Then paste your Gumroad license key via:")
        print("  python3 tools/setup-wizard.py")
        print("="*65 + "\n")
        sys.exit(1)

    def _trial_remaining(seconds_left):
        if force_check_command:
            return
        days_left = seconds_left / 86400
        if days_left > 1:
            print(f"ℹ️ AI-PM Operator Trial: {days_left:.1f} days remaining.")
        else:
            print(f"ℹ️ AI-PM Operator Trial: {seconds_left / 3600:.1f} hours remaining.")
        print(f"   Subscribe anytime: {SUBSCRIBE_URL}")

    trial_limit = 7 * 24 * 60 * 60  # 7 days in seconds

    # 2a. Prefer the SERVER's verdict — keyed on an anonymous machine fingerprint, so it
    #     resists the usual local resets (deleting .operator-state.json / re-pulling).
    #     Falls back to the local timer when offline or when telemetry is opted out.
    try:
        import telemetry
        verdict = telemetry.check_trial(license_status="trial")
    except Exception:
        verdict = None

    if verdict is not None:
        if verdict.get("trial_expired"):
            _trial_expired_block()
        days_left = verdict.get("days_left")
        if isinstance(days_left, (int, float)):
            _trial_remaining(days_left * 86400)
        return True

    # 2b. Local fallback gate.
    trial_start = state.get("trial_start_time")
    if trial_start is None:
        trial_start = current_time
        state["trial_start_time"] = trial_start
        state_file.write_text(json.dumps(state, indent=2))

    elapsed = current_time - trial_start
    if elapsed > trial_limit:
        _trial_expired_block()

    _trial_remaining(trial_limit - elapsed)
    return True



def _get_config():
    # Supports both JIRA_* and ATLASSIAN_* env names for maximum compatibility
    url = os.environ.get("JIRA_URL") or os.environ.get("ATLASSIAN_SITE") or ""
    email = os.environ.get("JIRA_EMAIL") or os.environ.get("ATLASSIAN_EMAIL") or ""
    token = os.environ.get("JIRA_TOKEN") or os.environ.get("ATLASSIAN_API_TOKEN") or ""
    default_proj = os.environ.get("JIRA_PROJECT_KEY") or "PROJ"
    
    if not url or not email or not token:
        print("Error: JIRA_URL, JIRA_EMAIL, and JIRA_TOKEN must be set in .env", file=sys.stderr)
        sys.exit(1)
        
    # Standardize url domain
    url = url.strip().rstrip('/')
    if url.startswith("https://"):
        domain = url[8:]
    elif url.startswith("http://"):
        domain = url[7:]
    else:
        domain = url
        
    return domain, email, token, default_proj


_auth_verified = False


def _verify_auth():
    global _auth_verified
    if _auth_verified:
        return
    site, email, token, _ = _get_config()
    auth = b64encode(f"{email}:{token}".encode()).decode()
    req = urllib.request.Request(
        f"https://{site}/rest/api/3/myself",
        method="GET",
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    
    ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            resp.read()
        _auth_verified = True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(
                "❌ Jira auth failed (401). Your JIRA_TOKEN is invalid or expired.\n"
                "   Generate one at https://id.atlassian.com/manage-profile/security/api-tokens\n"
                "   Then update JIRA_TOKEN in .env",
                file=sys.stderr,
            )
        else:
            error_body = e.read().decode() if e.fp else ""
            print(f"❌ Jira auth check failed ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)


def _request(method, url, data=None):
    if not url.startswith("/rest/api/3/myself"):
        _verify_auth()
    site, email, token, _ = _get_config()
    full_url = f"https://{site}{url}" if url.startswith("/") else url
    auth = b64encode(f"{email}:{token}".encode()).decode()
    payload = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        full_url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    
    ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"❌ Failed ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)


def cmd_comment(args):
    if args.file:
        body = Path(args.file).read_text().strip()
    elif args.comment:
        body = args.comment
    else:
        body = sys.stdin.read().strip()
    if not body:
        print("Error: No comment text provided", file=sys.stderr)
        sys.exit(1)

    if args.adf:
        adf_body = json.loads(body)
    else:
        adf_body = {
            "version": 1, "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]
        }

    result = _request("POST", f"/rest/api/3/issue/{args.issue}/comment", {"body": adf_body})
    site, _, _, _ = _get_config()
    print(f"✅ Comment added to {args.issue}")
    print(f"   https://{site}/browse/{args.issue}?focusedId={result.get('id', '')}")


def cmd_create(args):
    site, _, _, default_proj = _get_config()
    project_key = args.project or default_proj
    fields = {
        "project": {"key": project_key},
        "summary": args.summary,
        "issuetype": {"name": args.type},
    }
    description = _resolve_description(args)
    if description:
        if args.adf:
            fields["description"] = json.loads(description)
        else:
            fields["description"] = _text_to_adf(description)
    if args.assignee_id:
        fields["assignee"] = {"accountId": args.assignee_id}
    if args.labels:
        fields["labels"] = [l.strip() for l in args.labels.split(",")]
    if args.parent:
        fields["parent"] = {"key": args.parent}

    result = _request("POST", "/rest/api/3/issue", {"fields": fields})
    key = result.get("key", "???")
    print(f"✅ Created {key} — {args.summary}")
    print(f"   https://{site}/browse/{key}")
    print(json.dumps({"key": key, "id": result.get("id"), "self": result.get("self")}))


def _text_to_adf(text):
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return {
        "version": 1, "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs]
    }


def _resolve_description(args):
    if getattr(args, "description_file", None):
        path = args.description_file
        if path == "-":
            return sys.stdin.read()
        return Path(path).read_text()
    return getattr(args, "description", None)


def cmd_edit(args):
    fields = {}
    if args.labels is not None:
        fields["labels"] = [l.strip() for l in args.labels.split(",")] if args.labels else []
    if args.summary:
        fields["summary"] = args.summary
    description = _resolve_description(args)
    if description:
        if args.adf:
            fields["description"] = json.loads(description)
        else:
            fields["description"] = _text_to_adf(description)
    if args.assignee_id:
        fields["assignee"] = {"accountId": args.assignee_id}
    if args.parent:
        fields["parent"] = {"key": args.parent}
    if args.status:
        target = args.status.lower()
        transitions = _request("GET", f"/rest/api/3/issue/{args.issue}/transitions")
        match = next((t for t in transitions.get("transitions", [])
                      if t["name"].lower() == target or t["to"]["name"].lower() == target), None)
        if not match:
            available = [f"{t['name']} → {t['to']['name']}" for t in transitions.get("transitions", [])]
            print(f"❌ Status '{args.status}' not reachable. Available: {', '.join(available)}", file=sys.stderr)
            sys.exit(1)
        _request("POST", f"/rest/api/3/issue/{args.issue}/transitions", {"transition": {"id": match["id"]}})
        print(f"✅ Transitioned {args.issue} → {match['to']['name']}")

    if fields:
        _request("PUT", f"/rest/api/3/issue/{args.issue}", {"fields": fields})
        print(f"✅ Updated {args.issue}")


def cmd_search(args):
    encoded_jql = urllib.parse.quote(args.jql)
    max_results = args.max_results or 5
    fields = args.fields or "summary,status,assignee,priority,labels"
    result = _request("GET", f"/rest/api/3/search/jql?jql={encoded_jql}&fields={fields}&maxResults={max_results}")
    issues = result.get("issues", [])
    if not issues:
        print("No issues found.")
        return
    for issue in issues:
        f = issue.get("fields", {})
        status = f.get("status", {}).get("name", "?")
        assignee = f.get("assignee", {})
        assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        print(f"{issue['key']}: {f.get('summary', '?')} [{status}] ({assignee_name})")
    print("---JSON---")
    print(json.dumps(issues, indent=2))


def cmd_attach(args):
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    site, email, token, _ = _get_config()
    auth = b64encode(f"{email}:{token}".encode()).decode()
    boundary = uuid.uuid4().hex
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    file_data = file_path.read_bytes()
    filename = file_path.name

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    url = f"https://{site}/rest/api/3/issue/{args.issue}/attachments"
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        },
    )
    ctx = ssl.create_default_context(cafile=certifi.where()) if HAS_CERTIFI else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            result = json.loads(resp.read())
            name = result[0].get("filename", filename) if result else filename
            print(f"✅ Attached {name} to {args.issue}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"❌ Failed ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)


def cmd_worklog(args):
    fields = {"timeSpent": args.time_spent}
    if args.comment:
        fields["comment"] = _text_to_adf(args.comment)
    if args.started:
        fields["started"] = args.started
    result = _request("POST", f"/rest/api/3/issue/{args.issue}/worklog", fields)
    print(f"✅ Logged {args.time_spent} on {args.issue}")


def cmd_worklog_list(args):
    result = _request("GET", f"/rest/api/3/issue/{args.issue}/worklog")
    worklogs = result.get("worklogs", [])
    since = args.since or "1970-01-01"
    entries = []
    total_secs = 0
    for w in worklogs:
        started = w["started"][:10]
        if started < since:
            continue
        secs = w["timeSpentSeconds"]
        author = w["author"]["displayName"]
        comment_content = w.get("comment", {}).get("content", [{}])
        comment_text = ""
        if comment_content:
            inner = comment_content[0].get("content", [{}])
            if inner:
                comment_text = inner[0].get("text", "")
        entries.append({"date": started, "author": author, "hours": round(secs / 3600, 2), "comment": comment_text})
        total_secs += secs
    if not entries:
        print(f"No worklogs on {args.issue}" + (f" since {since}" if args.since else ""))
        return
    for e in entries:
        print(f"  {e['date']} | {e['author']:20s} | {e['hours']:5.1f}h | {e['comment']}")
    print(f"  {'':>23s} Total: {total_secs / 3600:.1f}h")
    print("---JSON---")
    print(json.dumps({"issue": args.issue, "total_hours": round(total_secs / 3600, 2), "entries": entries}, indent=2))


def cmd_epic_time(args):
    since = args.since or "1970-01-01"
    encoded_jql = urllib.parse.quote(f"parent = {args.epic}")
    result = _request("GET", f"/rest/api/3/search/jql?jql={encoded_jql}&fields=summary,assignee,status&maxResults=50")
    issues = result.get("issues", [])
    if not issues:
        print(f"No child issues found for {args.epic}")
        return
    all_entries = []
    grand_total = 0
    by_person = {}
    for issue in issues:
        key = issue["key"]
        summary = issue["fields"].get("summary", "?")
        wl_result = _request("GET", f"/rest/api/3/issue/{key}/worklog")
        for w in wl_result.get("worklogs", []):
            started = w["started"][:10]
            if started < since:
                continue
            secs = w["timeSpentSeconds"]
            author = w["author"]["displayName"]
            comment_content = w.get("comment", {}).get("content", [{}])
            comment_text = ""
            if comment_content:
                inner = comment_content[0].get("content", [{}])
                if inner:
                    comment_text = inner[0].get("text", "")
            hours = round(secs / 3600, 2)
            all_entries.append({"issue": key, "summary": summary, "date": started, "author": author, "hours": hours, "comment": comment_text})
            grand_total += secs
            by_person[author] = by_person.get(author, 0) + secs

    if not all_entries:
        print(f"No worklogs across {len(issues)} children of {args.epic}" + (f" since {since}" if args.since else ""))
        return
    all_entries.sort(key=lambda e: e["date"])
    for e in all_entries:
        print(f"  {e['date']} | {e['issue']:10s} | {e['author']:20s} | {e['hours']:5.1f}h | {e['comment']}")
    print(f"\n  Summary ({len(issues)} issues" + (f", since {since}" if args.since else "") + f"):")
    for person, secs in sorted(by_person.items(), key=lambda x: -x[1]):
        print(f"    {person:20s} {secs / 3600:.1f}h")
    print(f"    {'TOTAL':20s} {grand_total / 3600:.1f}h")
    print("---JSON---")
    print(json.dumps({"epic": args.epic, "total_hours": round(grand_total / 3600, 2), "by_person": {k: round(v / 3600, 2) for k, v in by_person.items()}, "entries": all_entries}, indent=2))


def cmd_lookup(args):
    encoded = urllib.parse.quote(args.query)
    result = _request("GET", f"/rest/api/3/user/search?query={encoded}&maxResults=5")
    if not result:
        print("No users found.")
        return
    for user in result:
        active = "✓" if user.get("active") else "✗"
        print(f"{active} {user.get('displayName', '?')} — {user.get('accountId', '?')} ({user.get('emailAddress', 'no email')})")
    if result:
        print("---JSON---")
        print(json.dumps({"accountId": result[0].get("accountId"), "displayName": result[0].get("displayName")}))


def main():
    load_env()
    
    # Fast-path: test a Gumroad key against the live API (does not consume an activation)
    if len(sys.argv) > 1 and sys.argv[1] == "verify-key":
        verify_key_cli(sys.argv[2] if len(sys.argv) > 2 else "")
        sys.exit(0)

    # Fast-path for license verification command
    if len(sys.argv) > 1 and sys.argv[1] == "check-license":
        verify_license_and_trial(force_check_command=True)
        print("✓ License / Trial check passed successfully.")
        sys.exit(0)
        
    # Enforce license/trial verification for all functional API runs
    verify_license_and_trial(force_check_command=False)

    # Best-effort, throttled (daily) usage heartbeat. Sends only a non-sensitive
    # business summary; respects OPERATOR_TELEMETRY=off. Never blocks or raises.
    try:
        import telemetry
        telemetry.send("ping")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Fast Jira REST API tool")
    sub = parser.add_subparsers(dest="command", required=True)

    # comment
    p_comment = sub.add_parser("comment", help="Add a comment to an issue")
    p_comment.add_argument("issue", help="Issue key (e.g. PROJ-123)")
    p_comment.add_argument("comment", nargs="?", help="Comment text")
    p_comment.add_argument("--file", "-f", help="Read comment from file")
    p_comment.add_argument("--adf", action="store_true", help="Treat body as raw ADF JSON")

    # create
    p_create = sub.add_parser("create", help="Create a new issue")
    p_create.add_argument("--project", "-p", help="Project key")
    p_create.add_argument("--type", "-t", required=True, help="Issue type: Bug, Story, Task")
    p_create.add_argument("--summary", "-s", required=True, help="Issue summary")
    p_create.add_argument("--description", "-d", help="Issue description")
    p_create.add_argument("--description-file", help="Read description from file")
    p_create.add_argument("--labels", "-l", help="Comma-separated labels")
    p_create.add_argument("--assignee-id", help="Assignee account ID")
    p_create.add_argument("--parent", help="Parent Epic key")
    p_create.add_argument("--adf", action="store_true", help="Treat description as raw ADF JSON")

    # edit
    p_edit = sub.add_parser("edit", help="Edit an existing issue")
    p_edit.add_argument("issue", help="Issue key (e.g. PROJ-123)")
    p_edit.add_argument("--labels", "-l", help="Comma-separated labels (replaces all)")
    p_edit.add_argument("--summary", "-s", help="New summary")
    p_edit.add_argument("--description", "-d", help="New description")
    p_edit.add_argument("--description-file", help="Read description from file")
    p_edit.add_argument("--assignee-id", help="Assignee account ID")
    p_edit.add_argument("--parent", help="Parent Epic key")
    p_edit.add_argument("--status", help="Transition to this status")
    p_edit.add_argument("--adf", action="store_true", help="Treat description as raw ADF JSON")

    # search
    p_search = sub.add_parser("search", help="Search issues with JQL")
    p_search.add_argument("jql", help="JQL query string")
    p_search.add_argument("--max-results", "-n", type=int, default=5)
    p_search.add_argument("--fields", help="Comma-separated field names")

    # lookup
    p_lookup = sub.add_parser("lookup", help="Look up Jira account ID by name/email")
    p_lookup.add_argument("query", help="Name or email to search")

    # attach
    p_attach = sub.add_parser("attach", help="Attach a file to an issue")
    p_attach.add_argument("issue", help="Issue key (e.g. PROJ-123)")
    p_attach.add_argument("file", help="Path to file to attach")

    # worklog
    p_worklog = sub.add_parser("worklog", help="Log time spent on an issue")
    p_worklog.add_argument("issue", help="Issue key (e.g. PROJ-123)")
    p_worklog.add_argument("time_spent", help="Time spent")
    p_worklog.add_argument("--comment", "-c", help="Work description")
    p_worklog.add_argument("--started", help="Start time")

    # worklog-list
    p_wl_list = sub.add_parser("worklog-list", help="List worklogs on an issue")
    p_wl_list.add_argument("issue", help="Issue key (e.g. PROJ-123)")
    p_wl_list.add_argument("--since", help="Only show worklogs on or after this date (YYYY-MM-DD)")

    # epic-time
    p_epic = sub.add_parser("epic-time", help="Aggregate time logged across all children of an epic")
    p_epic.add_argument("epic", help="Epic issue key")
    p_epic.add_argument("--since", help="Only include worklogs on or after this date (YYYY-MM-DD)")

    args = parser.parse_args()
    {
        "comment": cmd_comment, "create": cmd_create, "edit": cmd_edit,
        "search": cmd_search, "lookup": cmd_lookup, "attach": cmd_attach,
        "worklog": cmd_worklog, "worklog-list": cmd_worklog_list, "epic-time": cmd_epic_time,
    }[args.command](args)


if __name__ == "__main__":
    main()
