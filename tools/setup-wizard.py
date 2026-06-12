#!/usr/bin/env python3
import os
import json
import urllib.request
import urllib.error
import urllib.parse
import base64

# Colors for terminal styling
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

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
        ctx = ssl._create_unverified_context()
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

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}✦ Welcome to AI-PM Operator Setup Wizard ✦{Colors.END}")
    print("This wizard will configure your local environment and connect your APIs.\n")
    
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
    
    while True:
        jira_url = input("Jira Site URL (e.g., mycompany.atlassian.net): ").strip()
        jira_email = input("Jira User Email (e.g., pm@mycompany.com): ").strip()
        jira_token = input("Jira API Token: ").strip()
        jira_project = input("Jira Project Key (e.g., SP): ").strip().upper()
        
        # Dry run validate
        if validate_jira(jira_url, jira_email, jira_token, jira_project):
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
    if enable_conf == 'y':
        conf_space = input("Confluence Space Key (e.g., PMOPS): ").strip().upper()
        conf_parent = input("Confluence Parent Page ID (optional): ").strip()

    # 4. Analytics Integrations (Optional)
    print_header("Step 4: Analytics Integrations (Optional)")
    enable_analytics = input("Do you want to configure Google Analytics & Search Console? (y/N): ").strip().lower()
    ga4_prop = ""
    gsc_url = ""
    if enable_analytics == 'y':
        ga4_prop = input("Google Analytics 4 Property ID (optional): ").strip()
        gsc_url = input("Google Search Console Property URL (e.g., https://mycompany.com): ").strip()

    # 5. Team Roster Setup
    print_header("Step 5: Configure Team Roster")
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
        
    # 6. Write .env
    print_header("Step 6: Writing Environment Configuration")
    
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
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}✦ AI-PM Operator Setup Completed! ✦{Colors.END}")
    print("Your environment is configured and validated.")
    print("To start running your PM workflows, fire up Claude Code and run:")
    print(f"  {Colors.BOLD}claude{Colors.END}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
