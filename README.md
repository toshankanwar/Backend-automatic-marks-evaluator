# AutoGrade Backend (FastAPI)

Production-ready backend for **AutoGrade** — an AI-powered academic evaluation platform that lets teachers/students upload answer sheets, extract text using OCR, evaluate responses against model answers/rubrics, generate marks with feedback, and track performance analytics — with JWT auth, profile management, account deletion, forgot/reset password flow, and cron cleanup support for expired and used tokens.

---

## Features

- FastAPI + Uvicorn
- MongoDB integration
- JWT authentication
- Profile APIs
- Account deletion (with password + explicit confirmation text)
- Forgot password (email reset link)
- Reset password (secure one-time token)
- Daily cleanup endpoint for password reset tokens (cron-job.org compatible)

---

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- MongoDB
- Pydantic / pydantic-settings
- Passlib / bcrypt
- Email provider (Brevo/SMTP)

---

## Project Structure (example)

backend/
├─ app/
│  ├─ main.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ database.py
│  │  └─ security.py
│  ├─ routes/
│  │  ├─ auth_routes.py
│  │  ├─ profile_routes.py
│  │  └─ maintenance_routes.py
│  ├─ schemas/
│  │  └─ auth_schema.py
│  ├─ dependencies/
│  │  └─ auth.py
│  └─ services/
│     └─ email_service.py
├─ .env
├─ requirements.txt
└─ README.md

---

## Environment Variables

Create `backend/.env`:

APP_NAME=AutoGrade
FRONTEND_URL=http://localhost:3000

HOST=0.0.0.0
PORT=8000

MONGO_URI=mongodb://localhost:27017
DB_NAME=autograde

JWT_SECRET=change-this-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

RESET_TOKEN_EXPIRE_MINUTES=15

BREVO_API_KEY=
EMAIL_FROM=
EMAIL_FROM_NAME=AutoGrade

CRON_SECRET=your-super-long-random-secret

---

## Run Locally

1) Create virtual environment

python -m venv .venv

2) Activate it

Windows:
.venv\Scripts\activate

Linux/macOS:
source .venv/bin/activate

3) Install dependencies

pip install -r requirements.txt

4) Run backend

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API docs:
- http://localhost:8000/docs
- http://localhost:8000/redoc

---

## Auth Dependency (example)

Use this in protected routes:

from fastapi import Header, HTTPException
from app.core.security import decode_token

async def get_current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing/invalid token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

---

## Forgot Password Flow

POST /auth/forgot-password

- Accepts email
- Always returns generic message
- Creates secure reset token
- Stores token hash in `password_resets`
- Sends email link:
  `${FRONTEND_URL}/reset-password?token=<raw_token>`

---

## Reset Password Flow

POST /auth/reset-password

- Accepts token, new_password, confirm_password
- Validates token hash, used=false, not expired
- Updates password hash
- Marks token used
- Optional: invalidates all other active reset tokens

---

## Datetime Fix (Important)

If Mongo returns naive datetime, normalize before comparing with UTC-aware `now`:

from datetime import timezone

def _to_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

---

## Profile APIs

GET /profile/me  
PUT /profile/me  
DELETE /profile/me

Delete flow verifies:
- password is correct
- confirm_text == "DELETE"

Also delete related data collections (example):
- evaluations
- results
- ocr_accuracies
- users

---

## Cron Cleanup Endpoint

GET /maintenance/cleanup-password-resets

Header required:
x-cron-secret: <CRON_SECRET>

Deletes:
- used reset tokens
- expired reset tokens

Example response:

{
  "ok": true,
  "deleted_count": 12,
  "ran_at": "2026-04-19T12:00:00+00:00"
}

---

## cron-job.org Setup (Every 24 Hours)

- URL: https://your-domain.com/maintenance/cleanup-password-resets
- Method: GET
- Header:
  - x-cron-secret: your-super-long-random-secret
- Request body: empty
- HTTP auth username/password: empty

---

## Common Errors

1) AttributeError: RESET_TOKEN_EXPIRE_MINUTES missing  
Fix: add `RESET_TOKEN_EXPIRE_MINUTES` in config + .env

2) TypeError: offset-naive vs offset-aware datetime  
Fix: normalize datetime using `_to_utc()` before comparison

3) NotImplementedError in get_current_user  
Fix: replace placeholder with actual JWT dependency

4) Frontend "Failed to fetch"  
Check backend running, API base URL, CORS, endpoint path

---

## cURL Examples

Forgot password:

curl -X POST "http://localhost:8000/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"user@example.com\"}"

Reset password:

curl -X POST "http://localhost:8000/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"<token>\",\"new_password\":\"NewPass@123\",\"confirm_password\":\"NewPass@123\"}"

Cron cleanup:

curl -X GET "http://localhost:8000/maintenance/cleanup-password-resets" \
  -H "x-cron-secret: your-super-long-random-secret"

---

## License

MIT (or your preferred license)