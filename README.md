# Eso — AI Transaction Guardian

Eso now includes a React + Tailwind web dashboard and the Django REST API that
scores simulated transfers, pauses unusual activity, and records every outcome
in a transparency ledger.

## Frontend

The frontend lives in `src/` and covers the complete hackathon demonstration:

- authenticated sign-in and registration;
- hashed four-digit payment PIN authorization with failed-attempt lockout;
- responsive guardian dashboard;
- simulated Nigerian bank transfer form;
- live API-backed transaction analysis;
- required reflection questions for every flagged transfer;
- red-flag phrase escalation and a server-enforced cooling-off period;
- non-overridable critical holds with an independent staff review queue;
- shared beneficiary reports that feed back into future risk scores;
- approved, overridden, and cancelled outcome screens;
- searchable, filterable, exportable transparency ledger; and
- guardian preferences, notifications, and appearance settings.

Create a local frontend environment file if the API is not running on the
default address:

```bash
cp .env.frontend.example .env.local
```

Then run:

```bash
npm install
npm run dev
```

The frontend expects Django at `http://localhost:8000/api` by default and uses
the JWT login, refresh, transaction, reflection, report, decision, baseline,
and ledger endpoints documented below.

## Backend

Django REST Framework backend for the Eso hackathon MVP. Handles transaction
intake, calls out to the ML dev's scoring service, and maintains the
transparency ledger.

## Structure

```
eso_backend/
├── eso_backend/        # project config (settings, root urls)
├── transactions/        # the one app — everything lives here for a hackathon scope
│   ├── models.py         # Transaction, BehaviorBaseline, RecipientReport, LedgerEntry
│   ├── serializers.py     # request/response validation
│   ├── services.py        # business logic + ML service integration (the important file)
│   ├── views.py            # thin — just calls services.py and returns a Response
│   └── urls.py
├── manage.py
└── requirements.txt
```

**Why a `services.py` layer:** views should just handle HTTP in/out. All the
actual logic — talking to the ML service, deciding what counts as risky,
writing to the ledger — lives in `services.py`. This means when the ML dev's
endpoint contract changes (and it will, mid-hackathon), you edit one file,
not scattered logic across every view.

## API Routes

| Method | Route | Auth? | Purpose |
|---|---|---|---|
| POST | `/api/auth/register/` | No | Create an account, returns tokens immediately |
| POST | `/api/auth/login/` | No | Log in, returns access + refresh tokens |
| POST | `/api/auth/refresh/` | No | Exchange a refresh token for a new access token |
| GET | `/api/auth/me/` | Yes | Confirm which user a token belongs to |
| GET/POST | `/api/auth/payment-pin/` | Yes | Read PIN status or create/change the hashed payment PIN |
| GET | `/api/me/baseline/` | Yes | Get (or auto-create) the current user's behavioral baseline |
| POST | `/api/transactions/` | Yes | Verify the payment PIN, then submit and score a transaction |
| GET | `/api/transactions/<id>/` | Yes | Fetch a transaction's current state (owner only) |
| POST | `/api/transactions/<id>/reflection/` | Yes | Record the required reflection response and escalate coached-payment language |
| POST | `/api/transactions/<id>/report/` | Yes | Report the beneficiary to the shared recipient-risk registry |
| POST | `/api/transactions/<id>/review-request/` | Yes | Place a critical transfer into independent security review |
| POST | `/api/transactions/<id>/decision/` | Yes | Confirm or cancel after reflection and any required cooling-off period |
| GET | `/api/security-reviews/` | Staff | List critical transfers awaiting independent review |
| POST | `/api/security-reviews/<id>/decision/` | Staff | Independently approve or block a held transfer |
| GET | `/api/me/ledger/` | Yes | Transparency log for the activity screen |

**Auth is JWT-based** (`djangorestframework-simplejwt`). All routes except
register/login/refresh require `Authorization: Bearer <access_token>`.
`user_id` is never accepted from the client — it is always derived from the
authenticated token, so nobody can submit transactions or read data under
someone else's identity.

Cooling-off and reviewer authorization are checked again by Django. Critical
transfers cannot be self-approved at all, so removing a disabled state in
browser developer tools does not release the payment.

## Integrating with the ML dev

Set `ML_SCORING_SERVICE_URL` (defaults to `http://localhost:8001/score`) via
a `.env` file — don't hardcode a teammate's local IP into the codebase.

**Agree this contract with the ML dev before they build anything:**

Request sent to their FastAPI endpoint:
```json
{
  "user_id": "u123",
  "recipient": "new_recipient_456",
  "amount": 450000,
  "device_id": "device_abc",
  "hour_of_day": 2,
  "baseline": {
    "typical_recipients": ["r1", "r2"],
    "typical_amount_min": 1000,
    "typical_amount_max": 50000,
    "typical_hours": [7, 8, 9, "..."],
    "known_devices": ["device_abc"]
  }
}
```

Expected response:
```json
{ "risk_score": 0.87, "reason": "New recipient, amount 9x typical, late-night timing" }
```

If the ML service is down or times out, `services.py` fails safe: it flags
the transaction for manual review rather than silently approving it.

## Running it

Run migrations and start Django, then start Vite in a second terminal:

```bash
python manage.py migrate
python manage.py runserver
npm run dev
```

Create a separate reviewer account for the demo. Do not reuse the sender's
credentials:

```bash
python manage.py create_demo_reviewer --password "choose-a-demo-password"
```

Sign into a second browser profile with username `eso_reviewer`; staff users
see the **Security Reviews** queue in the sidebar. No default reviewer password
is stored in the repository.

The seeded beneficiary account `8091234567` has three simulated community
reports. Use the “Community-reported account” scenario to demonstrate a
transfer being escalated because of network reputation rather than amount.

## Not in scope for the hackathon MVP

- No payment gateway of any kind — transactions are simulated end-to-end.
  This matches the Stage 1 proposal's hackathon MVP scope (section 8.2:
  simulated transaction data), so it's not a gap against what was promised.
- No real Mono/Okra account-aggregation integration — that's phase 3 in the
  proposal, post-hackathon.
- No facial identity matching. A future liveness challenge should use real
  landmark detection and be described accurately as presence/liveness, not as
  proof that the account owner is acting free from coercion.
