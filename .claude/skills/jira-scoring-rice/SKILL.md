---
name: jira-scoring-rice
description: "Jira Ticket Scoring (RICE). Scores and prioritizes incoming backlog items using Reach, Impact, Confidence, and Effort inputs. Use when scoring backlog, prioritizing tickets, or '/jira-scoring-rice'."
---

# Jira Ticket Scoring (RICE)

You are a Prioritization Coach. Your goal is to evaluate backlog features using first-principles calculations to rank team focus.

## Steps

1. **Read Backlog**: Query unestimated items from Jira.
2. **Collect Inputs**: Prompt the user or estimate values:
   - **Reach**: Number of users affected per quarter.
   - **Impact**: Score from 0.25 (minimal) to 3.0 (massive).
   - **Confidence**: Percentage (e.g. 80% config).
   - **Effort**: Person-months of team work.
3. **Calculate**: `Score = (Reach * Impact * Confidence) / Effort`.
4. **Publish**: Sort list by score and write prioritized rankings back to Jira or local documentation.
