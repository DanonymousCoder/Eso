import uuid
from django.db import models


class BehaviorBaseline(models.Model):
    """
    A user's learned 'normal' — typical recipients, amount range, timing.
    Updated automatically when transfers are approved or user-confirmed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, unique=True)
    typical_recipients = models.JSONField(default=list)  # list of recipient ids/names
    typical_amount_min = models.DecimalField(max_digits=14, decimal_places=2)
    typical_amount_max = models.DecimalField(max_digits=14, decimal_places=2)
    typical_hours = models.JSONField(default=list)  # e.g. [8,9,10,...,21]
    known_devices = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Baseline for {self.user_id}"


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        FLAGGED = "flagged", "Flagged"
        AWAITING_REVIEW = "awaiting_review", "Awaiting security review"
        REVIEW_APPROVED = "review_approved", "Approved by security review"
        BLOCKED = "blocked", "Blocked by security review"
        CANCELLED = "cancelled", "Cancelled"
        CONFIRMED = "confirmed", "Confirmed after flag"

    class RiskTier(models.TextChoices):
        LOW = "low", "Low"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)
    recipient = models.CharField(max_length=150)
    recipient_account_id = models.CharField(max_length=30, blank=True, db_index=True)
    recipient_bank = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=240, blank=True)
    device_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    risk_score = models.FloatField(null=True, blank=True)
    risk_tier = models.CharField(
        max_length=20, choices=RiskTier.choices, default=RiskTier.LOW
    )
    risk_reason = models.TextField(blank=True)  # plain-language explanation
    network_report_count = models.PositiveIntegerField(default=0)
    reflection_prompt = models.CharField(max_length=240, blank=True)
    reflection_answer = models.TextField(blank=True)
    reflection_red_flags = models.JSONField(default=list, blank=True)
    reflection_submitted_at = models.DateTimeField(null=True, blank=True)
    cooldown_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    scored_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user_id} -> {self.recipient} ({self.amount})"


class RecipientReport(models.Model):
    """A shared fraud signal keyed to a beneficiary bank account."""

    class Reason(models.TextChoices):
        IMPERSONATION = "impersonation", "Impersonation"
        INVESTMENT = "investment", "Investment scam"
        ROMANCE = "romance", "Romance scam"
        PURCHASE = "purchase", "Goods or services scam"
        COERCION = "coercion", "Pressure or coercion"
        OTHER = "other", "Other suspicious activity"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_account_id = models.CharField(max_length=30, db_index=True)
    recipient_bank = models.CharField(max_length=100, blank=True)
    recipient_name = models.CharField(max_length=150, blank=True)
    reported_by_user_id = models.CharField(max_length=100, db_index=True)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        related_name="recipient_reports",
        null=True,
        blank=True,
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient_account_id", "reported_by_user_id"],
                name="one_recipient_report_per_user",
            )
        ]

    def __str__(self):
        return f"{self.recipient_account_id} reported by {self.reported_by_user_id}"


class SecurityReview(models.Model):
    """Independent release decision for a critical-risk transaction."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        BLOCKED = "blocked", "Blocked"
        CANCELLED = "cancelled", "Cancelled by sender"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="security_review"
    )
    requested_by_user_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reviewer_note = models.TextField(blank=True)
    reviewed_by_user_id = models.CharField(max_length=100, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Review for {self.transaction_id}: {self.status}"


class LedgerEntry(models.Model):
    """
    Append-only transparency log. Every score, flag, and user decision
    gets written here so it can be rendered in the activity/trust log UI.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    event_type = models.CharField(max_length=50)  # e.g. "scored", "flagged", "overridden"
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} @ {self.created_at}"
