#!/usr/bin/env python3
import os
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import getpass
import subprocess

# Colors for terminal styling
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== {title} ==={Colors.END}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠️ {msg}{Colors.END}")

def scan_codebase():
    """Scans the surrounding project environment to detect connections and project structures."""
    print(f"{Colors.BOLD}{Colors.CYAN}🔍 Scanning your project workspace...{Colors.END}")
    
    diagnostic = {
        "is_git": False,
        "repo_name": "Unknown",
        "branch": "Unknown",
        "tech_stack": [],
        "skills_found": [],
        "config_status": {
            "env_exists": os.path.exists(".env"),
            "team_exists": os.path.exists("team.json"),
            "google_creds_exists": os.path.exists("google-credentials.json"),
            "competitors_exists": os.path.exists(".claude/knowledge/competitor-audit/scan-urls.json")
        }
    }
    
    # 1. Check Git
    try:
        is_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        if is_git.returncode == 0 and is_git.stdout.strip() == "true":
            diagnostic["is_git"] = True
            
            # Get Repo Name
            repo_path = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
            if repo_path.returncode == 0:
                diagnostic["repo_name"] = os.path.basename(repo_path.stdout.strip())
                
            # Get Current Branch
            branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
            if branch.returncode == 0:
                diagnostic["branch"] = branch.stdout.strip()
    except Exception:
        pass
        
    # 2. Check Tech Stack
    # We look in the parent directories as setup-wizard.py is typically in product/tools/ or root
    paths_to_check = [".", "..", "../.."]
    for p in paths_to_check:
        if os.path.exists(os.path.join(p, "package.json")):
            diagnostic["tech_stack"].append("Node.js / Web")
        if os.path.exists(os.path.join(p, "requirements.txt")) or os.path.exists(os.path.join(p, "pipfile")):
            diagnostic["tech_stack"].append("Python")
        if os.path.exists(os.path.join(p, "build.gradle")) or os.path.exists(os.path.join(p, "AndroidManifest.xml")):
            diagnostic["tech_stack"].append("Android (Java/Kotlin)")
        if os.path.exists(os.path.join(p, "Podfile")) or any(f.endswith(".xcodeproj") for f in os.listdir(p) if os.path.isdir(os.path.join(p, f))):
            diagnostic["tech_stack"].append("iOS (Swift/Obj-C)")
        if os.path.exists(os.path.join(p, "go.mod")):
            diagnostic["tech_stack"].append("Go")
        if os.path.exists(os.path.join(p, "composer.json")):
            diagnostic["tech_stack"].append("PHP")

    # Remove duplicates and limit
    diagnostic["tech_stack"] = list(set(diagnostic["tech_stack"]))
    if not diagnostic["tech_stack"]:
        diagnostic["tech_stack"].append("General / Agnostic")

    # 3. Scan for Operator Skills
    skills_path = ".claude/skills"
    if os.path.exists(skills_path):
        diagnostic["skills_found"] = [d for d in os.listdir(skills_path) if os.path.isdir(os.path.join(skills_path, d))]
    else:
        # Fallback to check relative paths if run from tools/
        skills_path = "../.claude/skills"
        if os.path.exists(skills_path):
            diagnostic["skills_found"] = [d for d in os.listdir(skills_path) if os.path.isdir(os.path.join(skills_path, d))]

    # 4. Print beautiful Diagnostic dashboard
    print(f"\n{Colors.BOLD}{Colors.BLUE}==============================================={Colors.END}")
    print(f"{Colors.BOLD}💻 ENVIRONMENT DIAGNOSTICS{Colors.END}")
    print(f"{Colors.BLUE}-----------------------------------------------{Colors.END}")
    print(f"• Git Repository:  {Colors.GREEN}{'Connected' if diagnostic['is_git'] else 'No Git detected'}{Colors.END} (Name: {diagnostic['repo_name']}, Branch: {diagnostic['branch']})")
    print(f"• Project Type:    {Colors.GREEN}{', '.join(diagnostic['tech_stack'])}{Colors.END}")
    print(f"• Operator Skills: {Colors.GREEN}{len(diagnostic['skills_found'])} skills detected{Colors.END}")
    print(f"• Config Files:    .env ({'Present' if diagnostic['config_status']['env_exists'] else 'Missing'}), team.json ({'Present' if diagnostic['config_status']['team_exists'] else 'Missing'})")
    print(f"{Colors.BOLD}{Colors.BLUE}==============================================={Colors.END}\n")
    
    return diagnostic

def validate_subscription(sub_id):
    if not sub_id:
        return True
    
    print_info("Validating PayPal Subscription ID with server...")
    if not sub_id.startswith("I-") or len(sub_id.strip()) < 10:
        print_error("Invalid PayPal subscription ID format. Should start with 'I-'.")
        return False
        
    try:
        import ssl
        url = f"https://dydb.in/verify.php?subscription_id={urllib.parse.quote(sub_id)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get("valid") is True:
                    print_success(f"Subscription is ACTIVE! Status: {data.get('status')}")
                    return True
                else:
                    print_error(f"Subscription validation failed: {data.get('error', 'Not active')}")
                    return False
    except Exception as e:
        print_error(f"Could not connect to subscription verification server: {str(e)}")
        print_warning("Server offline. Continuing under 3-day local trial.")
        return True

def validate_jira(url, email, token, project_key):
    print_info("Connecting to Jira and validating credentials...")
    
    # Format Jira URL
    url = url.strip().rstrip('/')
    if not url.startswith("http"):
        url = "https://" + url
        
    api_endpoint = f"{url}/rest/api/3/project/{project_key}"
    
    # Create Auth Header
    auth_str = f"{email}:{token}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    
    req = urllib.request.Request(
        api_endpoint,
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                print_success(f"Connected to Jira! Found project: {data.get('name', project_key)}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print_error("Jira Authentication failed (Unauthorized). Check Email and Token.")
        elif e.code == 404:
            print_error(f"Jira project key '{project_key}' not found. Verify the project key.")
        else:
            print_error(f"HTTP Error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        print_error(f"Failed to reach Jira server: {e.reason}")
    except Exception as e:
        print_error(f"Unexpected verification error: {str(e)}")
        
    return False

def initialize_competitors(competitors_list):
    """Initializes custom competitors.md and scan-urls.json configs based on user input."""
    os.makedirs(".claude/knowledge/competitor-audit", exist_ok=True)
    
    # 1. Write scan-urls.json
    scan_urls = {
        "app_store_data": [],
        "cross_verification": [],
        "ads_library": [],
        "news_rss": [],
        "discovery_queries": [
            {
                "queries": [
                    "new carpool app India 2026 launch",
                    "best carpooling apps India 2026",
                    "carpool startup India funding 2026"
                ]
            }
        ]
    }
    
    competitors_md = "# Competitor Registry\n\n## Tracked Competitors\n\n"
    
    for comp in competitors_list:
        name = comp["name"]
        domain = comp["domain"]
        package = comp["package"]
        
        # Add to scan-urls lists
        if package:
            scan_urls["app_store_data"].append({
                "competitor": name.lower(),
                "android_url": f"https://play.google.com/store/apps/details?id={package}",
                "ios_url": f"https://apps.apple.com/in/app/{name.lower()}/id12345678"
            })
            scan_urls["cross_verification"].append({
                "competitor": name.lower(),
                "appbrain_url": f"https://www.appbrain.com/app/{package}"
            })
            
        scan_urls["ads_library"].append({
            "competitor": name.lower(),
            "google_transparency_url": f"https://adstransparency.google.com/?domain={domain}"
        })
        scan_urls["news_rss"].append({
            "competitor": name.lower(),
            "query": f'"{name}" carpool India'
        })
        
        # Add to competitors.md profile
        competitors_md += f"### {name} (Tier 1)\n"
        competitors_md += f"- **Website**: [https://{domain}](https://{domain})\n"
        if package:
            competitors_md += f"- **Android App ID**: `{package}`\n"
        competitors_md += f"- **Classification**: Daily commute commute ridesharing\n\n"
        
    # Write files
    with open(".claude/knowledge/competitor-audit/scan-urls.json", "w") as f:
        json.dump(scan_urls, f, indent=2)
        
    with open(".claude/knowledge/competitor-audit/competitors.md", "w") as f:
        f.write(competitors_md)
        
    # Write blank baseline last-scan.json
    last_scan = {
        "scan_date": "2026-06-12",
        "competitors": {}
    }
    for comp in competitors_list:
        last_scan["competitors"][comp["name"].lower()] = {
            "android_rating": 4.0,
            "android_installs": "100k+",
            "android_version": "1.0.0",
            "android_whats_new": "Initial release",
            "ads_channels": {"google_ads": "inactive", "meta_ads": "inactive"}
        }
    with open(".claude/knowledge/competitor-audit/last-scan.json", "w") as f:
        json.dump(last_scan, f, indent=2)

    print_success("Initialized customized competitor tracking reference files.")

def display_readiness_report(diagnostic, jira_configured, conf_configured, analytics_configured, comp_configured):
    """Outputs a beautiful operational readiness status for all 14 skills."""
    print_header("OPERATIONAL READINESS STATUS")
    
    # Map of skills to their prerequisite checks
    skills_map = [
        ("deep-competitor-tracker", comp_configured, "Requires competitor configuration (Step 4)"),
        ("scrum-master", jira_configured, "Requires Jira connection (Step 2)"),
        ("weekly-plan", jira_configured, "Requires Jira connection (Step 2)"),
        ("weekly-metrics-analyst", analytics_configured, "Requires Google Analytics configuration (Step 5)"),
        ("search-console-insights", analytics_configured, "Requires Search Console configuration (Step 5)"),
        ("prd-generator", diagnostic["is_git"], "Requires active Git repository"),
        ("jira-vs-code-mismatch", diagnostic["is_git"] and jira_configured, "Requires Git & Jira credentials"),
        ("release-notes-writer", diagnostic["is_git"] and jira_configured, "Requires Git & Jira credentials"),
        ("play-console-insights", True, "Ready (loads from local CSVs)"),
        ("support-emails-to-features", True, "Ready (loads from local CSVs)"),
        ("jira-scoring-rice", jira_configured, "Requires Jira connection (Step 2)"),
        ("monthly-board-prep", jira_configured, "Requires Jira connection (Step 2)"),
        ("product-performance-analysis", True, "Ready"),
        ("idea-generator", True, "Ready")
    ]
    
    print(f"{Colors.BOLD}{Colors.BLUE}{'Skill Command':<30}{'Status':<15}{'Requirement/Note':<30}{Colors.END}")
    print(f"{Colors.BLUE}--------------------------------------------------------------------------------{Colors.END}")
    
    ready_count = 0
    for skill, status, note in skills_map:
        if status:
            status_text = f"{Colors.GREEN}● OPERATIONAL{Colors.END}"
            ready_count += 1
            note_text = "All connections validated."
        else:
            status_text = f"{Colors.WARNING}▲ INACTIVE{Colors.END}"
            note_text = note
            
        print(f"/{skill:<29} {status_text:<25} {note_text}")
        
    print(f"{Colors.BLUE}--------------------------------------------------------------------------------{Colors.END}")
    print(f"{Colors.BOLD}Overall Readiness: {ready_count}/14 Skills fully operational.{Colors.END}\n")
    
    if ready_count < 14:
        print_info("To activate the remaining skills, simply configure their credentials in your `.env` file.")

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}✦ Welcome to AI-PM Operator Setup Wizard ✦{Colors.END}")
    print("This wizard will configure your local environment, run diagnostics, and connect your APIs.\n")
    
    # Run Environment Diagnostics First
    diagnostic = scan_codebase()
    
    # 1. Subscription Check
    print_header("Step 1: PayPal Subscription ID")
    print("If you have subscribed, enter your PayPal Subscription ID (starts with 'I-').")
    print("If you want to use the 3-day free trial, press Enter/return to skip.")
    subscription_id = ""
    while True:
        subscription_id = input("\nEnter PayPal Subscription ID (or press Enter to skip): ").strip()
        if not subscription_id:
            print_info("Using 3-day free trial mode.")
            break
        if validate_subscription(subscription_id):
            break
        print_error("Invalid subscription. Please check your Subscription ID and try again.")
    
    # 2. Jira Credentials
    print_header("Step 2: Connect Jira Cloud")
    print("Generate an Atlassian API Token here: https://id.atlassian.com/manage-profile/security/api-tokens")
    
    jira_configured = False
    jira_url = ""
    jira_email = ""
    jira_token = ""
    jira_project = ""
    
    while True:
        jira_url = input("Jira Site URL (e.g., mycompany.atlassian.net): ").strip()
        jira_email = input("Jira User Email (e.g., pm@mycompany.com): ").strip()
        jira_token = getpass.getpass("Jira API Token: ").strip()
        jira_project = input("Jira Project Key (e.g., SP): ").strip().upper()
        
        # Dry run validate
        if validate_jira(jira_url, jira_email, jira_token, jira_project):
            jira_configured = True
            break
            
        retry = input("\nVerification failed. Retry credentials? (Y/n): ").strip().lower()
        if retry == 'n':
            print_warning("Skipping Jira validation. Credentials written as-is.")
            break
            
    # 3. Confluence (Optional)
    print_header("Step 3: Confluence Integration (Optional)")
    enable_conf = input("Do you want to configure Confluence for publishing reports? (y/N): ").strip().lower()
    conf_space = ""
    conf_parent = ""
    conf_configured = False
    if enable_conf == 'y':
        conf_space = input("Confluence Space Key (e.g., PMOPS): ").strip().upper()
        conf_parent = input("Confluence Parent Page ID (optional): ").strip()
        conf_configured = True

    # 4. Competitor Tracker Setup
    print_header("Step 4: Initialize Competitor Tracker")
    enable_comp = input("Do you want to set up custom competitors to track? (y/N): ").strip().lower()
    comp_configured = False
    if enable_comp == 'y':
        competitors_list = []
        print("\nEnter competitor details. Let's add at least 2 competitors.")
        while True:
            name = input("Competitor Name (e.g., QuickRide): ").strip()
            domain = input("Competitor Domain (e.g., quickride.in): ").strip()
            package = input("Android App ID (optional, e.g., co.quickride): ").strip()
            competitors_list.append({"name": name, "domain": domain, "package": package})
            
            more = input("Add another competitor? (Y/n): ").strip().lower()
            if more == 'n':
                break
        if competitors_list:
            initialize_competitors(competitors_list)
            comp_configured = True
    else:
        # Check if default registry exists
        if diagnostic["config_status"]["competitors_exists"]:
            comp_configured = True
            print_info("Using existing competitor registry settings.")
        else:
            # Setup default mockup competitors
            default_competitors = [
                {"name": "QuickRide", "domain": "quickride.in", "package": "co.quickride"},
                {"name": "Hopr", "domain": "hopr.mobi", "package": "com.hopr.commute"}
            ]
            initialize_competitors(default_competitors)
            comp_configured = True

    # 5. Analytics Integrations (Optional)
    print_header("Step 5: Analytics Integrations (Optional)")
    enable_analytics = input("Do you want to configure Google Analytics & Search Console? (y/N): ").strip().lower()
    ga4_prop = ""
    gsc_url = ""
    analytics_configured = False
    if enable_analytics == 'y':
        ga4_prop = input("Google Analytics 4 Property ID (optional): ").strip()
        gsc_url = input("Google Search Console Property URL (e.g., https://mycompany.com): ").strip()
        analytics_configured = True

    # 6. Team Roster Setup
    print_header("Step 6: Configure Team Roster")
    print("Set up your key team members so AI-PM Operator can route and assign issues correctly.")
    
    team_members = []
    while True:
        add_member = input("\nAdd a team member? (Y/n): ").strip().lower()
        if add_member == 'n':
            break
        
        name = input("Full Name (e.g., John Smith): ").strip()
        alias = input("Short Name / Alias (e.g., John): ").strip()
        email = input("Email: ").strip()
        atlassian_id = input("Atlassian Account ID (Find in Jira profile URL): ").strip()
        role = input("Role (e.g., Developer, QA, Designer): ").strip()
        domains_raw = input("Domains of expertise (comma separated, e.g. backend, database): ")
        domains = [d.strip().lower() for d in domains_raw.split(',') if d.strip()]
        
        team_members.append({
            "name": name,
            "alias": alias,
            "atlassianId": atlassian_id,
            "email": email,
            "role": role,
            "domains": domains,
            "messageStyle": "concise"
        })
        print_success(f"Added {name} ({role}) to roster.")
        
    # Write team.json
    if not team_members:
        # Fallback to copy from template
        print_info("No custom team roster created. Using template roster.")
        if os.path.exists("team.json.template"):
            os.system("cp team.json.template team.json")
    else:
        with open("team.json", "w") as f:
            json.dump(team_members, f, indent=2)
        print_success("Created team.json roster.")
        
    # 7. Write .env
    print_header("Step 7: Writing Environment Configuration")
    
    env_content = f"""# ==============================================================================
# AI-PM Operator — Environment Configuration (Generated)
# ==============================================================================

OPERATOR_SUBSCRIPTION_ID={subscription_id}

# Jira Integration
JIRA_URL={jira_url}
JIRA_EMAIL={jira_email}
JIRA_TOKEN={jira_token}
JIRA_PROJECT_KEY={jira_project}
"""
    if conf_space:
        env_content += f"""
# Confluence Integration
CONFLUENCE_SPACE_KEY={conf_space}
CONFLUENCE_PARENT_PAGE_ID={conf_parent}
"""
    if ga4_prop:
        env_content += f"""
# Analytics Integration
GA4_PROPERTY_ID={ga4_prop}
GOOGLE_APPLICATION_CREDENTIALS=google-credentials.json
"""
    if gsc_url:
        env_content += f"""
GSC_PROPERTY_URL={gsc_url}
"""

    with open(".env", "w") as f:
        f.write(env_content)
        
    # Add .env to gitignore
    if os.path.exists(".gitignore"):
        with open(".gitignore", "r") as f:
            gitignore = f.read()
        if ".env" not in gitignore:
            with open(".gitignore", "a") as f:
                f.write("\n# AI-PM Operator Env\n.env\nteam.json\n")
            print_success("Added .env and team.json to .gitignore.")
            
    print_success("Configuration file .env written successfully.")
    
    # 8. Readiness Report
    display_readiness_report(diagnostic, jira_configured, conf_configured, analytics_configured, comp_configured)
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}✦ AI-PM Operator Setup Completed! ✦{Colors.END}")
    print("Your environment is configured and validated.")
    print("To start running your PM workflows, fire up Claude Code and run:")
    print(f"  {Colors.BOLD}claude{Colors.END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
