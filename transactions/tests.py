from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import Transaction, LedgerEntry, RecipientReport, SecurityReview
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

    @patch("transactions.services._tier2_groq", return_value=None)
    @patch("transactions.services._tier1_local_pkl")
    def test_score_transaction_approved(self, mock_tier1, _mock_groq):
        mock_tier1.return_value = {"risk_score": 0.3, "reason": "Looks fine"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="test_recipient",
            amount=10000,
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.APPROVED)
        self.assertAlmostEqual(result.risk_score, 0.3)

    @patch("transactions.services._tier2_groq", return_value=None)
    @patch("transactions.services._tier1_local_pkl")
    def test_score_transaction_flagged(self, mock_tier1, _mock_tier2):
        mock_tier1.return_value = {"risk_score": 0.85, "reason": "Suspicious activity"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="new_recipient",
            amount=500000,
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.FLAGGED)
        self.assertAlmostEqual(result.risk_score, 0.85)

    @patch("transactions.services._tier2_groq", return_value=None)
    @patch("transactions.services._tier1_local_pkl", return_value=None)
    def test_score_transaction_ml_down_failsafe(self, mock_tier1, mock_tier2):
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
            reflection_submitted_at=timezone.now(),
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
            reflection_submitted_at=timezone.now(),
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
        with patch("transactions.services._tier2_groq", return_value=None), \
             patch("transactions.services._tier1_local_pkl") as mock_tier1:
            mock_tier1.return_value = {"risk_score": 0.3, "reason": "All good"}
            transaction = Transaction.objects.create(
                user_id=str(self.user.id),
                recipient="test",
                amount=5000,
            )
            services.score_transaction(transaction)
            entries = LedgerEntry.objects.filter(transaction=transaction)
            self.assertEqual(entries.count(), 1)
            self.assertEqual(entries.first().event_type, "scored")

    @patch("transactions.services._tier2_groq", return_value=None)
    @patch("transactions.services._tier1_local_pkl")
    def test_baseline_updates_on_approved_transaction(self, mock_tier1, _mock_groq):
        mock_tier1.return_value = {"risk_score": 0.2, "reason": "Routine transfer"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="GTBank - Ada Okafor",
            amount=85000,
            device_id="demo-device",
        )
        services.score_transaction(transaction)
        baseline = services.get_or_create_baseline(str(self.user.id))
        self.assertIn("GTBank - Ada Okafor", baseline.typical_recipients)
        self.assertIn("demo-device", baseline.known_devices)
        self.assertGreaterEqual(float(baseline.typical_amount_max), 85000)

    @patch("transactions.services._tier2_groq", return_value=None)
    def test_baseline_updates_when_user_confirms_flagged(self, _mock_groq):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id),
            recipient="Access Bank - Chidi Eze",
            amount=1500000,
            status=Transaction.Status.FLAGGED,
            risk_score=0.9,
            reflection_submitted_at=timezone.now(),
        )
        services.apply_user_decision(transaction, "confirm")
        baseline = services.get_or_create_baseline(str(self.user.id))
        self.assertIn("Access Bank - Chidi Eze", baseline.typical_recipients)
        self.assertGreaterEqual(float(baseline.typical_amount_max), 1500000)

    def test_reflection_blocks_short_answer(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="test", amount=10000,
            status=Transaction.Status.FLAGGED, reflection_prompt="Why?",
        )
        with self.assertRaisesMessage(ValueError, "Please tell us a bit more"):
            services.submit_reflection(transaction, "because")

    def test_confirm_is_blocked_until_reflection_is_submitted(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="test", amount=10000,
            status=Transaction.Status.FLAGGED, risk_tier=Transaction.RiskTier.HIGH,
        )
        with self.assertRaisesMessage(ValueError, "reflection question"):
            services.apply_user_decision(transaction, "confirm")

    def test_reflection_answer_is_logged(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Ada", amount=10000,
            status=Transaction.Status.FLAGGED, reflection_prompt="What is this for?",
        )
        result = services.submit_reflection(transaction, "Monthly support for my sister")
        self.assertEqual(result.reflection_answer, "Monthly support for my sister")
        self.assertEqual(result.reflection_red_flags, [])
        entry = LedgerEntry.objects.get(transaction=transaction, event_type="reflection_completed")
        self.assertIn("Monthly support", entry.detail)

    def test_coached_reflection_escalates_and_starts_cooldown(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.FLAGGED, risk_score=0.75,
            risk_tier=Transaction.RiskTier.HIGH, reflection_prompt="Why?",
        )
        result = services.submit_reflection(
            transaction, "He told me on the phone to send it right now"
        )
        self.assertEqual(result.risk_tier, Transaction.RiskTier.CRITICAL)
        self.assertEqual(result.risk_score, 0.98)
        self.assertIn("he told me", result.reflection_red_flags)
        self.assertGreater(result.cooldown_until, timezone.now())

    def test_existing_critical_risk_starts_cooldown_after_reflection(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Reported account", amount=85000,
            status=Transaction.Status.FLAGGED, risk_score=0.92,
            risk_tier=Transaction.RiskTier.CRITICAL, reflection_prompt="Why?",
        )
        result = services.submit_reflection(
            transaction, "This is payment for a new office chair"
        )
        self.assertEqual(result.reflection_red_flags, [])
        self.assertGreater(result.cooldown_until, timezone.now())

    def test_critical_transaction_cannot_be_self_approved(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.FLAGGED, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            reflection_submitted_at=timezone.now(),
            cooldown_until=timezone.now() + timedelta(seconds=20),
        )
        with self.assertRaisesMessage(ValueError, "cannot be self-approved"):
            services.apply_user_decision(transaction, "confirm")

    def test_critical_transaction_moves_to_independent_review(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.FLAGGED, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            reflection_submitted_at=timezone.now(),
            cooldown_until=timezone.now() + timedelta(seconds=20),
        )
        result = services.request_security_review(transaction)
        self.assertEqual(result.status, Transaction.Status.AWAITING_REVIEW)
        self.assertEqual(result.security_review.status, SecurityReview.Status.PENDING)
        self.assertTrue(
            LedgerEntry.objects.filter(
                transaction=transaction, event_type="security_review_requested"
            ).exists()
        )

    def test_reviewer_cannot_approve_before_safety_pause_expires(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.AWAITING_REVIEW, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            reflection_submitted_at=timezone.now(),
            cooldown_until=timezone.now() + timedelta(seconds=20),
        )
        SecurityReview.objects.create(
            transaction=transaction, requested_by_user_id=str(self.user.id)
        )
        with self.assertRaisesMessage(ValueError, "minimum safety pause"):
            services.decide_security_review(transaction, "reviewer-1", "approve")

    def test_sender_cannot_act_as_their_own_reviewer(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.AWAITING_REVIEW, risk_tier=Transaction.RiskTier.CRITICAL,
            cooldown_until=timezone.now() - timedelta(seconds=1),
        )
        SecurityReview.objects.create(
            transaction=transaction, requested_by_user_id=str(self.user.id)
        )
        with self.assertRaisesMessage(ValueError, "cannot review their own"):
            services.decide_security_review(
                transaction, str(self.user.id), "approve", "Self approval attempt"
            )

    def test_independent_reviewer_can_approve_after_pause(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.AWAITING_REVIEW, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            reflection_submitted_at=timezone.now(),
            cooldown_until=timezone.now() - timedelta(seconds=1),
        )
        SecurityReview.objects.create(
            transaction=transaction, requested_by_user_id=str(self.user.id)
        )
        result = services.decide_security_review(
            transaction, "reviewer-1", "approve", "Recipient independently verified"
        )
        self.assertEqual(result.status, Transaction.Status.REVIEW_APPROVED)
        result.security_review.refresh_from_db()
        self.assertEqual(result.security_review.status, SecurityReview.Status.APPROVED)
        self.assertEqual(result.security_review.reviewed_by_user_id, "reviewer-1")

    def test_independent_reviewer_can_block_immediately(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.AWAITING_REVIEW, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            cooldown_until=timezone.now() + timedelta(seconds=20),
        )
        SecurityReview.objects.create(
            transaction=transaction, requested_by_user_id=str(self.user.id)
        )
        result = services.decide_security_review(
            transaction, "reviewer-1", "block", "Recipient could not be verified"
        )
        self.assertEqual(result.status, Transaction.Status.BLOCKED)
        result.security_review.refresh_from_db()
        self.assertEqual(result.security_review.status, SecurityReview.Status.BLOCKED)

    def test_sender_can_cancel_while_review_is_pending(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.AWAITING_REVIEW, risk_tier=Transaction.RiskTier.CRITICAL,
        )
        review = SecurityReview.objects.create(
            transaction=transaction, requested_by_user_id=str(self.user.id)
        )
        result = services.apply_user_decision(transaction, "cancel")
        review.refresh_from_db()
        self.assertEqual(result.status, Transaction.Status.CANCELLED)
        self.assertEqual(review.status, SecurityReview.Status.CANCELLED)

    @patch("transactions.services._tier2_groq", return_value=None)
    @patch("transactions.services._tier1_local_pkl")
    def test_shared_reports_force_critical_risk(self, mock_tier1, _mock_groq):
        mock_tier1.return_value = {"risk_score": 0.2, "reason": "Personally routine"}
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="OPay - Demo", amount=85000,
            recipient_account_id="8091234567", recipient_bank="OPay",
        )
        result = services.score_transaction(transaction)
        self.assertEqual(result.status, Transaction.Status.FLAGGED)
        self.assertEqual(result.risk_tier, Transaction.RiskTier.CRITICAL)
        self.assertEqual(result.network_report_count, 3)
        self.assertGreaterEqual(result.risk_score, 0.92)

    def test_one_user_cannot_inflate_recipient_report_count(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Other", amount=10000,
            recipient_account_id="1111111111", recipient_bank="Kuda Bank",
        )
        _report, first_count, first_created = services.report_recipient(
            transaction, str(self.user.id), "coercion", "Pressed to hurry"
        )
        _report, second_count, second_created = services.report_recipient(
            transaction, str(self.user.id), "other", "Updated detail"
        )
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)
        self.assertEqual(RecipientReport.objects.filter(recipient_account_id="1111111111").count(), 1)


class TransactionAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_create_transaction_success(self):
        with patch("transactions.services._tier1_local_pkl") as mock_tier1:
            mock_tier1.return_value = {"risk_score": 0.2, "reason": "Low risk"}
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

    def test_reflection_and_report_endpoints(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            recipient_account_id="2222222222", recipient_bank="Opay",
            status=Transaction.Status.FLAGGED, risk_score=0.8,
            risk_tier=Transaction.RiskTier.HIGH, reflection_prompt="Why are you paying?",
        )
        reflection = self.client.post(
            f"/api/transactions/{transaction.id}/reflection/",
            {"answer": "Someone told me to transfer while on the phone"}, format="json",
        )
        self.assertEqual(reflection.status_code, status.HTTP_200_OK)
        self.assertEqual(reflection.data["risk_tier"], "critical")

        report = self.client.post(
            f"/api/transactions/{transaction.id}/report/",
            {"reason": "coercion", "detail": "Caller pressured me"}, format="json",
        )
        self.assertEqual(report.status_code, status.HTTP_201_CREATED)
        self.assertEqual(report.data["report_count"], 1)

    def test_security_review_requires_staff_for_decision(self):
        transaction = Transaction.objects.create(
            user_id=str(self.user.id), recipient="Unknown", amount=10000,
            status=Transaction.Status.FLAGGED, risk_score=0.98,
            risk_tier=Transaction.RiskTier.CRITICAL,
            reflection_submitted_at=timezone.now(),
            cooldown_until=timezone.now() - timedelta(seconds=1),
        )
        requested = self.client.post(
            f"/api/transactions/{transaction.id}/review-request/", {}, format="json"
        )
        self.assertEqual(requested.status_code, status.HTTP_201_CREATED)
        denied = self.client.post(
            f"/api/security-reviews/{transaction.id}/decision/",
            {"decision": "approve", "note": "Looks valid"}, format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        reviewer = User.objects.create_user(
            username="reviewer", password="testpass123", is_staff=True
        )
        self.client.force_authenticate(user=reviewer)
        queue = self.client.get("/api/security-reviews/")
        self.assertEqual(queue.status_code, status.HTTP_200_OK)
        self.assertEqual(len(queue.data), 1)
        approved = self.client.post(
            f"/api/security-reviews/{transaction.id}/decision/",
            {"decision": "approve", "note": "Recipient independently verified"},
            format="json",
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data["status"], Transaction.Status.REVIEW_APPROVED)
