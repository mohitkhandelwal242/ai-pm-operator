# Scrum & Kanban Playbook

## Agile Cadence

| Ceremony | Frequency | Owner | Duration |
|---|---|---|---|
| Daily Standup | Daily (weekdays) | Product Manager | 15 min |
| Planning Session | Every 2 weeks (Monday) | Product Manager + Tech Leads | 2h |
| Review / Demo | Every 2 weeks (Friday) | Product Manager | 1h |
| Retrospective | Every 2 weeks (Friday) | Product Manager | 1h |
| Backlog Refinement | Weekly (Wednesday) | Product Manager + Tech Leads | 1h |

## Definition of Done (DoD)

A story is Done when ALL of the following are true:
- [ ] Code reviewed and approved (PR merged)
- [ ] QA tested on staging environment
- [ ] Acceptance criteria met (from Jira description)
- [ ] No known blockers or critical bugs
- [ ] Jira ticket moved to Done status

Missing any of these = DoD gap. Flag it.

## Blocker Escalation Protocol

1. **Day 0**: Blocker identified → Comment on Jira ticket.
2. **Day 1**: No resolution → Ping assignee via email.
3. **Day 2**: No resolution → Escalate to team lead (Backend/Mobile Lead).
4. **Day 3+**: Still open → Flag in scrum summary for the Product Manager.

Escalation owner by domain:
- Backend issues → Backend Lead
- Mobile issues → Mobile Lead
- Product/scope issues → Product Manager
- Process/org issues → Project Coordinator

## Sprint / Flow Health Thresholds

| Metric | Healthy | At Risk | Critical |
|--------|---------|---------|---------|
| Done% vs time elapsed% | Within 10% | 10-25% behind | >25% behind |
| Blockers open | 0 | 1-2 | 3+ |
| Stale In-Progress (>3d) | 0 | 1-2 | 3+ |
| Unestimated stories | 0 | 1-3 | 4+ |
| In-Review >2d | 0 | 1-2 | 3+ |

## Velocity Baseline
- Target: maintain consistent velocity sprint-over-sprint.
- Alert if velocity drops >20% from previous sprint.
- Track in `past_insights` in `scrum-state.md`.

## Comment Templates

### Stale issue nudge
```
Scrum sweep: no update on this for 3+ days. [Assignee] — any blockers? A quick status comment keeps the team unblocked. Please update status or add a note.
```

### Blocker flag
```
Scrum sweep: flagging this as a blocker (no movement in 3+ days). [Assignee] — what's needed to unblock this? I'll follow up in 24h if no update.
```

### PR review lag
```
Scrum sweep: this PR has been in review for 2+ days. Could a reviewer please prioritize this? Keeping PRs moving keeps the sprint on track.
```

### Unestimated story
```
Scrum sweep: this story has no story points. Please add an estimate so we can accurately track sprint velocity and completion.
```

### DoD gap
```
Scrum sweep: DoD check — this story appears to be missing [acceptance criteria / QA sign-off]. Please update before closing the ticket.
```

### Backlog grooming candidate
```
Scrum sweep: this issue has been in the backlog for 30+ days without refinement. Consider: does it still apply? If so, please add an estimate and assignee for the next sprint planning.
```

## Confluence Hygiene Checks
- Sprint review notes should link to the sprint in Jira.
- Decision pages should reference the Jira issue that prompted the decision.
- Meeting notes older than 2 sprints should be archived or linked to outcomes.

Confluence Space Key: `${CONFLUENCE_SPACE_KEY}`

CQL for recent pages: `space=${CONFLUENCE_SPACE_KEY} AND type=page AND created>=-14d ORDER BY created DESC`

## Focus Rotation Order

1. `sprint-health` / `flow-health` — weekly baseline check
2. `blockers` — highest urgency, run frequently
3. `stale-issues` — mid-sprint check
4. `pr-review-lag` — keeps code moving
5. `dod-gaps` — quality gate before sprint end
6. `backlog-grooming` — preparedness for next sprint
7. `velocity` / `throughput` — trend analysis
8. `confluence-hygiene` — documentation health
9. `ceremony-reminders` — day-of-week awareness

Repeat from the beginning after completing one full cycle.
