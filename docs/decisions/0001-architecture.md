# 0001 — Layered modular monolith with an inward dependency rule

Date: 2026-11-03 · Status: implemented as planned (plan.md §4)

## Decision

One FastAPI application, one PostgreSQL database, four layers with a strict
inward dependency rule: `presentation → application → domain`, plus
`application → persistence port`. The domain (`policy.py`, `calendar.py`)
imports no framework, no ORM, no HTTP. The service depends on the
`ReviewRepository` port; SQLAlchemy is an adapter behind it. Wiring happens in
`create_app` (composition root).

## Why

Single-deployable simplicity with transactional consistency, while keeping the
seams (port/adapter, pure policy) that make the interesting parts testable
without infrastructure and leave extraction possible if a concrete need ever
appears.

## Consequence

The service is covered through real-PostgreSQL API tests rather than mocks;
the policy and calendar are covered by pure unit tests; no test doubles exist
for the repository (none needed — the adapter is thin, and the real database
is cheap to run locally).
