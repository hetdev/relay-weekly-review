# Relay — Take-Home Starter

Seed data and context for the take-home exercise. **Copy the contents into a fresh repo of your own** (please don't fork — forks are publicly linked to the source), then follow the instructions in the take-home prompt you received by email.

**Give your repo a name of your own choosing** — please don't keep `relay-analytics-starter`. A distinct name keeps your submission from being trivially discoverable alongside everyone else's.

You don't need to carry `docs/` into your own repo; it's context for you, not part of what you're building.

## Contents

| Path | What it is |
|---|---|
| `docs/PRODUCT_BACKGROUND.md` | One-page background on Relay, the fictional product |
| `docs/TICKET.md` | The ticket you're picking up (DASH-247) |
| `schema.sql` | Schema for the two seed tables (`accounts`, `activity_events`) |
| `seed.sql` | The seed dataset (~12.6k events across 20 accounts) |

## Using the data

- Load `schema.sql` then `seed.sql` into a relational database of your choice. The SQL is written portably; adapt types to your stack's migration tooling as needed (e.g., `TIMESTAMP` → `DATETIME2` on SQL Server).
- Wire the schema into **your own migrations** rather than hand-running the DDL — treat this like a real project.
- All `occurred_at` values are stored in **UTC**. Each account has an IANA `timezone`.
- `location` identifies the account's site/branch where the activity occurred; accounts range from single-site to 15 locations.
- Use this dataset as-is — don't regenerate, extend, or replace it. Treat it like production data: it's real-world messy, not idealized.

Questions? Route them through the recruiter, per the prompt.
