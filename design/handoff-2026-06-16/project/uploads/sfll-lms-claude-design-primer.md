# SFLL — League Management System
### A primer for Claude Design

> **Naming note.** This system is being renamed from "Player Database" to **SFLL — League Management System** (sometimes shortened to LMS). The old name will keep appearing in code, docs, and the repo URL until the global rename lands. Treat the new name as canonical.
>
> **Repo:** `github.com/sfll-org/player-database` (will become `sfll-org/league-management-system`). Clone to `~/Git/` before working in Claude Code.

---

## 1. What SFLL is

South Florida Little League is a volunteer-run youth baseball and softball organization. Several hundred kids, ~12 teams per season, two seasons a year (Spring and Fall), plus All-Stars, tournaments, and umpire scheduling on top. Nate runs operations. The people doing the work are coaches, board members, and parents — almost none of them are technical, and turnover is high. Anything that depends on one person remembering how something works will fail within a season.

The administrative reality the tool is fighting:

- **Sources of truth are scattered.** Registration data lives in one SaaS, payments in another, rosters in spreadsheets, contact info in coaches' phones, umpire schedules in shared docs, equipment inventory in someone's garage.
- **Compliance has teeth.** Background checks, concussion certifications, coach training, age/division eligibility — all required, all auditable, all easy to lose track of.
- **Volunteers churn.** Board members and head coaches turn over every 1–2 years. Tribal knowledge evaporates.
- **Communication is high-volume and low-quality.** Group texts, email blasts, hand-written notes from the snack stand.

The League Management System is meant to be the durable backbone underneath all of that — the place where the real state of the league lives, and a clear UI that volunteers can actually use without training.

## 2. What the tool is for

The product brief in one sentence: **a league operations console where the board can see and manage everything that matters about players, families, volunteers, teams, and the season — without depending on the registration vendor or any one person's memory.**

Core jobs it needs to do well:

- Maintain the canonical roster: players, families, coaches, board members, umpires, with the relationships between them.
- Track compliance state per person (background check status, certifications, expirations).
- Support seasonal operations: division/team assignments, schedule, evaluations, draft, All-Stars selection.
- Surface "what needs attention this week" — gaps, expiring certs, kids without a team, families with unpaid balances.
- Be readable on a phone at the field. Half of all use happens between innings on someone's phone.

What it is **not**:

- Not a public-facing site for parents to register. That stays in the registration vendor for now.
- Not a payments processor. Read-only reflection of payment state at most.
- Not a generic CRM. Every screen should feel like it knows it's about a Little League.

## 3. Users and their primary jobs

| Role | What they do here |
|---|---|
| **Operations lead (Nate)** | Daily ops, compliance audit, cross-cutting reporting, anything that lands on the league's desk. |
| **Board members (~8)** | Division-level views: their division's rosters, coaches, schedules. Weekly check-ins on what needs action. |
| **Player Agent** | Roster integrity, eligibility decisions, draft coordination. Power user. |
| **Coaches (~24)** | Their team's roster + contact info + practice/game schedule. Read-mostly. Mobile-first. |
| **Umpire-in-Chief** | Umpire roster, certifications, game assignments, payment status. |
| **Treasurer** | Read-only view of payment/balance state per family. |

The "design for the coach on their phone at the field" constraint and the "design for the ops lead doing audit work on a laptop" constraint pull in different directions. The tool needs to honor both — the same data model, but views that meet each user where they are.

## 4. Current state

This section is intentionally thin so Claude Code can fill it in by reading the repo. The repo is private and only resolves with auth, so deep inspection happens after Nate clones it.

**Stack and structure — to be confirmed from the repo:**

- Backend framework
- Frontend framework / templating
- Database
- Auth / session model
- Deployment target
- Test coverage
- Open PRs and what they're for

**Existing screens / surfaces — to be enumerated:**

- Authenticated home / dashboard
- Player list / detail
- Family list / detail
- Team / division views
- Compliance / certification tracking
- Admin / settings

**What is built vs. stubbed vs. missing.** Claude Code should produce a one-table summary.

> **Instruction to Claude Code:** Before designing anything, walk the repo end-to-end. Read `README.md`, the routes/controllers, the schema (migrations or ORM models), and the templates/components. Produce a "Current State" appendix in this primer with: stack, top-level directory map, list of routes/screens with what each does, data model summary, deployment story, and the 3–5 most obvious technical-debt items. That appendix is what Claude Design will lean on.

## 5. The design opportunity

What Claude Design is being asked to do:

1. **Define the visual and interaction language for the LMS.** Right now the UI is functional but un-designed. The product needs a consistent look that reads as "youth sports nonprofit run by competent people" — friendly, legible, not corporate, not childish. A real palette, type system, component set, and density model.
2. **Design the 5–8 screens that matter most.** In rough priority: the operations dashboard (Nate's daily view), the player detail page, the team/coach view (mobile-first), the compliance audit view, the season-setup wizard, the family detail page, and the "needs attention" surface that lives across multiple roles.
3. **Solve the desktop ↔ mobile split.** Same data, two very different jobs. Don't just shrink the desktop layout for phones — design the field-side mobile flow as a first-class experience.
4. **Propose a navigation model.** Today's navigation is implicit. We need a top-level information architecture that scales from "show me one kid's record" to "show me the whole league's compliance status."
5. **Suggest where the product is currently fighting itself.** Patterns we copied from generic admin tools that aren't earning their keep. UI that reflects how the data is stored rather than how the user thinks about it. Honest critique is more valuable than polish.

## 6. Constraints and non-negotiables

- **Volunteers must be able to use this without training.** If a coach has to be onboarded to find their team's roster, the design has failed.
- **Phone-readable.** Field-side use is real. Not "responsive as an afterthought" — designed for it.
- **Print-friendly for a small set of views** (rosters, dugout cards). Coaches still print things.
- **No login dependency the average parent doesn't already have.** Realistic auth: email magic link or Google. No password gymnastics.
- **Accessibility matters and won't be optional.** This serves families with a wide range of abilities and ages.
- **Stack stability.** Whatever the current stack is, plan around it. This isn't a redesign-and-rewrite — it's a design-led iteration on a running system.
- **Self-hosted, no SaaS surveillance.** The league owns its data. Any analytics, error tracking, or third-party widgets need a defensible reason.

## 7. Out of scope (for now)

- Public registration / parent-facing signup flows.
- Payment processing.
- Native mobile apps. Web-first, installable as PWA at most.
- AI features in the UI. (We use AI heavily in the *operations* of building this; we don't need AI features inside the product itself yet.)
- Multi-tenant / multi-league. SFLL only.

## 8. How Claude Design should deliver

Open to whatever format works, but a useful shape would be:

- **A design rationale doc** explaining the system being proposed (palette, type, density, voice) and why.
- **High-fidelity mocks of the priority screens**, desktop and mobile.
- **A component inventory** — buttons, forms, table rows, status pills, navigation chrome — with usage rules.
- **Concrete redlines or callouts** on the 3–5 places where the current UI is most actively hurting users, with a suggested fix for each.
- **An "if we had two more weeks" section.** What didn't make the cut, ranked.

Working in Figma is fine; final handoff should include a way to extract tokens (colors, type, spacing) into code.

## 9. Working notes

- The system runs at SFLL scale (hundreds of records, dozens of concurrent users at peak), not enterprise scale. Optimize for clarity, not load.
- Tone in microcopy should match the league: direct, warm, occasionally funny, never corporate. Error messages should read like a competent ops person wrote them, not a legal team.
- The board has a slight aesthetic preference for navy/red (loose ties to the league colors). Not a hard constraint — Claude Design should propose what serves the product, not what flatters the board.

---

## Appendix A — Handoff to Claude Code

When this document moves into Claude Code, please:

1. **Clone the repo.** It's currently `sfll-org/player-database`. Once the rename lands it will be `sfll-org/league-management-system`.
2. **Audit it.** Fill in Section 4 (Current state) — stack, schema, routes/screens, data model, deployment, tech-debt highlights.
3. **Update naming.** Anywhere "Player Database" appears in user-facing strings, treat that as a rename target (the global rename task is tracked in Plane under project SFLL).
4. **Produce a "Current State" appendix** at the bottom of this primer with everything Claude Design will need that isn't in the body above.
5. **Flag gaps.** Anything in the spec that doesn't match what the code actually does — call it out so Nate can reconcile before design starts.

## Appendix B — Reference

- **Plane project:** SFLL (`15deb480-894a-43f2-af55-77621e881566`)
- **Confluence hub:** page 17563649 on prodromou.atlassian.net
- **GitHub:** `sfll-org/player-database` (private; ask Nate for access if needed)
- **Rename task in Plane:** filed 2026-05-15
- **Operations lead:** Nate Prodromou (nate@prodromou.com)
