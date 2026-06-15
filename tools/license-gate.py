#!/usr/bin/env python3
"""
license-gate.py — PreToolUse gate that puts EVERY AI-PM Operator skill behind the
subscription/trial check.

Wired in .claude/settings.json as a PreToolUse hook on the `Skill` tool. Claude Code
runs this before any skill is used:
  - exit 0  -> allow the skill to run (license active, or trial still valid)
  - exit 2  -> BLOCK the skill; stderr is shown to the user/Claude with the subscribe info

It simply shells out to `jira-api.py check-license` (the single source of truth for the
Gumroad license + server/local 7-day trial logic) and maps its result to the hook's
block/allow convention. Fast for licensed users (license cached 24h) and trial users
(server verdict cached ~30 min); never makes the gate the bottleneck.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(HERE, "jira-api.py"), "check-license"],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        # If the check itself errors out, don't hard-block the user — fail open so a
        # transient problem with the gate never bricks a paying customer's session.
        sys.exit(0)

    if result.returncode == 0:
        sys.exit(0)  # allow

    # Blocked: surface the subscribe message (printed by check-license) to the user.
    msg = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    sys.stderr.write((msg + "\n" + err).strip() + "\n")
    sys.exit(2)  # exit code 2 = block the tool call


if __name__ == "__main__":
    main()
