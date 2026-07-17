import logging
from pathlib import Path
from datetime import datetime, timezone

import joblib
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_PATH = Path(settings.BASE_DIR) / "transactions" / "risk_model.pkl"

# Feature weights for the heuristic model
WEIGHTS = {
    "amount_ratio": 0.35,
    "new_recipient": 0.25,
    "unusual_hour": 0.15,
    "new_device": 0.15,
    "amount_velocity": 0.10,
}


def _extract_features(transaction, baseline, recent_count=0):
    hour = datetime.now(timezone.utc).hour
    typical_min = float(baseline.typical_amount_min)
    typical_max = float(baseline.typical_amount_max)
    amount = float(transaction.amount)

    amount_range = max(typical_max - typical_min, 1)
    amount_mid = (typical_max + typical_min) / 2
    amount_ratio = min(abs(amount - amount_mid) / amount_range, 5.0) / 5.0

    is_new_recipient = 1.0 if transaction.recipient not in baseline.typical_recipients else 0.0

    typical_hours = baseline.typical_hours or list(range(7, 22))
    is_unusual_hour = 0.0 if hour in typical_hours else 1.0

    is_new_device = 1.0 if transaction.device_id and transaction.device_id not in baseline.known_devices else 0.0

    amount_velocity = min(recent_count / 10, 1.0)

    return {
        "amount_ratio": amount_ratio,
        "new_recipient": is_new_recipient,
        "unusual_hour": is_unusual_hour,
        "new_device": is_new_device,
        "amount_velocity": amount_velocity,
    }


def heuristic_risk_score(transaction, baseline, recent_count=0):
    features = _extract_features(transaction, baseline, recent_count)
    score = sum(WEIGHTS[k] * features[k] for k in WEIGHTS)
    score = min(max(score, 0.0), 1.0)
    return score


def _generate_reason(score, features):
    reasons = []
    if features["amount_ratio"] > 0.6:
        reasons.append("Amount significantly outside typical range")
    if features["new_recipient"] > 0.5:
        reasons.append("New/unusual recipient")
    if features["unusual_hour"] > 0.5:
        reasons.append("Transaction outside typical hours")
    if features["new_device"] > 0.5:
        reasons.append("Unrecognized device")
    if features["amount_velocity"] > 0.5:
        reasons.append("Unusual transaction frequency")
    if not reasons:
        reasons.append("Routine transaction")
    return "; ".join(reasons)


class RiskModel:
    def __init__(self):
        self.model = None
        self._load()

    def _load(self):
        if MODEL_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
                logger.info("Loaded risk model from %s", MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load model: %s. Using heuristic fallback.", e)
                self.model = None

    def predict(self, transaction, baseline, recent_count=0):
        features = _extract_features(transaction, baseline, recent_count)

        if self.model is not None:
            try:
                X = np.array([[features[k] for k in WEIGHTS]])
                score = float(self.model.predict_proba(X)[0, 1])
                score = min(max(score, 0.0), 1.0)
            except Exception as e:
                logger.warning("Model prediction failed: %s. Falling back to heuristic.", e)
                score = heuristic_risk_score(transaction, baseline, recent_count)
        else:
            score = heuristic_risk_score(transaction, baseline, recent_count)

        reason = _generate_reason(score, features)
        return {"risk_score": round(score, 4), "reason": reason}

    def is_loaded(self):
        return self.model is not None


risk_model = RiskModel()
