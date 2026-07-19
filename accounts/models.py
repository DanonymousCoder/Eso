from django.contrib.auth.models import User
from django.db import models


class PaymentProfile(models.Model):
    """Payment authorization state; the raw PIN is never stored."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="payment_profile"
    )
    pin_hash = models.CharField(max_length=128, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_pin(self):
        return bool(self.pin_hash)

    def __str__(self):
        return f"Payment profile for {self.user.username}"
