import logging
import json

from django.conf import settings

logger = logging.getLogger(__name__)


def _build_analysis_prompt(transaction, baseline):
    return f"""You are Eso, an AI transaction guardian for a Nigerian bank. Analyze this transaction for fraud risk.

Transaction details:
- Recipient: {transaction.recipient}
- Amount: ₦{transaction.amount}
- Device ID: {transaction.device_id or "Not provided"}
- Hour: {transaction.created_at.hour if transaction.created_at else "Unknown"}

User's behavioral baseline:
- Typical recipients: {baseline.typical_recipients or "None yet"}
- Typical amount range: ₦{baseline.typical_amount_min} - ₦{baseline.typical_amount_max}
- Typical hours: {baseline.typical_hours}
- Known devices: {baseline.known_devices or "None yet"}

Respond in this exact JSON format:
{{"risk_score": <0.0 to 1.0>, "reason": "<1-2 sentence explanation>", "red_flags": ["<specific concern>", ...], "suggested_action": "<approve | flag | block>"}}"""


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
