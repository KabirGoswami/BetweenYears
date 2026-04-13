# BetweenYears — Backend API

FastAPI + Supabase (PostgreSQL) + Gemini AI backend for the **BetweenYears** reflection journaling app.

---

## Stack

| Layer | Tech |
|---|---|
| API Framework | FastAPI 0.115 |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth (JWT) |
| AI | Google Gemini 2.0 Flash |
| Email | Resend |
| Scheduling | APScheduler |
| Rate Limiting | Slowapi |

---

## Setup

### 1. Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier works)
- A [Gemini API key](https://aistudio.google.com/app/apikey) (free)
- A [Resend](https://resend.com) account for emails (free tier: 3000 emails/month)

### 2. Database Schema

In the **Supabase SQL Editor**, run the entire contents of:
```
sql/schema.sql
```
This creates all tables, RLS policies, triggers, and seed data.

### 3. Environment Variables

```bash
cd backend
cp .env.example .env
# Fill in your keys in .env
```

Required values:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
GEMINI_API_KEY=...
RESEND_API_KEY=re_...
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
FRONTEND_URL=http://localhost:5500
```

### 4. Install & Run

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: **http://localhost:8000/docs**

---

## API Overview

### Auth `/auth`
| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | Register new account |
| POST | `/auth/login` | Login, returns JWT |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Invalidate session |
| POST | `/auth/reset-password` | Send password reset email |
| GET | `/auth/me` | Get current user profile |
| PATCH | `/auth/me` | Update display name / bio |

### Journal `/journal`
| Method | Path | Description |
|---|---|---|
| POST | `/journal/` | Save new entry (triggers streak + AI) |
| GET | `/journal/` | List own entries (paginated) |
| GET | `/journal/{id}` | Get single entry |
| PATCH | `/journal/{id}` | Update entry |
| DELETE | `/journal/{id}` | Soft-delete entry |
| GET | `/journal/prompts/daily` | Today's curated prompt |
| GET | `/journal/prompts/random` | Random prompt |

### AI `/ai`
| Method | Path | Description |
|---|---|---|
| POST | `/ai/analyze` | Analyze entry — themes, tone, insight |
| POST | `/ai/generate-prompt` | Personalized prompt from history |
| POST | `/ai/decision` | Analyze pros/cons decision |
| GET | `/ai/patterns` | Detect patterns across entries |

### Streaks `/streaks`
| Method | Path | Description |
|---|---|---|
| GET | `/streaks/me` | Current streak, XP, level |
| GET | `/streaks/badges` | All badges (earned/locked) |
| POST | `/streaks/values-complete` | Award values badge |

### Community `/community`
| Method | Path | Description |
|---|---|---|
| GET | `/community/stories` | List stories (paginated) |
| POST | `/community/stories` | Share a story (anonymous) |
| GET | `/community/stories/{id}` | Single story |
| POST | `/community/stories/{id}/react` | React with emoji |
| POST | `/community/stories/{id}/flag` | Report story |
| DELETE | `/community/stories/{id}` | Remove own story |

### Notifications `/notifications`
| Method | Path | Description |
|---|---|---|
| GET | `/notifications/preferences` | Get email preferences |
| PATCH | `/notifications/preferences` | Update preferences |
| POST | `/notifications/send-test` | Send test email |
| GET | `/notifications/unsubscribe` | One-click unsubscribe |

### Privacy `/privacy`
| Method | Path | Description |
|---|---|---|
| GET | `/privacy/settings` | Get privacy settings |
| PATCH | `/privacy/settings` | Update privacy settings |
| GET | `/privacy/data-summary` | GDPR Article 15: what data we hold |
| POST | `/privacy/export` | GDPR Article 20: full data export |
| DELETE | `/privacy/delete-account` | GDPR Article 17: permanent deletion |

---

## Connecting the Frontend

In `betweenyears.html`, replace the stub `handleSignup()` and `saveEntry()` functions with real `fetch()` calls:

```javascript
const API_BASE = 'http://localhost:8000';

async function handleSignup() {
  const name = document.querySelector('.modal-input[placeholder="Your first name"]').value;
  const email = document.querySelector('.modal-input[placeholder="Email address"]').value;
  const password = document.querySelector('.modal-input[placeholder="Create a password"]').value;

  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: name, email, password })
  });
  const data = await res.json();
  if (res.ok) {
    localStorage.setItem('access_token', data.access_token);
    closeModal();
    showToast('🎉', `Welcome, ${name}!`);
  } else {
    showToast('❌', data.detail || 'Signup failed');
  }
}

async function saveEntry() {
  const token = localStorage.getItem('access_token');
  const content = document.getElementById('journalArea').value.trim();
  const mood = document.querySelector('.mood-btn.selected')?.dataset.mood || null;
  
  if (!content) { showToast('✏️', 'Write something first!'); return; }
  if (!token) { openModal(); return; }

  const res = await fetch(`${API_BASE}/journal/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ content, mood })
  });

  if (res.ok) {
    showToast('✓', 'Reflection saved! Keep going.');
    document.getElementById('journalArea').value = '';
    document.getElementById('wordCount').textContent = '0 words';
  } else {
    showToast('❌', 'Could not save — please try again');
  }
}
```

---

## Privacy & Security

- **RLS enabled** on all tables — users can only access their own data
- **Gemini receives anonymized text only** — no name, email, or user ID
- **No PII in AI prompts** — content is capped at 2000 chars and stripped
- **GDPR compliant** — data export (Article 20) and deletion (Article 17) built in
- **Rate limited** — 100 req/min general, 10 AI calls/hour per IP
- **Security headers** — X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **HMAC-signed unsubscribe tokens** — prevents email enumeration
- **Passwords never stored** — delegated entirely to Supabase Auth

---

## Badge System

| Badge | Trigger | XP |
|---|---|---|
| 🌱 First Reflection | First journal entry | 50 |
| 🔥 3-Day Streak | 3 consecutive days | 50 |
| 💎 Values Explorer | Completed values test | 50 |
| 🌊 Deep Diver | Entry > 200 words | 75 |
| ⭐ 10-Day Streak | 10 consecutive days | 100 |
| 🧠 Pattern Seeker | 5 AI analyses | 75 |
| 🤝 Community Voice | Published a story | 50 |
| 🏆 30-Day Streak | 30 consecutive days | 200 |
| 🧹 Mind Clearer | 10 total entries | 100 |

## XP Levels

| Level | XP Range |
|---|---|
| Beginner | 0 – 99 |
| Explorer | 100 – 499 |
| Discoverer | 500 – 1499 |
| Thinker | 1500 – 3999 |
| Sage | 4000+ |
