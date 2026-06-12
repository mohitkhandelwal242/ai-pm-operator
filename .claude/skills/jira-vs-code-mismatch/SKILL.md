---
name: jira-vs-code-mismatch
description: "Jira vs Code Mismatch Detector. Cross-references Jira Acceptance Criteria (AC) against local Git diffs to detect spec-code drift before committing. Use when checking spec drift, verification code check, or '/jira-vs-code'."
argument-hint: "[--issue ISSUE-KEY] [--branch BRANCH_NAME] [--all-diffs]"
allowed-tools: [Read, Write, Bash, WebSearch]
---

# Jira vs Code Mismatch Detector

You are a **Quality Assurance PM Advisor**. Your goal is to scan current Git changes (diffs) and cross-reference them against the specifications and Acceptance Criteria (AC) of the corresponding Jira issue. This helps prevent scope drift, gold-plating, or missed requirements before code is committed or pushed to production.

---

## Input

`$ARGUMENTS`
- `--issue ISSUE-KEY`: Specify the Jira issue key directly (e.g., `${PROJECT_KEY}-123`).
- `--branch BRANCH_NAME`: Check a remote or local branch instead of the current working directory branch.
- `--all-diffs`: Audit all files in the current branch against the target branch (`origin/main`) rather than just unstaged/staged changes.

---

## Phase 0 — Resolve Branch & Jira Issue Key

1. **Auto-detect branch & issue**:
   - Run a bash command to get the active branch name:
     ```bash
     git rev-parse --abbrev-ref HEAD
     ```
   - Extract the Jira issue key from the branch name using pattern matching (e.g., `feature/SP-1234-auth-flow` contains `SP-1234`).
   - Substitute the project prefix to match your workspace: `${PROJECT_KEY}-\d+`.
2. **Fallback**:
   - If no issue key is found in the branch name and `--issue` was not provided, ask the user:
     ```
     Could not detect a Jira issue key from branch name [branch_name].
     Please enter the Jira issue key to audit (e.g., ${PROJECT_KEY}-123):
     ```

---

## Phase 1 — Fetch Jira Specifications & AC

Use `tools/jira-api.py` to fetch full issue context:
```bash
python3 tools/jira-api.py get ${ISSUE_KEY}
python3 tools/jira-api.py comments ${ISSUE_KEY}
```

Extract the following data fields:
- **Title / Summary**: High-level capability being built.
- **Description**: Read description carefully. Extract any Gherkin syntax (`Given/When/Then`), numbered lists, or bullet points under headers like "Acceptance Criteria", "AC", "Requirements", or "Testing Scenarios".
- **Comments**: Look for requirements updates or clarifications from the PM or tech leads.

---

## Phase 2 — Parse Acceptance Criteria

Compile all gathered ACs into a discrete checklist:
- Each AC must represent a single, testable condition (e.g., "AC-1: User sees validation error if password is < 8 chars").
- Deduplicate and normalize terms.

---

## Phase 3 — Extract Local Git Diffs

Acquire the code changes to analyze based on the configured mode:
- **Unstaged changes (default)**:
  ```bash
  git diff
  ```
- **Staged changes**:
  ```bash
  git diff --cached
  ```
- **Branch-level diffs (against origin/main)**:
  ```bash
  git diff origin/main...HEAD
  ```

Parse the diff output to identify:
- All files added, modified, or deleted.
- Added functions, files, databases, routes, configuration parameters, and test cases.

---

## Phase 4 — Semantic Compliance Audit

For each parsed Acceptance Criteria (AC), audit the diff to check if the requirement is satisfied.

### 1. Code Implementation Check
- Scan the code additions for matches to the AC (e.g., if AC states "validate email domain", check if domain parsing or regex validations were added).
- Map the AC to specific files and line numbers where the implementation is found.

### 2. Test Case Compliance
- Verify if unit tests or integration tests were added or modified to validate this AC.
- If no matching test file modifications are found in the diff, flag a warnings: `Missing test validation for AC-X`.

---

## Phase 5 — Scope Drift (Gold-Plating) Detection

Identify additions in the code that do NOT correspond to any Jira AC:
- Flag brand-new modules, classes, API routes, or features introduced in the diff that aren't mentioned in the Jira issue.
- Mark these as **Scope Drift**. Drift represents a risk (untested code, diverging specs, undocumented behavior).

---

## Phase 6 — Generate Mismatch Report

Output a clean, readable audit report to the console and write it to `reports/mismatch-audit-${ISSUE_KEY}.md`:

```markdown
# Spec Compliance & Drift Report: {ISSUE_KEY}
**Branch**: {branch_name}
**Date**: {current_time}

## Summary
- **Acceptance Criteria Audited**: {total_ac_count}
- **AC Met**: {met_count}
- **AC Missing/Incomplete**: {missing_count}
- **Scope Drift Detected**: {drift_count}

---

## Acceptance Criteria Matrix

| ID | Jira Requirement | Implementation Status | Code Evidence | Test File |
|---|---|---|---|---|
| AC-1 | Email validation strictly checks domain | ✅ Met | `UserService.ts:L45` | `UserService.test.ts` |
| AC-2 | Show modal alert on success | ❌ Missing | No matching UI code | None |
| AC-3 | Cache token locally | ⚠️ Partial | `AuthService.ts:L89` (no TTL logic) | `AuthService.test.ts` |

---

## Scope Drift Warnings (Gold-Plating)
- **Warning 1**: Added `StripeWebhookHandler.ts`. No payment requirements exist in this Jira issue.
- **Warning 2**: Added helper functions for profile picture upload in `UserProfile.kt`, but this issue only covers username edits.

---

## Audit Verdict

### [VERDICT] 🔴 FAIL | 🟡 WARNING | ✅ PASS

- **PASS**: All ACs are met and tested; zero scope drift detected.
- **WARNING**: All ACs are met, but testing is missing, or minor scope drift is present.
- **FAIL**: Any AC is missing implementation, or critical/unrelated modules were added without specification.
```

## Phase 7 — Recommended Actions
Offer to:
1. Re-run with `--all-diffs` to double-check against another baseline branch.
2. Generate unit test templates for any AC that is missing test cases.
3. Automatically append the audit report summary as a comment to the Jira ticket to warn reviewers before merging.
