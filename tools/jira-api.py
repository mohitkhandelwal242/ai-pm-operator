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


def verify_license_and_trial(force_check_command=False):
    """Enforce a local 3-day free trial, or validate the PayPal subscription ID online."""
    load_env()
    subscription_id = os.environ.get("OPERATOR_SUBSCRIPTION_ID", "").strip()
    
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
    
    # 1. PayPal Subscription validation
    if subscription_id:
        # Check cache if valid, not changed, and checked less than 24 hours ago
        if license_valid and cached_key == subscription_id and (current_time - last_checked < 86400):
            return True
            
        # Validate online via dydb.in/verify.php
        try:
            url = f"https://dydb.in/verify.php?subscription_id={urllib.parse.quote(subscription_id)}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                result = json.loads(resp.read().decode())
                if result.get("valid") is True:
                    state["license_valid"] = True
                    state["cached_key"] = subscription_id
                    state["last_checked"] = current_time
                    state_file.write_text(json.dumps(state, indent=2))
                    return True
                else:
                    # Invalidate if payment declined, cancelled, etc.
                    state["license_valid"] = False
                    state["cached_key"] = subscription_id
                    state["last_checked"] = current_time
                    state_file.write_text(json.dumps(state, indent=2))
                    print("\n" + "="*65)
                    print("❌ PAYPAL SUBSCRIPTION INACTIVE OR DECLINED.")
                    print(f"Subscription ID: {subscription_id}")
                    print("Please check your payment status or update details at https://dydb.in.")
                    print("Run the setup wizard to update your subscription ID:")
                    print("  python3 tools/setup-wizard.py")
                    print("="*65 + "\n")
                    sys.exit(1)
        except Exception as e:
            # Offline fallback if already previously verified (within 3 days of offline tolerance)
            if license_valid and cached_key == subscription_id and (current_time - last_checked < 259200):
                return True
            print(f"\n⚠️ Offline connection warning: Could not verify subscription ({e}).")
            if not license_valid:
                # Fall through to trial check if not previously verified
                pass

    # 2. 3-day Free Trial gate
    trial_start = state.get("trial_start_time")
    
    if trial_start is None:
        trial_start = current_time
        state["trial_start_time"] = trial_start
        state_file.write_text(json.dumps(state, indent=2))
        
    elapsed = current_time - trial_start
    trial_limit = 3 * 24 * 60 * 60 # 3 days in seconds
    
    if elapsed > trial_limit:
        print("\n" + "="*65)
        print("❌ 3-DAY FREE TRIAL EXPIRED.")
        print("Please set up your subscription at https://dydb.in to continue.")
        print("Once subscribed, configure your PayPal Subscription ID using:")
        print("  python3 tools/setup-wizard.py")
        print("="*65 + "\n")
        sys.exit(1)
        
    if not force_check_command:
        days_left = (trial_limit - elapsed) / 86400
        if days_left > 1:
            print(f"ℹ️ AI-PM Operator Trial: {days_left:.1f} days remaining.")
        else:
            hours_left = (trial_limit - elapsed) / 3600
            print(f"ℹ️ AI-PM Operator Trial: {hours_left:.1f} hours remaining.")
            
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
    
    # Fast-path for license verification command
    if len(sys.argv) > 1 and sys.argv[1] == "check-license":
        verify_license_and_trial(force_check_command=True)
        print("✓ License / Trial check passed successfully.")
        sys.exit(0)
        
    # Enforce license/trial verification for all functional API runs
    verify_license_and_trial(force_check_command=False)

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
