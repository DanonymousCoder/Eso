# DEVLOG — AI Features Branch

## Branch
`ai-features` (branched from `main`)

## Changes

### 1. Tiered AI Scoring Pipeline (`transactions/services.py`)
Replaced the single `call_ml_scoring_service` function with a 3-tier fallback pipeline:

| Tier | Engine | When |
|------|--------|------|
| 1 | Local `.pkl` model (heuristic + optional sklearn) | Always runs first — fast, no network |
| 2 | Groq API (Llama 3 70B) | Only if Tier 1 flags a transaction — richer reasoning |
| 3 | External ML FastAPI (original) | If both Tiers 1 & 2 fail — original fallback |

- `_tier1_local_pkl()` — calls `risk_model.predict()` from `ml_model.py`
- `_tier2_groq()` — calls `groq_client.analyze_transaction()` for deep analysis on flagged txs
- `_tier3_external_ml()` — the original HTTP call to the ML dev's endpoint
- If all tiers fail, flags conservatively (risk_score=1.0)
- Ledger entries now include the source tag: `[pkl]`, `[groq]`, or `[heuristic]`
- `apply_user_decision()` generates Groq-powered plain-language explanations for the ledger

### 2. Local Pickle Model (`transactions/ml_model.py`)
- `RiskModel` class loaded from `transactions/risk_model.pkl` via `joblib`
- Heuristic fallback when `.pkl` is missing or fails to load
- Features extracted:
  - `amount_ratio` — how far amount deviates from baseline (35% weight)
  - `new_recipient` — unseen recipient (25%)
  - `unusual_hour` — outside typical hours (15%)
  - `new_device` — unrecognized device (15%)
  - `amount_velocity` — recent tx frequency (10%)
- `heuristic_risk_score()` computes a deterministic 0–1 score when sklearn unavailable
- `RiskModel.predict()` uses sklearn `LogisticRegression.predict_proba` if model is loaded

### 3. Groq API Client (`transactions/groq_client.py`)
- `analyze_transaction()` — sends transaction + baseline to Groq, returns structured JSON with risk_score, reason, red_flags, suggested_action
- `explain_decision()` — generates 1-sentence plain-language explanation for the ledger after user decision
- Uses `httpx` for async-capable HTTP calls
- Prompt engineered for the Eso guardian persona (Nigerian bank fraud context)
- Configured via settings: `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_TIMEOUT_SECONDS`
- Returns `None` silently if API key is missing or call fails (non-blocking)

### 4. Training Command (`transactions/management/commands/train_model.py`)
- `python manage.py train_model` generates 10,000 synthetic training samples
- Features: amount_ratio, new_recipient, unusual_hour, new_device, amount_velocity
- Target: weighted sum of features + Gaussian noise, thresholded at 0.5
- Trains `LogisticRegression(class_weight='balanced')` and saves to `transactions/risk_model.pkl`

### 5. Settings (`eso_backend/settings.py`)
Added Groq config variables:
```python
GROQ_API_KEY = config("GROQ_API_KEY", default="")
GROQ_MODEL = config("GROQ_MODEL", default="llama-3.3-70b-versatile")
GROQ_TIMEOUT_SECONDS = config("GROQ_TIMEOUT_SECONDS", default=10, cast=int)
```

### 6. Dependencies (`requirements.txt`)
Added:
- `scikit-learn>=1.5` — LogisticRegression model
- `joblib>=1.4` — pickle serialization
- `httpx>=0.27` — async HTTP for Groq API

### 7. Environment (`transactions/risk_model.pkl`)
- 10,000-sample synthetic logistic regression model, ~1 KB
- `.pkl` files added to `.gitignore`

### 8. Test Updates (`transactions/tests.py`)
- Updated 5 tests to mock `_tier1_local_pkl` and `_tier2_groq` instead of the removed `call_ml_scoring_service`

## How to Use

```bash
# Train/fresh the model
python manage.py train_model

# Run with Groq (optional — set key in .env)
echo "GROQ_API_KEY=gsk_your_key_here" >> .env

# Run tests
pytest
```

## Architecture Flow

```
Transaction created
  └→ Tier 1: Local .pkl model ──→ score < 0.7 → APPROVED ✓
       │                              └→ Ledger [pkl]
       └→ score >= 0.7
            └→ Tier 2: Groq API ──→ deeper analysis → FLAGGED
                 │                    └→ Ledger [groq] with red_flags
                 └→ Groq unavailable
                      └→ Tier 3: External ML ──→ same as original
                           └→ All down → FAILSAFE (risk=1.0)
```
