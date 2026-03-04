# AGENTS.md — SFLL Player Database

## Project Overview
**SFLL Player Database** — SFLL player database and operations tools.
**Visibility:** Private

## Tech Stack
- Repository is currently bootstrap-level (README + agent context files)
- Application stack to be finalized as implementation starts

## Links
- **Plane Project:** SFLL
  https://plane.prodromou.com/prodromou/projects/15deb480-894a-43f2-af55-77621e881566/issues
  Project ID: `15deb480-894a-43f2-af55-77621e881566`
- **Confluence Hub:** None yet
  Create one if significant work is done on this project

## Tier 3 Operating Rules

You are operating as Tier 3 (Bot / bot@prodromou.com). Full rules are in the AI Agent Instructions:
https://prodromou.atlassian.net/wiki/spaces/Operations/pages/163850

### Git Identity
```
git config user.name "Prodromou Bot"
git config user.email "bot@prodromou.com"
```
Branch naming: `bot/{TICKET-KEY}-short-description`
Commit format: `{TICKET-KEY}-{number}: description`

### Plane
- You CAN: update work item status, add comments, link related items
- You CANNOT: create new tasks, modify task descriptions, reprioritize, reassign, delete
- If blocked: move task back to Todo, unassign yourself, comment explaining why
- If work spawns follow-up: label with `needs-followup`, describe in comment

### Confluence
- You CAN: update Confluence pages — all edits are attributed to bot@prodromou.com and audited by Tier 2
- Update "Current State" sections, "Known Issues", documentation that reflects completed work
- Add decisions you made during work to "Key Decisions"
- You CANNOT: delete pages or restructure page hierarchy
- If you find a spec discrepancy: leave a Plane comment, do NOT change the spec

### After Completing Work
Update BOTH Plane (status + reference-level comment) and Confluence (relevant project/system page).
See AI Agent Instructions for the full checklist.

## Configuration
- **Confluence Space:** Operations
- **Confluence Cloud ID:** `08465a75-9bd1-4bb7-9cd1-c5998fe88d47`
- **Plane Workspace:** prodromou (https://plane.prodromou.com)
