from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAdminUser
from accounts import services as account_services

from .models import Transaction, LedgerEntry
from .serializers import (
    TransactionCreateSerializer,
    TransactionSerializer,
    TransactionDecisionSerializer,
    LedgerEntrySerializer,
    BehaviorBaselineSerializer,
    ReflectionAnswerSerializer,
    RecipientReportCreateSerializer,
    RecipientReportSerializer,
    SecurityReviewDecisionSerializer,
)
from . import services


class BaselineView(APIView):
    """GET /api/me/baseline/ — the current authenticated user's baseline."""

    def get(self, request):
        baseline = services.get_or_create_baseline(str(request.user.id))
        return Response(BehaviorBaselineSerializer(baseline).data)


class TransactionCreateView(APIView):
    """
    POST /api/transactions/

    Creates a transaction AND scores it in one call. Collapsing "submit"
    and "score" into a single route keeps the demo flow simpler — the
    frontend doesn't need two sequential requests before it can show a
    result. user_id comes from the authenticated token, never from the
    request body.
    """

    def post(self, request):
        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            account_services.verify_payment_pin(
                request.user, serializer.validated_data["payment_pin"]
            )
        except account_services.PaymentPinError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        transaction = serializer.save(user_id=str(request.user.id))

        transaction = services.score_transaction(transaction)

        return Response(
            TransactionSerializer(transaction).data,
            status=status.HTTP_201_CREATED,
        )


class TransactionDetailView(APIView):
    """GET /api/transactions/<id>/"""

    def get(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        _assert_owns(request, transaction)
        return Response(TransactionSerializer(transaction).data)


class TransactionDecisionView(APIView):
    """
    POST /api/transactions/<id>/decision/
    Body: {"decision": "confirm" | "cancel"}
    """

    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        _assert_owns(request, transaction)
        serializer = TransactionDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transaction = services.apply_user_decision(
                transaction, serializer.validated_data["decision"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TransactionSerializer(transaction).data)


class TransactionReflectionView(APIView):
    """POST /api/transactions/<id>/reflection/ — required step-up response."""

    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        _assert_owns(request, transaction)
        serializer = ReflectionAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            transaction = services.submit_reflection(
                transaction, serializer.validated_data["answer"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TransactionSerializer(transaction).data)


class TransactionRecipientReportView(APIView):
    """POST /api/transactions/<id>/report/ — feeds the shared recipient registry."""

    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        _assert_owns(request, transaction)
        serializer = RecipientReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            report, report_count, created = services.report_recipient(
                transaction=transaction,
                reported_by_user_id=str(request.user.id),
                reason=serializer.validated_data["reason"],
                detail=serializer.validated_data.get("detail", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "report": RecipientReportSerializer(report).data,
                "report_count": report_count,
                "created": created,
                "transaction": TransactionSerializer(transaction).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TransactionSecurityReviewRequestView(APIView):
    """POST — move a critical transaction into a non-self-releasable hold."""

    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        _assert_owns(request, transaction)
        try:
            transaction = services.request_security_review(transaction)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransactionSerializer(transaction).data, status=status.HTTP_201_CREATED)


class SecurityReviewQueueView(APIView):
    """GET — staff-only queue of critical transfers awaiting a decision."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        transactions = Transaction.objects.filter(
            status=Transaction.Status.AWAITING_REVIEW
        ).select_related("security_review")
        return Response(TransactionSerializer(transactions, many=True).data)


class SecurityReviewDecisionView(APIView):
    """POST — staff-only independent approve/block decision."""

    permission_classes = [IsAdminUser]

    def post(self, request, transaction_id):
        transaction = get_object_or_404(Transaction, id=transaction_id)
        serializer = SecurityReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transaction = services.decide_security_review(
                transaction=transaction,
                reviewer_user_id=str(request.user.id),
                decision=serializer.validated_data["decision"],
                note=serializer.validated_data.get("note", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TransactionSerializer(transaction).data)


class LedgerView(APIView):
    """GET /api/me/ledger/ — the current authenticated user's transparency log."""

    def get(self, request):
        entries = LedgerEntry.objects.filter(user_id=str(request.user.id))
        return Response(LedgerEntrySerializer(entries, many=True).data)


def _assert_owns(request, transaction: Transaction):
    """A user can only view/decide on their own transactions."""
    if transaction.user_id != str(request.user.id):
        raise PermissionDenied("This transaction does not belong to you.")
