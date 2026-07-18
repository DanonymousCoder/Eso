import logging
import json

from django.conf import settings

logger = logging.getLogger(__name__)


def _build_analysis_prompt(transaction, baseline):
    known_recipients = baseline.typical_recipients or []
    is_new = transaction.recipient not in known_recipients
    recipient_context = (
        f"UNKNOWN — '{transaction.recipient}' has NEVER been paid before"
        if is_new
        else f"KNOWN — '{transaction.recipient}' is in the user's approved list"
    )
    amount = float(transaction.amount)
    lo = float(baseline.typical_amount_min)
    hi = float(baseline.typical_amount_max)
    amount_context = (
        f"₦{amount:,.0f} (OUTSIDE typical range ₦{lo:,.0f}–₦{hi:,.0f})"
        if amount < lo or amount > hi
        else f"₦{amount:,.0f} (within typical range ₦{lo:,.0f}–₦{hi:,.0f})"
    )
    hour = transaction.created_at.hour if transaction.created_at else "Unknown"
    typical_hours = baseline.typical_hours or list(range(7, 22))
    hour_context = (
        f"{hour}:00 (OUTSIDE usual hours {min(typical_hours)}:00–{max(typical_hours)}:00)"
        if isinstance(hour, int) and hour not in typical_hours
        else f"{hour}:00 (within usual active hours)"
    )
    return f"""You are Eso, an AI transaction guardian for a Nigerian bank. Analyze this transaction for fraud risk.

TRANSACTION DATA:
- Recipient: {recipient_context}
- Amount: {amount_context}
- Device: {"NEW device not seen before" if transaction.device_id and transaction.device_id not in (baseline.known_devices or []) else "Recognised device"}
- Time: {hour_context}
- Total known recipients: {len(known_recipients)}

NIGERIAN FRAUD PATTERNS TO CHECK:
- SIM swap urgency (unknown recipient + large amount)
- Late-night large wires (post 22:00)
- New device + high amount = session hijack signal
- Amounts far above baseline = account takeover pattern

INSTRUCTIONS:
- Be SPECIFIC: mention the actual amount, recipient name, and hour in your reason.
- Do NOT say "the recipient is unknown" generically — say WHO the recipient is and WHY it is suspicious or safe.
- For approved transactions, explain WHY it looks normal (e.g. amount is within range, recipient is known).
- Reason must be 1-2 sentences max, plain English a bank customer can understand.

Respond ONLY in this exact JSON format:
{{"risk_score": <0.0 to 1.0>, "reason": "<specific 1-2 sentence explanation with real values>", "red_flags": ["<specific concern with values>"], "suggested_action": "<approve | flag | block>"}}"""


def analyze_transaction(transaction, baseline):
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. Skipping Groq analysis.")
        return None

    try:
        import httpx

        prompt = _build_analysis_prompt(transaction, baseline)

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Eso, an AI transaction guardian. Analyze transactions for fraud risk and return JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=settings.GROQ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(content)

        return {
            "risk_score": float(result.get("risk_score", 0.5)),
            "reason": result.get("reason", ""),
            "red_flags": result.get("red_flags", []),
            "suggested_action": result.get("suggested_action", "flag"),
        }

    except ImportError:
        logger.warning("httpx not installed. Install with: pip install httpx")
        return None
    except Exception as e:
        logger.error("Groq API call failed: %s", e)
        return None


def explain_decision(transaction):
    if not settings.GROQ_API_KEY:
        return None

    try:
        import httpx

        prompt = f"""A transaction was {'approved' if transaction.status == 'approved' else transaction.status} by the system.
Transaction: ₦{transaction.amount} to {transaction.recipient}
Risk score: {transaction.risk_score}
Reason: {transaction.risk_reason}

Write a 1-sentence plain-language explanation the user will see in their transparency ledger. Be specific and helpful."""

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are Eso's explanation engine. Write short, clear explanations."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 150,
            },
            timeout=settings.GROQ_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error("Groq explanation failed: %s", e)
        return None
