# Telegram Notification
## Overview

This document describes the Telegram notification system used for post approval workflow

## Telegram Notification Lifecycle

### 1. Connection Setup

| Route | Method | Description |
|-------|--------|-------------|
| `/api/v1/notifications/telegram/connect-link` | GET | Generate a Telegram bot connect link with reference ID |
| `/api/v1/webhooks/telegram/webhook` | POST | Telegram sends updates (messages, callbacks) to this endpoint |

### 2. Post Approval Flow

| Route | Method | Description |
|-------|--------|-------------|
| `/api/v1/posts/{post_id}/submit` | POST | Submit a post for approval (triggers Celery task) |
| `/api/v1/notifications/telegram/send` | POST | Send Telegram notification (manual) |
| `/api/v1/posts/{post_id}/approve` | POST | Direct approve endpoint |

### 3. Health Checks

| Route | Method | Description |
|-------|--------|-------------|
| `/api/v1/notifications/telegram/health` | GET | Telegram notification service health |
| `/api/v1/notifications/telegram/webhook-info` | GET | Check Telegram webhook status |
| `/api/v1/webhooks/telegram/health` | GET | Webhook service health |

---

## Simple Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TELEGRAM APPROVAL FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

1. USER CONNECTS TELEGRAM
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  GET /api/v1/notifications/telegram/connect-link                       │
   │         ↓                                                                │
   │  User gets: https://t.me/momoduxp_bot?start=REFERENCE_ID               │
   │         ↓                                                                │
   │  User clicks link → sends /start to Telegram bot                       │
   │         ↓                                                                │
   │  POST /api/v1/webhooks/telegram/webhook (with /start REFERENCE_ID)     │
   │         ↓                                                                │
   │  System creates NotificationConnection (saves chat_id, user_id)        │
   └─────────────────────────────────────────────────────────────────────────┘

2. POST SUBMITTED FOR APPROVAL
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  POST /api/v1/posts/{post_id}/submit                                    │
   │         ↓                                                                │
   │  trigger_send_for_approval() → Celery task queued                      │
   │         ↓                                                                │
   │  Celery worker executes send_for_approval task                         │
   │         ↓                                                                │
   │  _send_for_approval_sync():                                            │
   │    - Gets user's active Telegram connection                            │
   │    - Creates NotificationDelivery record                               │
   │    - Sends message via Telegram Bot API                                 │
   │    - Message includes inline keyboard (Confirm/Stop buttons)          │
   └─────────────────────────────────────────────────────────────────────────┘

3. USER APPROVES POST
   ┌─────────────────────────────────────────────────────────────────────────┐
   │  User clicks "Confirm" button on Telegram message                      │
   │         ↓                                                                │
   │  Telegram sends callback_query to webhook                              │
   │         ↓                                                                │
   │  POST /api/v1/webhooks/telegram/webhook                                │
   │  Payload: { callback_query: { data: "automation:confirm:POST_ID" } }   │
   │         ↓                                                                │
   │  _parse_telegram_action() extracts action="confirm", reference=POST_ID│
   │         ↓                                                                │
   │  consume_telegram_action() called with sync DB session                 │
   │         ↓                                                                │
   │  approve_post_record() updates post status to "approved"              │
   │         ↓                                                                │
   │  trigger_publish_post() queues publish task                            │
   └─────────────────────────────────────────────────────────────────────────┘
```

---

## Bugs Discovered and Fixed

### Bug 1: Malformed Webhook URL

**File:** `.env`

**Problem:**
```
PUBLIC_API_BASE_URL=https://momoduxp.michealchinemeluugwu.xyz/api/v1/notifications/telegram/set-webhook
```
The URL included the full path, causing Telegram webhook to be set to:
```
https://momoduxp.michealchinemeluugwu.xyz/api/v1/notifications/telegram/set-webhook/api/v1/webhooks/telegram/webhook
```
This resulted in 404 errors when Telegram tried to send updates.

**Fix:**
```bash
# Changed to:
PUBLIC_API_BASE_URL=https://momoduxp.michealchinemeluugwu.xyz

# After change, delete and reset webhook:
DELETE /api/v1/notifications/telegram/webhook
POST /api/v1/notifications/telegram/set-webhook

# Result: Correct webhook URL
# https://momoduxp.michealchinemeluugwu.xyz/api/v1/webhooks/telegram/webhook
```

**Files Modified:**
- `backend/.env` (line 31)
- `backend/.env.production` (added PUBLIC_API_BASE_URL)

---

### Bug 2: Async/Await Type Error

**File:** `apps/api/v1/webhooks/notifications.py` (line ~403)

**Problem:**
```python
# WRONG - consume_telegram_action is a synchronous function
action_detail = await consume_telegram_action(
    db,
    user_id=user.id,
    action=action,
    reference_id=action_reference,
)
```
Error: `TypeError: object str can't be used in 'await' expression`

**Fix:**
```python
# CORRECT - use sync session for sync function
from shared.database import get_sync_session

with get_sync_session() as sync_db:
    action_detail = consume_telegram_action(
        sync_db,
        user_id=user.id,
        action=action,
        reference_id=action_reference,
    )
```

**Why this works:**
- `consume_telegram_action()` in `post_task.py` is a synchronous function using SQLAlchemy sync session
- The webhook handler uses async SQLAlchemy session
- Using async session with sync function caused: `'coroutine' object has no attribute 'scalar_one_or_none'`
- Solution: Use `get_sync_session()` context manager which creates a separate sync session

**File Modified:**
- `backend/apps/api/v1/webhooks/notifications.py` (lines 437-451)

---

### Bug 3: Missing Database Commit

**File:** `apps/api/v1/webhooks/notifications.py`

**Problem:**
Initially tried to add `await db.commit()` after the sync function, but this caused issues because:
1. The sync function already commits internally via context manager
2. Mixing async session operations with sync session caused conflicts

**Fix:**
The sync session context manager handles commit/rollback automatically:
```python
with get_sync_session() as sync_db:
    action_detail = consume_telegram_action(...)
    # commit/rollback handled automatically by context manager
```

---

## Key Code Locations

### Telegram Bot Configuration
- **File:** `apps/api/config.py`
- **Settings:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `PUBLIC_API_BASE_URL`

### Webhook Handler
- **File:** `apps/api/v1/webhooks/notifications.py`
- **Function:** `receive_notification_webhook()` (line ~325)
- **Action Parser:** `_parse_telegram_action()` (line ~36)

### Celery Tasks
- **File:** `apps/api/v1/tasks/post_task.py`
- **Functions:**
  - `send_for_approval` (line ~508) - Celery task wrapper
  - `_send_for_approval_sync()` (line ~217) - Actual implementation
  - `consume_telegram_action()` (line ~144) - Handle confirm/stop
  - `_build_automation_keyboard()` (line ~203) - Create inline buttons

### Database Sessions
- **File:** `shared/database.py`
- **Functions:**
  - `get_sync_session()` (line ~166) - Sync session for Celery/sync tasks
  - `get_db()` - Async session for FastAPI endpoints

---

## Testing the Flow

### Step 1: Connect Telegram
```bash
curl -X GET "https://momoduxp.michealchinemeluugwu.xyz/api/v1/notifications/telegram/connect-link" \
  -H "Authorization: Bearer YOUR_TOKEN"
```
Click the returned link and send `/start` to the bot.

### Step 2: Submit Post for Approval
```bash
curl -X POST "https://momoduxp.michealchinemeluugwu.xyz/api/v1/posts/POST_ID/submit" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Step 3: Verify Telegram Message
Check your Telegram bot - you should receive a message with "Confirm" and "Stop" buttons.

### Step 4: Click Confirm
Click "Confirm" on the Telegram message. The post status should change to `approved`.

---

## Requirements for Production

1. **Celery Worker Running:**
   ```bash
   celery -A shared.celery worker --loglevel=info -Q fast,default
   ```

2. **Correct Environment Variables:**
   - `PUBLIC_API_BASE_URL` = base domain (no paths)
   - `TELEGRAM_BOT_TOKEN` = bot token from @BotFather
   - `TELEGRAM_BOT_USERNAME` = bot username

3. **Webhook Configured:**
   - Delete old webhook if URL is wrong
   - Set new webhook after fixing PUBLIC_API_BASE_URL

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Webhook returns 404 | Check PUBLIC_API_BASE_URL in .env |
| Telegram not connecting | Verify webhook is set: GET /webhook-info |
| Approval not working | Ensure Celery worker is running |
| "coroutine" error | Use sync session for sync functions |
| Buttons not working | Check callback_data format: `automation:confirm:POST_ID` |