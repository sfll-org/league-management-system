# SFLL — League Management System

San Francisco Little League's internal Django app for player records, SES (Skills Evaluation Session) data, draft system, and communications.

Repository name (`player-database`) is the legacy slug from the original 2024 scope; the product name is the SFLL League Management System. Repo rename to `league-management-system` tracked in SFLL-90.

## Quick start

```bash
git clone https://github.com/sfll-org/player-database.git
cd player-database
cp .env.example .env
docker compose up -d
```

See `docs/deployment.md` for the full setup.

## Documentation

- `AGENTS.md` — project context, Plane/Confluence links, agent operating rules
- `docs/deployment.md` — environment setup
