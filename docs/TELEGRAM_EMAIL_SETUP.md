# Telegram & Email Setup Guide

> Complete this once before go-live. You will need the Render backend URL, access to the server `.env`, and a phone with Telegram.

---

## Part 1 — Telegram Bot

### Step 1: Create the bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot`.
3. Choose a name (e.g. `Gysbin Pharmacy AI`).
4. Choose a username ending in `bot` (e.g. `gysbin_pharmacy_bot`).
5. BotFather replies with a **bot token** — looks like `7123456789:AAFxyz...`
6. Copy it. This is your `TELEGRAM_BOT_TOKEN`.

### Step 2: Get the CEO's chat ID

The CEO must message the bot first before alerts can be sent.

1. CEO opens Telegram and searches for the bot by its username.
2. CEO sends any message (e.g. `/start`).
3. Fetch the update from Telegram to find the chat ID:

```bash
curl https://api.telegram.org/bot<TOKEN>/getUpdates
```

4. In the JSON response, find `message.chat.id` — it is a number like `987654321`.
5. That number is the CEO's **Telegram chat ID**.

### Step 3: Add the chat ID to delivery settings

Log in to the cloud dashboard as an admin and go to AI Settings → Delivery Settings. Add the chat ID to the organization's Telegram chat IDs list.

Or set it directly via the API:

```http
POST /api/ai-manager/delivery-settings
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "report_scope_key": "organization",
  "telegram_enabled": true,
  "telegram_chat_ids": ["987654321"]
}
```

### Step 4: Set environment variables

Add these to the Render backend environment (or `backend/.env` for local):

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxyz...
TELEGRAM_WEBHOOK_SECRET=some-long-random-string-you-generate
TELEGRAM_ALERTS_ENABLED=True
TELEGRAM_ALERT_COOLDOWN_HOURS=4
TELEGRAM_ALERT_INTERVAL_MINUTES=45
AI_DAILY_BRIEFING_ENABLED=True
AI_DAILY_BRIEFING_HOUR=8
AI_DAILY_BRIEFING_PERIOD_DAYS=7
```

Generate a strong webhook secret with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 5: Register the webhook with Telegram

Run this once after deploying. Replace the placeholders:

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-render-app.onrender.com/api/telegram/webhook",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
  }'
```

Telegram should respond with `{"ok":true,"result":true}`.

**Verify the webhook is registered:**
```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

### Step 6: Test it

CEO sends any message to the bot on Telegram — e.g. *"What were today's sales?"* — and should receive an AI answer within a few seconds.

---

## Part 2 — Email (Daily Briefing)

> The daily email briefing uses the existing weekly report SMTP configuration.
> If you already have SMTP set up for weekly reports, it will work for daily briefings too.

### Option A: Gmail (simplest)

1. Go to your Google account → Security → **2-Step Verification** (must be on).
2. Search for **App Passwords** → create a new one → choose **Mail** and **Other**.
3. Google gives you a 16-character password. Copy it.

Add to `backend/.env` / Render environment:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_FROM_EMAIL=your@gmail.com
SMTP_FROM_NAME=Gysbin Pharmacy AI
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

### Option B: SendGrid (recommended for production)

1. Create a free account at sendgrid.com.
2. Settings → API Keys → Create API Key (Full Access).
3. Copy the key.
4. Verify your sender domain or a single sender email address.

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.xxxx...
SMTP_FROM_EMAIL=alerts@yourdomain.com
SMTP_FROM_NAME=Gysbin Pharmacy AI
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

### Step: Add email recipients to delivery settings

```http
POST /api/ai-manager/delivery-settings
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "report_scope_key": "organization",
  "email_enabled": true,
  "email_recipients": ["john@yourdomain.com"]
}
```

### Enable the weekly report (if not already done)

```env
AI_WEEKLY_REPORTS_ENABLED=True
AI_WEEKLY_REPORT_DELIVERY_ENABLED=True
AI_WEEKLY_REPORT_EMAIL_ENABLED=True
AI_WEEKLY_REPORT_DAY=sun
AI_WEEKLY_REPORT_HOUR=19
AI_WEEKLY_REPORT_MINUTE=0
```

---

## Summary of all new environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | — | Bot token from BotFather. Required for all Telegram features. |
| `TELEGRAM_WEBHOOK_SECRET` | — | Random string to verify Telegram calls our webhook. Optional but recommended. |
| `TELEGRAM_ALERTS_ENABLED` | `False` | Enable the 45-minute anomaly detection and push alert job. |
| `TELEGRAM_ALERT_COOLDOWN_HOURS` | `4` | Minimum hours between repeated alerts for the same issue. |
| `TELEGRAM_ALERT_INTERVAL_MINUTES` | `45` | How often the alert scanner runs. |
| `AI_DAILY_BRIEFING_ENABLED` | `False` | Enable the daily morning Telegram briefing. |
| `AI_DAILY_BRIEFING_HOUR` | `8` | Hour (0–23, server timezone) to send the daily briefing. |
| `AI_DAILY_BRIEFING_PERIOD_DAYS` | `7` | How many days of data the daily briefing covers. |
| `ENABLE_BACKGROUND_SCHEDULER` | `True` | Must be `True` for alerts and briefings to run. |

---

## Troubleshooting

**Bot does not reply to CEO messages**
- Check that the webhook is registered: `GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Confirm `pending_update_count` is not stuck and `last_error_message` is empty.
- Confirm the Render URL is HTTPS and reachable.
- Confirm the CEO's chat ID is in the delivery settings.

**No alerts being pushed**
- Confirm `TELEGRAM_ALERTS_ENABLED=True` and `ENABLE_BACKGROUND_SCHEDULER=True` in env.
- Check Render logs for `Running Telegram anomaly alert task`.
- Confirm the organization has an active delivery setting with `telegram_enabled=true` and at least one chat ID.
- Alerts only fire for `critical` and `high` severity findings. If all findings are medium, no alert is sent.

**Email not delivering**
- Check Render logs for SMTP errors.
- For Gmail, confirm App Passwords is used (not your account password).
- For SendGrid, confirm the sender email is verified and the API key has Send Mail permission.
- Test SMTP credentials with a separate SMTP test tool before blaming the app.

**Wrong timezone for daily briefing**
- Set `TIMEZONE=Africa/Accra` (or the correct timezone) in the environment.
- The scheduler uses this timezone for the 08:00 cron trigger.
