# AGENTS.md — SFLL Player Database

## Project Overview

**South Florida Little League** — Player database, volunteer tracking, and umpiring operations for SFLL.

**Status:** Active Development
**Visibility:** Private

## Tech Stack

- Stack details: See Confluence

## Links

- **Plane Project:** SFLL
  https://plane.prodromou.com/prodromou/projects/15deb480-894a-43f2-af55-77621e881566/issues
  Project ID: `15deb480-894a-43f2-af55-77621e881566`

- **Confluence Hub:** Page 17563649
  https://prodromou.atlassian.net/wiki/spaces/Operations/pages/17563649

## Tier 3 Operating Rules

### Git Workflow

\`\`\`bash
git config user.name "Prodromou Bot"
git config user.email "bot@prodromou.com"
\`\`\`

**Branch naming:**
\`\`\`
bot/{TICKET-KEY}-short-description
\`\`\`
Example: `bot/SFLL-15-player-import`

**Commits:**
\`\`\`
SFLL-15: Add player import feature

Co-Authored-By: Prodromou Bot <bot@prodromou.com>
\`\`\`

### Plane Permissions

**You can:**
- Update work item status
- Add comments and notes
- Link related work items

**You cannot:**
- Create new tasks
- Modify task descriptions or specs
- Reprioritize or reassign work
- Delete work items

If blocked or unsure about a requirement, move the task back to "Todo", unassign yourself, and leave a comment explaining the blocker.

### Confluence Updates

**You can update:**
- "Current State" sections (progress reports)
- "Known Issues" sections (bugs found during implementation)

**You cannot:**
- Rewrite architectural decisions
- Restructure pages
- Change specs or requirements

If you find a spec discrepancy, leave a Plane comment — do not "fix" the spec yourself.

### Follow-up Work

If your completed task spawned follow-up work you cannot create tasks for, label it with `needs-followup` in Plane and leave a comment describing the follow-up.

## Configuration

- **Confluence Space:** Operations
- **Confluence Cloud ID:** `08465a75-9bd1-4bb7-9cd1-c5998fe88d47`
- **Plane Workspace:** prodromou (https://plane.prodromou.com)

---

Last updated: 2026-03-04
