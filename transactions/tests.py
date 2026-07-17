from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from .models import Transaction, LedgerEntry
from . import services


class ServicesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_get_or_create_baseline_creates_default(self):
        baseline = services.get_or_create_baseline(str(self.user.id))
        self.assertEqual(baseline.user_id, str(self.user.id))
        self.assertEqual(baseline.typical_amount_max, 50000)

    def test_get_or_create_baseline_returns_existing(self):
        baseline = services.get_or_create_baseline(str(self.user.id))
        same = services.get_or_create_baseline(str(self.user.id))
        self.assertEqual(baseline.id, same.id)

    @patch("transactions.services.call_ml_scoring_service")
    def test_score_transaction_approved(self, mock_call):
        mock_call.return_value = {"risk_score": 0.3, "reason": "Looks fine"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test_recipient",
            amount=10000,
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.APPROVED)
        self.assertAlmostEqual(result.risk_score, 0.3)

    @patch("transactions.services.call_ml_scoring_service")
    def test_score_transaction_flagged(self, mock_call):
        mock_call.return_value = {"risk_score": 0.85, "reason": "Suspicious activity"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="new_recipient",
            amount=500000,
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.FLAGGED)
        self.assertAlmostEqual(result.risk_score, 0.85)

    @patch("transactions.services.call_ml_scoring_service")
    def test_score_transaction_ml_down_failsafe(self, mock_call):
        mock_call.side_effect = services.ScoringServiceError("Connection refused")
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.FLAGGED)
        self.assertEqual(result.risk_score, 1.0)
        self.assertIn("Unable to verify", result.risk_reason)

    def test_apply_user_decision_confirm(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
            status=Transaction.Status.FLAGGED,
            risk_score=0.9,
        )
        result = services.apply_user_decision(transaction, "confirm")
        self.assertEqual(result.status, Transaction.Status.CONFIRMED)
        self.assertIsNotNone(result.decided_at)

    def test_apply_user_decision_cancel(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
            status=Transaction.Status.FLAGGED,
            risk_score=0.9,
        )
        result = services.apply_user_decision(transaction, "cancel")
        self.assertEqual(result.status, Transaction.Status.CANCELLED)
        self.assertIsNotNone(result.decided_at)

    def test_apply_user_decision_not_flagged(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
            status=Transaction.Status.APPROVED,
        )
        with self.assertRaises(ValueError):
            services.apply_user_decision(transaction, "confirm")

    def test_score_transaction_creates_ledger_entry(self):
        with patch("transactions.services.call_ml_scoring_service") as mock_call:
            mock_call.return_value = {"risk_score": 0.3, "reason": "All good"}
            transaction = Transaction.objects.create(
                user_id=str(self.user.id),
                recipient="test",
                amount=5000,
            )
            services.score_transaction(transaction)
            entries = LedgerEntry.objects.filter(transaction=transaction)
            self.assertEqual(entries.count(), 1)
            self.assertEqual(entries.first().event_type, "scored")


class TransactionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_create_transaction_success(self):
        with patch("transactions.services.call_ml_scoring_service") as mock_call:
            mock_call.return_value = {"risk_score": 0.2, "reason": "Low risk"}
            data = {"recipient": "someone", "amount": "5000.00", "device_id": "device_1"}
            response = self.client.post("/api/transactions/", data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertIn("id", response.data)
            self.assertEqual(response.data["user_id"], str(self.user.id))

    def test_create_transaction_unauthenticated(self):
        self.client.force_authenticate(user=None)
        data = {"recipient": "someone", "amount": "5000.00"}
        response = self.client.post("/api/transactions/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_transaction_detail(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
            status=Transaction.Status.APPROVED,
        )
        response = self.client.get(f"/api/transactions/{transaction.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["id"]), str(transaction.id))

    def test_cannot_access_others_transaction(self):
        other_user = User.objects.create_user(username="other", password="testpass123")
        transaction = Transaction.objects.create(
            user_id=str(other_user.id),
            recipient="test",
            amount=10000,
        )
        response = self.client.get(f"/api/transactions/{transaction.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_ledger(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test",
            amount=10000,
        )
        LedgerEntry.objects.create(
            user_id=str(self.user.id),
            transaction=transaction,
            event_type="scored",
            detail="test entry",
        )
        response = self.client.get("/api/me/ledger/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_baseline(self):
        response = self.client.get("/api/me/baseline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], str(self.user.id))
