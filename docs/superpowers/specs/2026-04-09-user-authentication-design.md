# User Authentication System Design

**Date:** 2026-04-09
**Status:** Draft
**Scope:** Add username/password authentication with JWT sessions to EmergentCTI

## Context

EmergentCTI currently uses API key-only authentication. Users paste an API key into the login page, and it's stored in `localStorage` and sent as an `X-API-Key` header. This approach has limitations:

- No concept of "users" -- just anonymous API keys
- API keys stored in `localStorage` are vulnerable to XSS
- No role-based access control
- No audit trail of who performed what action

This design adds proper user authentication (username/password with JWT sessions) while preserving the existing API key system for programmatic access.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth mechanism (web UI) | JWT in httpOnly cookies | XSS-safe, stateless, fits existing FastAPI patterns |
| Auth mechanism (API) | Keep X-API-Key header | Backwards compatible for external integrations |
| Dual-mode auth | Single dependency, JWT-first fallback to API key | Minimal endpoint changes |
| User roles | Admin + Regular user | Simple, covers the need without RBAC complexity |
| Password hashing | bcrypt via passlib | Battle-tested, no extra C deps in Docker |
| Initial user setup | Plaintext in .env, hashed on first boot | Simple Docker deployment |
| Token storage | httpOnly, Secure, SameSite=Lax cookies | Browser-managed, not accessible to JS |
| JWT secret | Required env var (no auto-generation) | Prevents accidental session loss on restart |
| Rate limiting | Redis counter on login endpoint | No new dependencies, 5 attempts per 15 min per IP |
| Refresh tokens | Server-side in DB (hashed) | Enables session revocation |
| API key scoping | API keys get `created_by` FK to users (nullable) | Audit trail, backwards compatible |

## Database Schema

### New: `users` table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default gen_random_uuid() | UUIDMixin |
| username | VARCHAR(64) | UNIQUE, NOT NULL, indexed | Login identifier |
| email | VARCHAR(256) | UNIQUE, nullable | Optional, future use |
| password_hash | VARCHAR(128) | NOT NULL | bcrypt hash |
| role | ENUM('admin', 'user') | NOT NULL, default 'user' | |
| is_active | BOOLEAN | NOT NULL, default true | |
| created_at | TIMESTAMP | NOT NULL, server default now() | TimestampMixin |
| updated_at | TIMESTAMP | NOT NULL, server default now() | TimestampMixin |
| last_login_at | TIMESTAMP | nullable | Updated on successful login |

### New: `refresh_tokens` table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| user_id | UUID | FK -> users ON DELETE CASCADE, indexed | |
| token_hash | VARCHAR(128) | UNIQUE, indexed | SHA-256 of refresh token |
| expires_at | TIMESTAMP | NOT NULL | 7 days from creation |
| created_at | TIMESTAMP | NOT NULL, server default now() | |
| revoked | BOOLEAN | NOT NULL, default false | |

### Modified: `api_keys` table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| created_by | UUID | FK -> users, nullable | Null for pre-existing keys |

### Alembic migration: `002_add_users_auth.py`

1. Create `userrole` enum type ('admin', 'user')
2. Create `users` table
3. Create `refresh_tokens` table
4. Add `created_by` column to `api_keys` (nullable, FK to users)

Migration is additive only -- no destructive changes. Safe for existing deployments.

## Backend Architecture

### New dependencies

Add to `pyproject.toml`:
- `pyjwt>=2.8.0` -- JWT encoding/decoding
- `passlib[bcrypt]>=1.7.4` -- bcrypt password hashing

### Environment variables

Add to `config.py` Settings class:

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| ADMIN_USERNAME | str | "admin" | No | Initial admin username |
| ADMIN_PASSWORD | SecretStr | "" | For first boot | Empty = skip seeding |
| JWT_SECRET_KEY | SecretStr | -- | Yes, always | App refuses to start without it |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | int | 15 | No | |
| JWT_REFRESH_TOKEN_EXPIRE_DAYS | int | 7 | No | |

`JWT_SECRET_KEY` is **required** in all environments. The app logs an error and exits if not set. This prevents accidental session invalidation on container restarts.

### New files

| File | Purpose |
|------|---------|
| `src/cti/models/user.py` | User model + UserRole enum |
| `src/cti/models/refresh_token.py` | RefreshToken model |
| `src/cti/schemas/user.py` | Pydantic schemas (UserCreate, UserResponse, UserUpdate, LoginRequest, TokenResponse) |
| `src/cti/schemas/auth.py` | Auth-specific schemas (LoginRequest, AuthMeResponse) |
| `src/cti/services/auth_service.py` | Password hashing, JWT creation/verification, refresh token management |
| `src/cti/api/v1/auth.py` | Auth endpoints (login, refresh, logout, me) |
| `alembic/versions/002_add_users_auth.py` | Database migration |

### Modified files

| File | Changes |
|------|---------|
| `src/cti/core/config.py` | Add new env vars to Settings class |
| `src/cti/core/dependencies.py` | Replace `verify_api_key` with dual-mode `get_current_auth` |
| `src/cti/main.py` | Add user seeding to lifespan, JWT_SECRET_KEY validation |
| `src/cti/api/v1/router.py` | Add auth router, add users router |
| `src/cti/api/v1/settings.py` | Add user management endpoints, link API key creation to user |
| `src/cti/api/v1/observables.py` | Swap dependency from `verify_api_key` to `get_current_auth` |
| `src/cti/api/v1/feeds.py` | Swap dependency + add admin check for write operations |
| `src/cti/api/v1/export.py` | Swap dependency |
| `src/cti/api/v1/stats.py` | Swap dependency |
| `src/cti/models/api_key.py` | Add `created_by` relationship |
| `pyproject.toml` | Add pyjwt and passlib dependencies |
| `.env` | Add ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET_KEY |
| `.env.example` | Add new vars with documentation |
| `docker-compose.yml` | Pass new env vars to api service |

### Auth dependency design

The core change is replacing the single `verify_api_key` dependency with a dual-mode `get_current_auth`:

```
AuthSubject = User | ApiKey

async def get_current_auth(request, db) -> AuthSubject:
    # 1. Check for access_token cookie
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
            user = await db.get(User, payload["sub"])
            if user and user.is_active:
                return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            pass  # Fall through to API key check

    # 2. Check for X-API-Key header
    raw_key = request.headers.get("X-API-Key")
    if raw_key:
        # ... existing API key verification logic ...
        return api_key

    # 3. Neither present
    raise HTTPException(401, "Authentication required")

async def require_admin(auth: AuthSubject = Depends(get_current_auth)) -> AuthSubject:
    if isinstance(auth, ApiKey):
        return auth  # API keys get admin-level access (backwards compat)
    if auth.role != UserRole.ADMIN:
        raise HTTPException(403, "Admin access required")
    return auth
```

### API endpoints

#### Auth endpoints (`/api/v1/auth/`)

**POST /auth/login** (unauthenticated)
- Body: `{ "username": "admin", "password": "secret" }`
- Success: Sets httpOnly cookies, returns `{ id, username, role }`
- Failure: 401 with "Invalid credentials"
- Rate limited: 5 failed attempts per 15 min per IP (Redis counter)

**POST /auth/refresh** (refresh cookie required)
- Reads refresh_token cookie
- Validates token hash against DB, checks expiry and revoked status
- Issues new access_token cookie
- Returns 200 on success, 401 on failure

**POST /auth/logout** (access cookie required)
- Revokes refresh token in DB
- Clears both cookies
- Returns 200

**GET /auth/me** (any auth)
- Returns current user info or API key info
- Response: `{ type: "user"|"api_key", id, username/name, role }`

#### User management endpoints (`/api/v1/settings/users/`)

**GET /settings/users** (admin only)
- Returns list of all users (id, username, email, role, is_active, created_at, last_login_at)

**POST /settings/users** (admin only)
- Body: `{ username, password, role?, email? }`
- Creates user with bcrypt-hashed password
- Returns 201 with user info (no password in response)

**PUT /settings/users/{id}** (admin only)
- Body: `{ role?, is_active?, email? }`
- Cannot deactivate yourself
- Returns updated user

**DELETE /settings/users/{id}** (admin only)
- Cannot delete yourself
- Revokes all refresh tokens for the deleted user
- Returns 204

**PUT /settings/users/{id}/password** (admin or self)
- Admin can set any user's password
- Regular users can only change their own (requires current_password field)
- Body: `{ new_password, current_password? }`

### Rate limiting (login endpoint)

Redis-based counter, no new dependencies:

```
Key: "login_fail:{client_ip}"
TTL: 15 minutes
Threshold: 5 attempts

On login attempt:
  count = redis.get(key)
  if count >= 5:
      return 429 Too Many Requests (with Retry-After header)

On failed login:
  redis.incr(key)
  redis.expire(key, 900)  # 15 min TTL

On successful login:
  redis.delete(key)
```

Client IP extracted from `X-Forwarded-For` header (set by nginx) or `request.client.host`.

### Startup sequence (lifespan)

Updated order:
1. Initialize Redis
2. **Validate JWT_SECRET_KEY is set** (exit if not)
3. Seed default feeds
4. **Seed initial admin user** (if ADMIN_PASSWORD set and no users exist)
5. Seed initial API key (existing behavior, kept for backwards compat)
6. Start scheduler

Seed logic:
- If no users exist AND `ADMIN_PASSWORD` is not empty: create admin user, log confirmation
- If no users exist AND `ADMIN_PASSWORD` is empty: log WARNING with instructions
- If users already exist: skip (idempotent)

## Frontend Architecture

### Modified files

| File | Changes |
|------|---------|
| `frontend/src/pages/LoginPage.tsx` | Username + password form (replaces API key input) |
| `frontend/src/contexts/AuthContext.tsx` | Rewrite: cookie-based auth, user state, role |
| `frontend/src/api/client.ts` | Remove localStorage interceptor, add withCredentials, add refresh interceptor |
| `frontend/src/api/auth.ts` | New: login(), refresh(), logout(), getMe() |
| `frontend/src/pages/SettingsPage.tsx` | Add Users tab (admin only) |
| `frontend/src/components/layout/Header.tsx` | Show username instead of API key prefix |
| `frontend/src/components/layout/Sidebar.tsx` | No changes (all pages visible to all roles) |
| `frontend/src/types/auth.ts` | New: User type, LoginRequest, role types |

### New files

| File | Purpose |
|------|---------|
| `frontend/src/components/settings/UserManager.tsx` | User management table + CRUD dialogs |
| `frontend/src/hooks/useUsers.ts` | React Query hooks for user CRUD |
| `frontend/src/api/users.ts` | API calls for user management |
| `frontend/src/types/user.ts` | User-related TypeScript types |

### Login flow

1. User enters username + password on LoginPage
2. POST `/api/v1/auth/login` (Axios sends it, browser receives Set-Cookie headers)
3. Backend sets `access_token` and `refresh_token` as httpOnly cookies
4. Response body contains `{ id, username, role }` -- stored in React state
5. AuthContext navigates to `/`
6. Subsequent API calls automatically include cookies (withCredentials: true)

### Auth state management

```typescript
interface AuthUser {
  id: string
  username: string
  role: 'admin' | 'user'
}

interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isAdmin: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<boolean>
  logout: () => void
}
```

On mount, AuthContext calls `GET /auth/me`:
- Success: set user state from response
- 401: try refresh, if fail -> redirect to login

### Token refresh interceptor

```typescript
let isRefreshing = false
let failedQueue: Array<{ resolve, reject }> = []

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => api(error.config))
      }

      isRefreshing = true
      error.config._retry = true

      try {
        await api.post('/auth/refresh')
        // Replay queued requests
        failedQueue.forEach(({ resolve }) => resolve())
        failedQueue = []
        return api(error.config)
      } catch {
        failedQueue.forEach(({ reject }) => reject())
        failedQueue = []
        // Redirect to login
        window.location.href = '/login'
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)
```

### Role-based UI

Admin sees all current functionality plus user management.

Regular users:
- **Dashboard:** Full view (read-only data)
- **Observables:** View + search. No create/delete buttons
- **Feeds:** View feed list + run history. No create/edit/delete/trigger buttons
- **Settings:** View own profile, change own password. No API key management, no user management

Implementation: check `isAdmin` from AuthContext to conditionally render action buttons.

## Docker & Environment

### `.env` additions

```env
# Authentication
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme-on-first-boot
JWT_SECRET_KEY=generate-a-random-string-here
```

### `docker-compose.yml` changes

Add to `api` service environment:
```yaml
ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
ADMIN_PASSWORD: ${ADMIN_PASSWORD:-}
JWT_SECRET_KEY: ${JWT_SECRET_KEY:?required}
```

`JWT_SECRET_KEY` uses `:?required` syntax to fail docker-compose up if not set.

### Cookie behavior across environments

| Environment | Secure flag | SameSite | Notes |
|-------------|-------------|----------|-------|
| Development (Vite proxy) | false | Lax | Same-origin via Vite proxy, no cookie issues |
| Production (Docker/nginx) | true | Lax | Same-origin via nginx proxy, cookies encrypted in transit |

The `Secure` flag is toggled based on `ENVIRONMENT` setting (production vs development).

## Potential Pitfalls & Mitigations

| # | Pitfall | Risk | Mitigation |
|---|---------|------|------------|
| 1 | Existing deployments lose UI access | Users who don't set ADMIN_PASSWORD can't log in via UI | API keys still work for API access. Startup logs warn explicitly. Clear error on login page. |
| 2 | JWT secret not set | Container restart with missing secret = startup failure | Required in all environments via docker-compose `:?required` syntax. App exits with clear error. |
| 3 | Cookie/CORS in development | Cookies not sent cross-origin | Vite proxy makes it same-origin. No issues expected. |
| 4 | Alembic migration on existing data | Adding FK to populated table | `created_by` is nullable. No constraint on existing rows. |
| 5 | Token refresh race condition | Multiple 401s trigger multiple refreshes | Request queue pattern in Axios interceptor. |
| 6 | bcrypt blocks async event loop | Password hashing is CPU-intensive | Use `asyncio.to_thread()` for all bcrypt calls. |
| 7 | Export endpoints break for external tools | SIEMs/firewalls use API keys for blocklists | API key auth unchanged. Dual-mode dependency is transparent. |
| 8 | CSRF with cookie auth | Cookies sent automatically on cross-site requests | SameSite=Lax + JSON Content-Type requirement. |
| 9 | Brute force on login | No rate limiting allows password guessing | Redis counter: 5 failed attempts per 15 min per IP. |
| 10 | Refresh token stolen | Attacker could maintain long-lived access | Tokens hashed in DB, revocable per-user. Logout revokes. Admin can delete users (revokes all tokens). |

## Files Changed Summary

### Backend (17 files)

**New (7):**
- `src/cti/models/user.py`
- `src/cti/models/refresh_token.py`
- `src/cti/schemas/user.py`
- `src/cti/schemas/auth.py`
- `src/cti/services/auth_service.py`
- `src/cti/api/v1/auth.py`
- `alembic/versions/002_add_users_auth.py`

**Modified (10):**
- `src/cti/core/config.py`
- `src/cti/core/dependencies.py`
- `src/cti/main.py`
- `src/cti/api/v1/router.py`
- `src/cti/api/v1/settings.py`
- `src/cti/api/v1/feeds.py` (admin check for write ops + dependency swap)
- `src/cti/api/v1/observables.py` (dependency swap + admin check for create/delete)
- `src/cti/api/v1/export.py` (dependency swap)
- `src/cti/api/v1/stats.py` (dependency swap)
- `src/cti/models/api_key.py` (add created_by)

### Frontend (10 files)

**New (4):**
- `frontend/src/components/settings/UserManager.tsx`
- `frontend/src/hooks/useUsers.ts`
- `frontend/src/api/users.ts`
- `frontend/src/types/user.ts`

**Modified (6):**
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/auth.ts`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/layout/Header.tsx`
- `frontend/src/types/auth.ts`

### Config/Docker (4 files)

**Modified:**
- `pyproject.toml`
- `.env`
- `.env.example`
- `docker-compose.yml`

**Total: ~31 files** (11 new, 20 modified)
