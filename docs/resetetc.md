# Local reset, verify, and sign-in

Do these steps on a laptop, then use the troubleshooting table if sign-in fails. The repo is public. This page uses placeholders only. Do not commit `.env`, `local/stub-users.json`, `local/email-inbox/`, or `local/audit-email-hmac.key`. Passwords stay in `local/stub-users.json`. They are not printed here. Auth rules are in [auth.md](auth.md).

## Steps

1. Update `dev` and install.

   ```bash
   git checkout dev
   git pull origin dev
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy the local files.

   ```bash
   cp .env.example .env
   cp local/stub-users.example.json local/stub-users.json
   ```

   In `local/stub-users.json`, replace the placeholder for `admintest` and for `membertest`. The API refuses a blank password and the placeholders `replace-me`, `changeme`, `password`, and `your-password`. Those two names are the only accounts the sign-in form accepts. **Get started** sends a sign-up only for an `@example.test` address.

3. Edit `.env`. Generate a value with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   `JWT_SECRET_KEY` must be at least 32 characters. The API exits if it is missing, shorter than that, or still the placeholder in `.env.example`.

   ```bash
   AJO_ENV=local
   SEED_DEMO_ACCOUNTS=true
   JWT_SECRET_KEY=<generated-value>
   DATABASE_URL=sqlite:///local/ajo.db
   AJO_API_BASE=http://127.0.0.1:8000
   PUBLIC_APP_URL=http://localhost:8055
   EMAIL_SENDER=
   AUDIT_EMAIL_HMAC_KEY=
   ```

   Leave `EMAIL_SENDER` empty. On `AJO_ENV=local` or `dev`, empty is a local sender. `dev`, `file`, `inbox`, and `console` do the same. Leave `AUDIT_EMAIL_HMAC_KEY` empty on a laptop. The API then creates git-ignored `local/audit-email-hmac.key` (or the path in `AUDIT_EMAIL_HMAC_KEY_FILE`). If you set the HMAC key, use another generated value. `PUBLIC_APP_URL` is the Dash origin written into email links. `http://127.0.0.1:8000` is the API, so a link built from that URL does not open the reset page. An unset `PUBLIC_APP_URL` already defaults to `http://localhost:8055`.

4. Create the tables. Alembic reads `DATABASE_URL` from the environment, then from `.env`.

   ```bash
   alembic upgrade head
   ```

   There is no seed command. Seeding runs when the API process starts, and only when `SEED_DEMO_ACCOUNTS` is `true` (`1`, `yes`, and `on` also count) and `AJO_ENV` is `local` or `dev`.

5. Start the API on port 8000.

   ```bash
   uvicorn api:app --reload --no-proxy-headers
   ```

   Startup inserts `admintest@example.test` and `membertest@example.test` from `local/stub-users.json` and marks them verified. A later start overwrites those two password hashes from that file. `http://127.0.0.1:8000/docs` and `http://localhost:8000/docs` are Swagger only when `AJO_ENV` is `local` or `dev`. Any other value, including unset, does not serve `/docs`.

6. Start Dash on port 8055, in a second terminal.

   ```bash
   python app_dash_web.py
   ```

   If `AJO_API_BASE` is empty, this command sets it to `http://127.0.0.1:8000` before the UI listens. Setting `AJO_API_BASE=http://localhost:8000` in `.env` reaches that same API. The old stub sign-in runs only when `AJO_API_BASE` stays empty, which is the test suite, not this command. Open `http://127.0.0.1:8055`.

7. Sign in at `/signin`. The field placeholder is Username. Enter `admintest` or `membertest`, or `admintest@example.test` or `membertest@example.test`. Dash sends the email to `POST /api/v1/auth/login`. The password is the one in `local/stub-users.json`.

8. Request a reset. On `/signin`, choose **Forgot password?**, enter the email (not the bare username), and submit. The page says `If an account exists for that email, a reset link is on its way.` Each message is a JSON file under `local/email-inbox` (`AJO_EMAIL_INBOX` overrides that folder). Open the newest file. The link in `body` is `{PUBLIC_APP_URL}/reset-password#token=...`. Paste it into the browser. The page reads the fragment and removes it from the address bar.

9. Set a new password on `/reset-password`. It must be at least 8 characters and at most 72 bytes. Success goes to `/signin` and shows `Your password has been reset. Sign in again.` That replaces the seeded password. A used link, or a link older than 30 minutes, shows `This reset link is invalid or has expired.`

10. From Settings, choose **Email reset link**. That calls the same forgot route for the signed-in email. Read the new file in `local/email-inbox`.

11. Sign up from **Get started** with an `@example.test` address. Any other domain stays on the form with `Use an @example.test address.` The inbox file contains `{PUBLIC_APP_URL}/verify-email#...`, which lasts 24 hours. Open it on the Dash origin. A used or expired link shows `This verification link is invalid or has expired.` Seeded `admintest` and `membertest` are already verified.

## Why an older local setup stops

Sign-in from `python app_dash_web.py` goes to the API, so that process has to be running. New auth tables come from `alembic upgrade head`. An old `local/ajo.db` does not have them. Login hashes the email for the rate limit. That uses `AUDIT_EMAIL_HMAC_KEY` or, when `AJO_ENV` is `local` or `dev`, the local key file. With neither, the API returns 503 and `Audit logging is not configured.` A completed reset changes `membertest`'s password until the API starts again and copies the hash from `local/stub-users.json`.

## Troubleshooting

Check the uvicorn terminal first. Then open `http://127.0.0.1:8000/docs`.

Dash shows `Sign-in failed.` when login is refused (401 or 429). A connection error or any 5xx, including the audit 503, is `Service unavailable, please try again shortly`.

| What you see | What it means |
|---|---|
| The browser cannot open `/docs`. Uvicorn shows no new request. Dash says the service is unavailable. | The API is not running, or Dash is calling a different origin than uvicorn. The start command listens on `127.0.0.1:8000`. |
| `/docs` is 404. | `AJO_ENV` is unset or is not `local` or `dev`, so Swagger is off. If `AUDIT_EMAIL_HMAC_KEY` is also empty, login returns 503. The key file is created only for `local` and `dev`. |
| Uvicorn prints a missing-table traceback. `/health` can still answer, because it only runs `SELECT 1`. Dash says the service is unavailable. | Migrations did not run against this `DATABASE_URL`. Run `alembic upgrade head` with the same URL the API process uses. A different `DATABASE_URL` in one terminal migrates or seeds another file. |
| Uvicorn exits at startup and prints `SEED_DEMO_ACCOUNTS` or a stub-credential error. | The flag is on while `AJO_ENV` is not `local` or `dev`, or `local/stub-users.json` is missing or still a placeholder. |
| `/docs` loads. Sign-in says `Sign-in failed.` Uvicorn shows 401 `Invalid email or password.` | `SEED_DEMO_ACCOUNTS` was not true, so the two users were not inserted, or the password is not the one in `local/stub-users.json`. A reset changes that password. Restart uvicorn with `SEED_DEMO_ACCOUNTS=true` to write the stub password back, or request another reset link. |
| Sign-in says `Sign-in failed.` Uvicorn shows 429 `Too many attempts. Try again later.` | Login locks on the 5th failed password for 1 minute, then at 10 failures for 15 minutes, then at 20 for 1 hour. Later multiples of 5 stay at 1 hour. A quiet 24 hours with no lock in force clears that streak. On `local` and `dev` the caps are 10000 per IP and 100 per account, so the lock is what stops repeated guesses. A correct password clears the login streak. |
| Dash says the service is unavailable and uvicorn shows 503 `Audit logging is not configured.` | No HMAC key. Set `AJO_ENV=local` and restart so `local/audit-email-hmac.key` is created, or set `AUDIT_EMAIL_HMAC_KEY` to a generated local value. |
| The reset or verify link opens the wrong host, often port 8000. | `PUBLIC_APP_URL` is stale. Set `http://localhost:8055` and request a new link. |
