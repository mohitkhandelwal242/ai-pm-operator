#!/usr/bin/env bash

# ==============================================================================
# AI-PM Operator — Installer Script
# ==============================================================================

set -euo pipefail

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}✦ Initializing AI-PM Operator Installer ✦${NC}\n"

# 1. Verify we are in a Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo -e "${RED}❌ Error: AI-PM Operator must be installed at the root of a Git repository.${NC}"
  echo -e "Please run ${BOLD}git init${NC} or navigate to your project repository, then re-run the installer."
  exit 1
fi

# 2. Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo -e "${RED}❌ Error: Python 3 is required but was not found on your system.${NC}"
  echo -e "Please install Python 3 and try again."
  exit 1
fi

# 3. Create directory structures
echo -e "Creating directory structures..."
mkdir -p .claude/skills
mkdir -p .claude/commands
mkdir -p .claude/knowledge
mkdir -p tools

# 4. Download product package from GitHub
echo -e "Downloading package components from GitHub..."
git clone --depth 1 https://github.com/mohitkhandelwal242/ai-pm-operator.git /tmp/ai-pm-operator

# 5. Extract files
echo -e "Extracting package components..."
cp -r /tmp/ai-pm-operator/.claude .
cp -r /tmp/ai-pm-operator/tools .
cp /tmp/ai-pm-operator/.env.example .
cp /tmp/ai-pm-operator/team.json.template .
cp /tmp/ai-pm-operator/README.md .
rm -rf /tmp/ai-pm-operator

echo -e "${GREEN}✓ Package components extracted successfully!${NC}"

# 6. Run the onboarding wizard
echo -e "Starting the setup wizard...\n"
python3 tools/setup-wizard.py
