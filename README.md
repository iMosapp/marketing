# i'M On Social (iMOS)

Relationship OS for automotive sales — React Native (Expo) + FastAPI + MongoDB.

## Internal Documentation
The living internal docs are in `/app/docs/` and auto-sync into the app (Admin → Docs) on every deploy:

- [`docs/PRODUCT_REQUIREMENTS.md`](docs/PRODUCT_REQUIREMENTS.md) — vision, personas, full feature scope, backlog
- [`docs/OPERATIONS_MANUAL.md`](docs/OPERATIONS_MANUAL.md) — environments, release workflow, all 21 scheduled automations, admin how-tos, troubleshooting
- [`docs/APP_SCOPE.md`](docs/APP_SCOPE.md) — architecture, backend domains, API surfaces, data model, screen map, security model

Change log of shipped work: [`memory/CHANGELOG.md`](memory/CHANGELOG.md)

## Release workflow
1. Save to GitHub → 2. Deploy (backend/web) → 3. `git pull` → 4. `cd frontend && eas update --branch production --message "..."`
