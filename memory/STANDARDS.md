# IMOS App - Technical Standards & Conventions

> **IMPORTANT:** This document defines the mandatory standards for the IMOS application.
> All future development MUST follow these conventions. DO NOT deviate without explicit user approval.

## API Route Standards

### Main API Routes
All application API endpoints MUST use versioned paths:
```
/api/v1/{resource}
```

**Examples:**
- `/api/v1/organizations`
- `/api/v1/accounts`
- `/api/v1/users`
- `/api/v1/quotes`
- `/api/v1/individuals`
- `/api/v1/discount-codes`
- `/api/v1/partner-agreements`
- `/api/v1/company-directory`
- `/api/v1/shared-inboxes`
- `/api/v1/pending-users`

### External Webhooks
Third-party integration webhooks use a separate path:
```
/api/webhooks/{type}
```

**Examples:**
- `/api/webhooks/inventory`
- `/api/webhooks/users`
- `/api/webhooks/twilio`

### Authentication Routes
```
/api/v1/auth/login
/api/v1/auth/register
/api/v1/auth/logout
/api/v1/auth/refresh
```

## Database Standards

### Collection Naming
- Use `lowercase_snake_case`
- Keep names simple and descriptive

**Collections:**
- `users`
- `organizations`
- `accounts` (formerly stores)
- `quotes`
- `individuals`
- `inventory_items`
- `discount_codes`
- `partner_agreements`
- `company_directory`
- `shared_inboxes`
- `pending_users`
- `calls`
- `campaigns`
- `contacts`

### Field Naming
- Use `snake_case` for all fields
- Use `_id` suffix for reference fields (e.g., `organization_id`, `user_id`)
- Use ISO 8601 format for dates stored as strings

## Frontend Standards

### API Service
- Single centralized API configuration
- Base URL from environment variable: `REACT_APP_BACKEND_URL`
- All API calls go through `/api/v1/...`

### Naming Conventions
- **UI Label:** "Account" (NOT "Store")
- **Brand Name:** "IMOS" or "imosapp"
- Components: PascalCase (e.g., `UserList.tsx`)
- Hooks: camelCase with `use` prefix (e.g., `useAuth.ts`)

## Code Organization

### Backend Structure
```
/app/backend/
├── models/          # Pydantic models
├── routes/          # API route handlers
├── services/        # Business logic
├── utils/           # Helper functions
└── server.py        # Main app, router registration
```

### Frontend Structure
```
/app/frontend/
├── app/
│   ├── (app)/       # Authenticated routes
│   ├── (auth)/      # Auth routes
│   └── ...
├── components/      # Reusable components
├── services/        # API services
└── hooks/           # Custom hooks
```

## Router Registration (server.py)

All routers MUST be registered with the `/api/v1` prefix in `server.py`:
```python
app.include_router(users_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
# ... etc
```

Webhook routers use `/api/webhooks`:
```python
app.include_router(inventory_webhooks_router, prefix="/api/webhooks")
```

---

**Last Updated:** December 2025
**Approved By:** User
