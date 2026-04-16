# Google OAuth Authentication

## Overview

This document describes the Google OAuth 2.0 authentication system implemented with authlib. The system provides secure OAuth login with token refresh capabilities.

## Architecture

### Why authlib?

We chose **authlib** over other OAuth libraries because:

1. **Production-ready**: Built by the same author as requests, battle-tested
2. **RFC 8414 compliant**: Implements OAuth 2.0 Authorization Server Metadata
3. **Token rotation**: Built-in support for refresh tokens
4. **Multiple clients**: Can manage multiple OAuth providers easily
5. **Active maintenance**: Well-maintained, security updates

Alternative options considered:
- `requests-oauthlib`: Less maintained, simpler API
- `google-auth`: Google-specific, not provider-agnostic
- `FastAPI-Social-Auth`: Too limited, not production-ready

### Directory Structure

```
backend/apps/api/v1/
├── auth/
│   ├── oauth.py                      # authlib client configuration
│   ├── oauth_service.py               # Business logic layer
│   └── deps/
│       └── oauth_dependencies.py      # FastAPI dependencies
├── repositories/
│   └── oauth_repository.py            # Data access layer
└── routers/
    └── oauth.py                       # API endpoints
```

### Why this Architecture?

1. **DRY (Don't Repeat Yourself)**: OAuth logic centralized in service layer
2. **Single Responsibility**: Each module has one job
3. **Dependency Injection**: FastAPI dependencies for testability
4. **Repository Pattern**: Clean separation of data access
5. **Service Layer**: Business logic isolated from HTTP concerns

---

## OAuth Lifecycle

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GOOGLE OAuth FLOW                                    │
└─────────────────────────────────────────────────────────────────────────────┘

1. FRONTEND REQUESTS OAUTH URL
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  GET /api/v1/auth/oauth/google/url                                      │
   │  Query params: redirect_url (optional)                                 │
   │         ↓                                                                │
   │  Backend generates cryptographically secure state token               │
   │         ↓                                                                │
   │  State stored in Redis with 10-minute TTL                              │
   │         ↓                                                                │
   │  Returns: { url: "https://accounts.google.com/...", state: "xxx" }   │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
2. FRONTEND REDIRECTS USER
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User redirected to Google OAuth consent screen                        │
   │         ↓                                                                │
   │  User sees: "Momodu wants to access your account"                     │
   │         ↓                                                                │
   │  Scopes requested:                                                      │
   │    - openid                                                             │
   │    - email                                                              │
   │    - profile                                                            │
   │    - userinfo.email                                                     │
   │    - userinfo.profile                                                   │
   │         ↓                                                                │
   │  User clicks "Continue" → authorization granted                        │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
3. GOOGLE CALLS BACK
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  GET /api/v1/auth/oauth/google/callback                                │
   │  Query params: code=xxx&state=xxx                                      │
   │         ↓                                                                │
   │  Backend validates state token (CSRF protection)                       │
   │         ↓                                                                │
   │  State deleted from Redis (prevents replay attacks)                    │
   │         ↓                                                                │
   │  Exchange authorization code for tokens:                               │
   │    - access_token (1 hour expiry)                                      │
   │    - refresh_token (for silent re-auth)                                │
   │    - id_token (JWT with user claims)                                    │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
4. BACKEND RESOLVES USER
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Get user info from Google:                                            │
   │    GET https://www.googleapis.com/oauth2/v3/userinfo                  │
   │    Header: Bearer ACCESS_TOKEN                                         │
   │         ↓                                                                │
   │  Response:                                                             │
   │    {                                                                    │
   │      "sub": "123456789",  // Google user ID                            │
   │      "email": "user@gmail.com",                                       │
   │      "email_verified": true,                                           │
   │      "name": "John Doe",                                               │
   │      "picture": "https://..."                                          │
   │    }                                                                    │
   │         ↓                                                                │
   │  Resolve user (3 steps):                                               │
   │    1. Check OAuthAccount exists with (provider, provider_user_id)    │
   │       → Return linked user                                             │
   │    2. Check User exists with same email                                │
   │       → Link existing user to OAuth                                    │
   │    3. Create new User + OAuthAccount                                   │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ↓
5. SAVE OAUTH ACCOUNT & GENERATE JWT
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  Save OAuth tokens to database:                                         │
   │    - access_token (for Google API calls)                               │
   │    - refresh_token (for token refresh)                                 │
   │    - id_token (for identity verification)                              │
   │    - token_expires_at                                                  │
   │    - scope                                                             │
   │         ↓                                                                │
   │  Generate JWT tokens:                                                  │
   │    - access_token (60 min) - for API access                            │
   │    - refresh_token (7 days) - for token refresh                       │
   │         ↓                                                                │
   │  Return to frontend:                                                    │
   │    {                                                                    │
   │      "access_token": "eyJ...",                                         │
   │      "refresh_token": "eyJ...",                                         │
   │      "token_type": "bearer",                                           │
   │      "expires_in": 3600,                                               │
   │      "user_id": "uuid",                                                │
   │      "email": "user@gmail.com"                                         │
   │    }                                                                    │
   └─────────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### 1. Get OAuth Authorization URL

Generate Google OAuth URL for frontend to redirect user.

| Property | Value |
|----------|-------|
| **URL** | `/api/v1/auth/oauth/google/url` |
| **Method** | GET |
| **Auth Required** | No |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `redirect_url` | string | No | URL to redirect after OAuth completion |

**Response (200):**

```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&response_type=code&scope=openid+email+profile&state=xxx&access_type=offline&prompt=consent",
  "state": "random_state_token_32_chars"
}
```

**State Token Security:**
- Generated using `secrets.token_urlsafe(32)` - cryptographically secure
- Stored in Redis with 10-minute TTL
- Validated on callback and deleted to prevent replay attacks

---

### 2. Handle OAuth Callback

Process Google's redirect after user authorizes.

| Property | Value |
|----------|-------|
| **URL** | `/api/v1/auth/oauth/google/callback` |
| **Method** | GET |
| **Auth Required** | No |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | Yes | Authorization code from Google |
| `state` | string | Yes | State token for CSRF validation |

**Response (200):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "6985b7e2-3ef3-433c-ac78-f5f088dd8b3a",
  "email": "user@gmail.com"
}
```

**Error Responses:**

```json
{
  "detail": "Invalid or expired OAuth state token. Please try again."
}
// Status: 400

{
  "detail": "Failed to exchange authorization code: ..."
}
// Status: 400

{
  "detail": "OAuth authentication failed. Please try again."
}
// Status: 500
```

---

### 3. Get User's OAuth Accounts

List all OAuth accounts linked to the current user.

| Property | Value |
|----------|-------|
| **URL** | `/api/v1/auth/oauth/accounts` |
| **Method** | GET |
| **Auth Required** | Yes (JWT) |

**Response (200):**

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "provider": "google",
    "provider_user_id": "123456789",
    "scope": "openid email profile",
    "is_active": true,
    "created_at": "2026-04-15T10:00:00"
  }
]
```

---

### 4. Unlink OAuth Account

Disconnect an OAuth provider from user's account.

| Property | Value |
|----------|-------|
| **URL** | `/api/v1/auth/oauth/accounts/{account_id}` |
| **Method** | DELETE |
| **Auth Required** | Yes (JWT) |

**Response (200):**

```json
{
  "message": "OAuth account unlinked successfully"
}
```

---

### 5. Refresh OAuth Token

Refresh access token without re-authentication.

| Property | Value |
|----------|-------|
| **URL** | `/api/v1/auth/oauth/refresh` |
| **Method** | POST |
| **Auth Required** | No |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `refresh_token` | string | Yes | OAuth refresh token |
| `provider` | string | No | Provider name (default: google) |

**Response (200):**

```json
{
  "access_token": "new_access_token",
  "refresh_token": "new_or_same_refresh_token",
  "expires_at": 1234567890
}
```

---

## Database Schema

### OAuthAccount Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to accounts_user |
| `provider` | VARCHAR(50) | OAuth provider (google, github) |
| `provider_user_id` | VARCHAR(255) | Provider's user ID |
| `access_token` | TEXT | OAuth access token |
| `refresh_token` | TEXT | OAuth refresh token |
| `id_token` | TEXT | OAuth ID token |
| `token_expires_at` | TIMESTAMP | Token expiration |
| `scope` | VARCHAR(500) | OAuth scopes |
| `extra_data` | TEXT | Extra provider data (JSON) |
| `is_active` | BOOLEAN | Account active status |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Update timestamp |

**Indexes:**
- `unique: (provider, provider_user_id)` - Prevent duplicate links
- `index: (user_id, provider)` - User's OAuth accounts lookup
- `index: (user_id, provider, is_active)` - Active accounts lookup

---

## Security Considerations

### 1. CSRF Protection

- State token generated with `secrets.token_urlsafe(32)`
- State stored in Redis with 10-minute TTL
- State deleted after validation (prevents replay)
- Frontend must validate state matches

### 2. Token Storage

- Access tokens stored in database (not encrypted in this implementation)
- For production: encrypt tokens using `shared.utils.encrypt_token`
- Refresh tokens enable long-lived sessions

### 3. Token Rotation

- Request `access_type=offline` to get refresh token
- `prompt=consent` forces consent to ensure refresh token
- Refresh token used for silent re-authentication

### 4. Scope Choices

**Chosen scopes:**
```python
GOOGLE_SCOPES = [
    "openid",           # Standard OAuth 2.0
    "email",           # Access email
    "profile",         # Access profile
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
```

**Why these scopes:**
- `openid`: Required for OpenID Connect compliance
- `email`: Get user's email (primary identifier)
- `profile`: Get name, picture for user profile
- `userinfo.email` / `userinfo.profile`: More detailed user info

---

## Configuration

### Environment Variables

Add to `backend/.env`:

```env
# Google OAuth (get from https://console.cloud.google.com/apis/credentials)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8001/api/v1/auth/oauth/google/callback
```

### Google Cloud Console Setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID
3. Set **Authorized redirect URIs** to:
   ```
   http://localhost:8001/api/v1/auth/oauth/google/callback
   ```
4. Copy Client ID and Client Secret to `.env`

---

## Frontend Integration Example

### JavaScript/TypeScript

```typescript
// Step 1: Get OAuth URL
async function getGoogleOAuthUrl(redirectUrl?: string) {
  const params = redirectUrl ? `?redirect_url=${encodeURIComponent(redirectUrl)}` : '';
  const response = await fetch(`/api/v1/auth/oauth/google/url${params}`);
  return response.json();
}

// Step 2: Redirect user
const { url, state } = await getGoogleOAuthUrl('http://localhost:3000/dashboard');
// Save state to sessionStorage for validation
sessionStorage.setItem('oauth_state', state);
window.location.href = url;

// Step 3: Handle callback
// After redirect, parse URL params
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const returnedState = urlParams.get('state');

// Validate state
const savedState = sessionStorage.getItem('oauth_state');
if (returnedState !== savedState) {
  throw new Error('State mismatch - possible CSRF');
}

// Exchange code for tokens
const response = await fetch(
  `/api/v1/auth/oauth/google/callback?code=${code}&state=${returnedState}`
);
const tokens = await response.json();

// Store tokens
localStorage.setItem('access_token', tokens.access_token);
localStorage.setItem('refresh_token', tokens.refresh_token);
```

---

## Testing the OAuth Flow

### Step 1: Get OAuth URL

```bash
curl -X GET "http://localhost:8001/api/v1/auth/oauth/google/url"
```

Response:
```json
{
  "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "abc123..."
}
```

### Step 2: Copy URL and Authenticate

1. Copy the `url` value
2. Open in browser
3. Complete Google authentication

### Step 3: Check Callback

After authentication, you'll be redirected to:
```
http://localhost:8001/api/v1/auth/oauth/google/callback?code=xxx&state=xxx
```

### Step 4: Verify Tokens

```bash
# Use returned access_token
curl -X GET "http://localhost:8001/api/v1/posts" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Invalid client ID | Check GOOGLE_CLIENT_ID in .env |
| Redirect URI mismatch | Verify GOOGLE_REDIRECT_URI matches Google Console |
| State token expired | State expires in 10 minutes - must complete auth quickly |
| No refresh token | Ensure `access_type=offline` and `prompt=consent` in auth URL |
| Email not returned | User may have hidden email - handle optional email |