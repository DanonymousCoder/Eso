from django.urls import path
from . import views

urlpatterns = [
    path("me/baseline/", views.BaselineView.as_view()),
    path("me/ledger/", views.LedgerView.as_view()),
    path("transactions/", views.TransactionCreateView.as_view()),
    path("transactions/<uuid:transaction_id>/", views.TransactionDetailView.as_view()),
    path("transactions/<uuid:transaction_id>/reflection/", views.TransactionReflectionView.as_view()),
    path("transactions/<uuid:transaction_id>/report/", views.TransactionRecipientReportView.as_view()),
    path("transactions/<uuid:transaction_id>/review-request/", views.TransactionSecurityReviewRequestView.as_view()),
    path("transactions/<uuid:transaction_id>/decision/", views.TransactionDecisionView.as_view()),
    path("security-reviews/", views.SecurityReviewQueueView.as_view()),
    path("security-reviews/<uuid:transaction_id>/decision/", views.SecurityReviewDecisionView.as_view()),
]
