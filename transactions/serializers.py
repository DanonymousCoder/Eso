from rest_framework import serializers
from .models import (
    Transaction,
    BehaviorBaseline,
    LedgerEntry,
    RecipientReport,
    SecurityReview,
)


class BehaviorBaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BehaviorBaseline
        fields = [
            "user_id",
            "typical_recipients",
            "typical_amount_min",
            "typical_amount_max",
            "typical_hours",
            "known_devices",
            "updated_at",
        ]


class TransactionCreateSerializer(serializers.ModelSerializer):
    """
    What the frontend sends when a user initiates a transfer.
    user_id is deliberately NOT accepted from the client — it's set server-side
    from the authenticated request user in the view. Otherwise anyone with a
    valid token could submit transactions under someone else's user_id.
    """

    payment_pin = serializers.RegexField(regex=r"^\d{4}$", write_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "recipient",
            "recipient_account_id",
            "recipient_bank",
            "amount",
            "description",
            "device_id",
            "payment_pin",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data.pop("payment_pin", None)
        return super().create(validated_data)


class SecurityReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityReview
        fields = [
            "id",
            "status",
            "reviewer_note",
            "requested_at",
            "reviewed_at",
        ]
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    """Full transaction state, including scoring outcome — used in responses."""

    security_review = SecurityReviewSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "user_id",
            "recipient",
            "recipient_account_id",
            "recipient_bank",
            "amount",
            "description",
            "device_id",
            "status",
            "risk_score",
            "risk_tier",
            "risk_reason",
            "network_report_count",
            "reflection_prompt",
            "reflection_answer",
            "reflection_red_flags",
            "reflection_submitted_at",
            "cooldown_until",
            "security_review",
            "created_at",
            "scored_at",
            "decided_at",
        ]
        read_only_fields = fields


class TransactionDecisionSerializer(serializers.Serializer):
    """What the frontend sends when the user responds to a flagged transaction."""

    decision = serializers.ChoiceField(choices=["confirm", "cancel"])


class SecurityReviewDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "block"])
    note = serializers.CharField(trim_whitespace=True, min_length=10, max_length=1000)


class ReflectionAnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(trim_whitespace=True, max_length=1000)


class RecipientReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipientReport
        fields = ["reason", "detail"]


class RecipientReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipientReport
        fields = [
            "id",
            "recipient_account_id",
            "recipient_bank",
            "recipient_name",
            "reason",
            "detail",
            "created_at",
        ]
        read_only_fields = fields


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "transaction", "event_type", "detail", "created_at"]
