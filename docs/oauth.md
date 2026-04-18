# Google OAuth Authentication

## Overview

This document describes the Google OAuth login flow currently implemented in the backend.

The current design is backend-led:

- the frontend asks the backend for a Google authorization URL
- the backend generates the URL from server-side configuration
- Google redirects back to the backend callback
- the backend exchanges the code, resolves the user, stores the OAuth link, and returns API JWTs

This keeps Google client credentials, redirect URI configuration, token exchange, and account-linking logic on the server.
---

## Current Behavior
The working Google OAuth flow now does the following:

- uses the redirect URI configured in `backend/.env`
- URL-encodes scopes correctly before redirecting to Google
- requests `openid`, `email`, `profile`, `userinfo.email`, and `userinfo.profile`
- accepts the Google callback on the backend
- resolves identity from Google `userinfo` first
- fills missing claims from the `id_token`
- uses Google `tokeninfo` as a last fallback when email claims are incomplete
- links to an existing local user by email when possible
- creates a new local user when needed
- stores the Google OAuth account link in the database
- returns Momodu JWT access and refresh tokens to the caller

## Why This Design

### Why the backend generates the Google URL

- It prevents drift between frontend and backend redirect URIs.
- It prevents the frontend from constructing a broken scope string.
- It centralizes OAuth parameters like `prompt=consent` and `access_type=offline`.
- It keeps the server in control of CSRF protection with the `state` token.

### Why Google redirects to the backend instead of the frontend

- The authorization code is exchanged server-side.
- Google client secret never touches the browser.
- User creation and account linking happen in one place.
- The frontend does not need to understand Google token exchange details.

### Why the backend resolves claims from multiple sources

Google can return slightly different claim sets depending on the granted scopes and endpoint behavior. To avoid brittle login failures, the backend resolves identity in this order:

1. `userinfo`
2. `id_token` claims
3. `tokeninfo`

That gives the system a reliable fallback chain without changing the frontend contract.

---

## Lifecycle

### End-to-end flow

1. Frontend requests `GET /api/v1/auth/oauth/google/url`.
2. Backend generates a secure `state` value and stores it in Redis.
3. Backend returns a Google authorization URL.
4. Frontend redirects the browser to Google immediately.
5. User chooses an account and grants consent.
6. Google redirects the browser to `GET /api/v1/auth/oauth/google/callback`.
7. Backend validates the `state`.
8. Backend exchanges the authorization `code` for Google tokens.
9. Backend fetches user identity from Google.
10. Backend finds or creates the local Momodu user.
11. Backend creates or updates the OAuth account link.
12. Backend issues Momodu JWT access and refresh tokens.
13. Backend returns those tokens as JSON.
14. Frontend stores the Momodu tokens and moves the user into the app.

### Fast-feeling frontend pattern

For the frontend to feel fast and smooth:

- call `/auth/oauth/google/url` only when the user explicitly clicks continue with Google
- redirect the browser immediately after receiving the URL
- do not construct a Google URL in the browser
- do not run a separate frontend-only Google auth SDK flow unless the backend is redesigned for it
- keep the callback page very light and immediately hand control to app auth state

The backend callback currently returns JSON. The smooth frontend approach is:

- open the backend callback in the main window
- let the backend return tokens
- have the frontend callback page read them and finish login

If later you want a cleaner browser UX, a common next step is to make the backend callback redirect to a frontend route with a short-lived handoff token instead of raw JSON. That is not the current implementation.

---

## API Endpoints

### `GET /api/v1/auth/oauth/google/url`

Returns a backend-generated Google authorization URL and the CSRF `state` value.

Response shape:

```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "secure-random-state"
}
```

Notes:

- `redirect_url` is optional and can be supplied by the frontend
- the backend stores the generated state in Redis

### `GET /api/v1/auth/oauth/google/callback`

Handles the Google redirect back to the backend.

Expected query params:

- `code`
- `state`

Google may also send:

- `iss`
- `scope`
- `authuser`
- `prompt`

Success response shape:

```json
{
  "access_token": "momodu-jwt-access-token",
  "refresh_token": "momodu-jwt-refresh-token",
  "token_type": "bearer",
  "expires_in": 1800,
  "user_id": "uuid",
  "email": "user@example.com"
}
```

### `GET /api/v1/auth/oauth/accounts`

Returns the current user’s linked OAuth accounts.

### `DELETE /api/v1/auth/oauth/accounts/{account_id}`

Marks a linked OAuth account inactive.

### `POST /api/v1/auth/oauth/refresh`

Refreshes Google access tokens using a stored refresh token.

---

## Frontend Flow

## Recommended frontend contract

The frontend should treat the backend as the source of truth for the entire OAuth handshake.

### Step 1: Ask backend for the URL

```ts
async function beginGoogleLogin() {
  const res = await fetch("/api/v1/auth/oauth/google/url", {
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error("Failed to start Google login");
  }

  const data = await res.json();
  sessionStorage.setItem("oauth_state", data.state);
  window.location.href = data.url;
}
```

### Step 2: Let Google return to the backend callback

Google redirects to:

```text
/api/v1/auth/oauth/google/callback?code=...&state=...
```

The frontend should not try to exchange the code itself.

### Step 3: Complete login in the browser

Because the current backend callback returns JSON, the simplest frontend callback page is a thin page that:

- lands on the backend callback response
- reads the JSON payload
- stores the Momodu tokens
- redirects into the main app

If you later move to a dedicated frontend callback route, keep the backend responsible for Google code exchange and return a frontend-safe handoff instead of rebuilding the flow in the browser.

## Anti-patterns to avoid

- Do not build the Google authorization URL manually in the frontend.
- Do not use a separate Google popup or One Tap flow unless the backend explicitly supports that token shape.
- Do not reuse callback URLs. Google authorization codes are one-time use.
- Do not assume Google always returns the same claim set from one endpoint.

---

## File Map

This is the current circle of files involved in the flow and what each one does.

### `backend/apps/api/config.py`

Purpose:

- loads FastAPI OAuth settings from environment
- exposes `GOOGLE_CLIENT_ID`
- exposes `GOOGLE_CLIENT_SECRET`
- exposes `GOOGLE_REDIRECT_URI`
- exposes Google scopes and URLs

Why it matters:

- this is the single source of truth for runtime OAuth configuration in FastAPI

### `backend/apps/api/v1/auth/oauth.py`

Purpose:

- builds the Google authorization URL
- exchanges authorization codes for tokens
- refreshes Google tokens
- fetches `userinfo`
- fetches `tokeninfo`
- normalizes Google identity payloads into one shape

Why it matters:

- this is the low-level Google client wrapper
- scope encoding correctness here directly determines whether email claims are granted

### `backend/apps/api/v1/auth/services/oauth_service.py`

Purpose:

- contains the business logic for the OAuth callback
- validates state when applicable
- orchestrates token exchange
- merges Google claims from multiple sources
- resolves whether the local user already exists
- creates new local users when needed
- issues Momodu JWT access and refresh tokens

Why it matters:

- this is the core lifecycle coordinator for Google login

### `backend/apps/api/v1/routers/oauth.py`

Purpose:

- exposes the HTTP routes for the OAuth flow
- returns the generated Google URL
- receives the Google callback
- converts service-layer failures into API responses

Why it matters:

- this is the public API boundary for frontend integration

### `backend/apps/api/v1/auth/deps/oauth_dependencies.py`

Purpose:

- stores and validates OAuth state tokens
- uses Redis to provide CSRF protection and one-time state usage

Why it matters:

- this is what prevents replay and cross-site request forgery in the login flow

### `backend/apps/api/v1/repositories/oauth_repository.py`

Purpose:

- reads and writes OAuth account link records
- finds existing OAuth links by provider and Google subject
- updates stored OAuth tokens

Why it matters:

- this is the persistence layer for Google account linkage

### `backend/apps/api/v1/repositories/user.py`

Purpose:

- finds local users by email or id
- creates local users for first-time OAuth signups

Why it matters:

- this is how Google identity becomes a Momodu user account

### `backend/shared/models/oauth.py`

Purpose:

- defines the SQLAlchemy model used by FastAPI for OAuth account records

Why it matters:

- this model must match the real Django-created database table name and columns
- it currently maps to Django’s `accounts_oauthaccount` table

### `backend/shared/models/users.py`

Purpose:

- defines the SQLAlchemy model used by FastAPI for the local user table

Why it matters:

- FastAPI user creation and lookup rely on this mapping matching Django’s schema

### `backend/apps/accounts/models.py`

Purpose:

- defines the Django-side user and OAuth account models

Why it matters:

- Django migrations are created from this side of the codebase
- FastAPI SQLAlchemy models must remain aligned with these tables

### `backend/apps/accounts/migrations/0002_oauth_accounts.py`

Purpose:

- creates the Django OAuth account table in the database

Why it matters:

- if this migration exists but the FastAPI SQLAlchemy model points to the wrong table name, OAuth login will fail even though migrations are applied

### `backend/run_api.py`

Purpose:

- starts the FastAPI app with Uvicorn
- loads `.env`

Why it matters:

- the server must start from the `backend` directory so the intended `.env` file is loaded

---

## Database Notes

### OAuth account storage

The active FastAPI OAuth repository uses the SQLAlchemy model in `backend/shared/models/oauth.py`.

That model must stay aligned with the Django migration-created schema:

- table name
- column names
- UUID types
- index expectations

### Important compatibility rule

If Django owns the schema and FastAPI uses SQLAlchemy models against the same database, both sides must describe the same tables. If one side renames a table without the other, the OAuth flow will fail after Google login succeeds.

---

## Logging Guidance

The current logging is intentionally moderate:

- it logs whether Google returned an email
- it logs whether refresh and ID tokens are present
- it logs stable identifiers like Google `sub` and local `user_id`
- it avoids logging access tokens, refresh tokens, ID tokens, and raw claim payloads
- it avoids logging user email during normal success paths

This keeps the flow debuggable during review without unnecessarily leaking secrets or personal data.

---

## Configuration

Add to `backend/.env`:

```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-public-api-domain/api/v1/auth/oauth/google/callback
GOOGLE_TOKEN_URL=https://oauth2.googleapis.com/token
GOOGLE_USERINFO_URL=https://www.googleapis.com/oauth2/v3/userinfo
GOOGLE_AUTH_URL=https://accounts.google.com/o/oauth2/v2/auth
GOOGLE_ISSUER=https://accounts.google.com
```

For this project, if you are exposing the local server through Cloudflare Tunnel, `GOOGLE_REDIRECT_URI` must use the public tunnel URL, not localhost.

---

## Google Cloud Console Setup

In Google Cloud Console:

1. Create or open the OAuth client.
2. Set the authorized redirect URI to your backend callback URL.
3. Make sure the redirect URI exactly matches `GOOGLE_REDIRECT_URI`.

Example:

```text
https://momoduxp.michealchinemeluugwu.xyz/api/v1/auth/oauth/google/callback
```

Exact matching matters. Scheme, domain, path, and trailing slash behavior must line up.

---

## Troubleshooting

### `Google account must have an email address`

Likely causes:

- scope string was malformed or not URL-encoded
- Google granted only `openid`
- callback was initiated from a different flow than `/google/url`

### `invalid_grant`

Likely causes:

- callback URL was reused
- authorization code expired
- authorization code was already consumed by the backend once

### `OAuth state not found in Redis`

Likely causes:

- callback was retried after a previous attempt
- state expired
- browser used an old callback URL

### `relation "... does not exist"`

Likely causes:

- FastAPI SQLAlchemy model points to the wrong table name
- Django and FastAPI are using mismatched schema assumptions

---

## Summary

The Google OAuth implementation is now stable around one rule:

- the backend owns the Google handshake

That is the main reason the flow now works reliably. The frontend contract should stay thin and should not reconstruct any part of the Google exchange logic that already exists on the server.
