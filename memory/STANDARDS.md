# IMOS App - Technical Standards & Conventions

> **IMPORTANT:** This document defines the mandatory standards for the IMOS application.
> All future development MUST follow these conventions. DO NOT deviate without explicit user approval.

## API Route Standards

### Main API Routes
All application API endpoints use the `/api/` prefix:
```
/api/{router-prefix}/{endpoint}
```

**Current Route Structure:**
- `/api/admin/organizations` - Organization management
- `/api/admin/stores` - Account (Store) management
- `/api/admin/users` - User management
- `/api/admin/individuals` - Individual management
- `/api/admin/pending-users` - Pending user approvals
- `/api/admin/team/shared-inboxes` - Shared inbox management
- `/api/subscriptions/quotes` - Quote management
- `/api/subscriptions/discount-codes` - Discount code management
- `/api/partners/agreements` - Partner agreements
- `/api/directory/members` - Company directory
- `/api/lead-sources` - Lead source routing

### External Webhooks
Third-party integration webhooks use a separate path:
```
/api/webhooks/{type}
```

**Examples:**
- `/api/webhooks/inventory` - Inventory sync webhooks
- `/api/webhooks/user-created` - User sync webhooks
- `/api/webhooks/user-deleted` - User deletion webhooks
- `/api/webhooks/twilio/incoming` - Twilio SMS webhooks

### Authentication Routes
```
/api/auth/login
/api/auth/signup
/api/auth/change-password
/api/auth/forgot-password/request
/api/auth/forgot-password/verify
/api/auth/forgot-password/reset
```

## Database Standards

### Collection Naming
- Use `lowercase_snake_case`
- Keep names simple and descriptive

**Collections:**
- `users`
- `organizations`
- `stores` (displayed as "Accounts" in UI)
- `quotes`
- `individuals`
- `inventory_items`
- `discount_codes`
- `partner_agreements`
- `directory_members`
- `shared_inboxes`
- `lead_sources`
- `conversations`
- `contacts`
- `calls`
- `campaigns`
- `messages`

### Field Naming
- Use `snake_case` for all fields
- Use `_id` suffix for reference fields (e.g., `organization_id`, `user_id`)
- Use ISO 8601 format for dates stored as strings

## Frontend Standards

### API Service
- Single centralized API configuration at `/app/frontend/services/api.ts`
- Base URL from environment variable: `EXPO_PUBLIC_BACKEND_URL` or `REACT_APP_BACKEND_URL`
- All API calls go through `/api/...` prefix (handled by axios baseURL)

### Naming Conventions
- **UI Label:** "Account" (NOT "Store") - internal DB still uses `stores`
- **Brand Name:** "iMOs" or "imosapp"
- Components: PascalCase (e.g., `UserList.tsx`)
- Hooks: camelCase with `use` prefix (e.g., `useAuth.ts`)
- Pages: lowercase with dashes (e.g., `shared-inboxes.tsx`)

## Code Organization

### Backend Structure
```
/app/backend/
├── models/          # Pydantic models (e.g., inventory_models.py, webhook_models.py)
├── routers/         # API route handlers (one file per feature)
├── services/        # Business logic services
├── tests/           # Pytest test files
└── server.py        # Main FastAPI app, router registration
```

### Frontend Structure
```
/app/frontend/
├── app/
│   ├── (tabs)/      # Main tab navigation (inbox, contacts, dialer, more)
│   ├── admin/       # Admin panel pages
│   ├── auth/        # Authentication pages
│   ├── settings/    # User settings pages
│   └── ...
├── components/      # Reusable components
├── services/        # API services (api.ts)
├── hooks/           # Custom hooks
└── store/           # Zustand state management
```

## Router Registration (server.py)

All routers are registered under the `/api` prefix via api_router:
```python
# Create the api_router with /api prefix
api_router = APIRouter(prefix="/api")

# Include feature routers (they define their own sub-prefixes)
api_router.include_router(auth.router)      # /api/auth/...
api_router.include_router(admin.router)      # /api/admin/...
api_router.include_router(contacts.router)   # /api/contacts/...
# ... etc

# Include api_router in main app
app.include_router(api_router)
```

## Admin Panel Routes (Frontend)

All admin pages are under `/admin/` path:
- `/admin` - Main admin dashboard
- `/admin/organizations` - Organizations list
- `/admin/stores` - Accounts list
- `/admin/users` - Users list
- `/admin/individuals` - Individuals list
- `/admin/pending-users` - Pending user approvals
- `/admin/shared-inboxes` - Shared inbox management
- `/admin/quotes` - Quote management
- `/admin/discount-codes` - Discount codes
- `/admin/partner-agreements` - Partner agreements
- `/admin/directory` - Company directory
- `/admin/phone-assignments` - Twilio phone assignments
- `/admin/lead-sources` - Lead source routing

---

**Last Updated:** December 2025
**Approved By:** User
