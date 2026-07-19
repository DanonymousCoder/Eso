import math
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import PaymentProfile


MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15
DISALLOWED_PINS = {
    "0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777",
    "8888", "9999", "1234", "4321",
}


class PaymentPinError(ValueError):
    pass


def validate_pin_format(pin: str) -> str:
    value = str(pin or "").strip()
    if len(value) != 4 or not value.isdigit():
        raise PaymentPinError("Your payment PIN must contain exactly four digits.")
    if value in DISALLOWED_PINS:
        raise PaymentPinError("Choose a less predictable payment PIN.")
    return value


def get_payment_profile(user) -> PaymentProfile:
    profile, _created = PaymentProfile.objects.get_or_create(user=user)
    return profile


def payment_pin_status(user) -> dict:
    profile = get_payment_profile(user)
    now = timezone.now()
    is_locked = bool(profile.locked_until and profile.locked_until > now)
    return {
        "has_pin": profile.has_pin,
        "is_locked": is_locked,
        "locked_until": profile.locked_until if is_locked else None,
        "attempts_remaining": max(0, MAX_PIN_ATTEMPTS - profile.failed_attempts),
    }


@transaction.atomic
def set_payment_pin(user, current_password: str, pin: str) -> PaymentProfile:
    if not user.check_password(current_password):
        raise PaymentPinError("Your account password is incorrect.")
    value = validate_pin_format(pin)
    profile = PaymentProfile.objects.select_for_update().filter(user=user).first()
    if profile is None:
        profile = PaymentProfile(user=user)
    profile.pin_hash = make_password(value)
    profile.failed_attempts = 0
    profile.locked_until = None
    profile.save()
    return profile


def verify_payment_pin(user, pin: str) -> None:
    error_message = None
    with transaction.atomic():
        profile = PaymentProfile.objects.select_for_update().filter(user=user).first()
        if profile is None or not profile.has_pin:
            raise PaymentPinError("Set a payment PIN in Settings before making a transfer.")

        now = timezone.now()
        if profile.locked_until and profile.locked_until > now:
            remaining = math.ceil((profile.locked_until - now).total_seconds() / 60)
            raise PaymentPinError(
                f"Payment authorization is temporarily locked. Try again in {remaining} minute"
                f"{'s' if remaining != 1 else ''}."
            )

        if not check_password(str(pin or ""), profile.pin_hash):
            profile.failed_attempts += 1
            if profile.failed_attempts >= MAX_PIN_ATTEMPTS:
                profile.locked_until = now + timedelta(minutes=PIN_LOCK_MINUTES)
                profile.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
                error_message = (
                    "Too many incorrect attempts. Payment authorization is locked for 15 minutes."
                )
            else:
                profile.save(update_fields=["failed_attempts", "updated_at"])
                attempts = MAX_PIN_ATTEMPTS - profile.failed_attempts
                error_message = (
                    f"Incorrect payment PIN. {attempts} "
                    f"attempt{'s' if attempts != 1 else ''} remaining."
                )
        elif profile.failed_attempts or profile.locked_until:
            profile.failed_attempts = 0
            profile.locked_until = None
            profile.save(update_fields=["failed_attempts", "locked_until", "updated_at"])

    if error_message:
        raise PaymentPinError(error_message)
