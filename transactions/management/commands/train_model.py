import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

MODEL_PATH = Path(settings.BASE_DIR) / "transactions" / "risk_model.pkl"


class Command(BaseCommand):
    help = "Train and save the risk scoring model to a pickle file"

    def handle(self, *args, **options):
        self.stdout.write("Generating synthetic training data...")

        np.random.seed(42)
        n_samples = 10000

        amount_ratio = np.random.uniform(0, 1, n_samples)
        new_recipient = np.random.randint(0, 2, n_samples).astype(float)
        unusual_hour = np.random.randint(0, 2, n_samples).astype(float)
        new_device = np.random.randint(0, 2, n_samples).astype(float)
        amount_velocity = np.random.uniform(0, 1, n_samples)

        X = np.column_stack([amount_ratio, new_recipient, unusual_hour, new_device, amount_velocity])

        risk = (
            0.35 * amount_ratio
            + 0.25 * new_recipient
            + 0.15 * unusual_hour
            + 0.15 * new_device
            + 0.10 * amount_velocity
            + np.random.normal(0, 0.05, n_samples)
        )
        y = (risk >= 0.5).astype(int)

        model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
        model.fit(X, y)

        joblib.dump(model, MODEL_PATH)
        self.stdout.write(self.style.SUCCESS(f"Model trained and saved to {MODEL_PATH}"))
        self.stdout.write(f"Training samples: {n_samples}")
        self.stdout.write(f"Fraud ratio: {y.mean():.2%}")
