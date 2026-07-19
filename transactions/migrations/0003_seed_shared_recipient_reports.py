from django.db import migrations


DEMO_ACCOUNT = "8091234567"
DEMO_REPORTERS = [
    ("seed-network-1", "impersonation", "Caller claimed to be a bank security officer."),
    ("seed-network-2", "coercion", "Recipient pressured me to transfer immediately."),
    ("seed-network-3", "investment", "Promised an unrealistic same-day investment return."),
]


def seed_reports(apps, schema_editor):
    RecipientReport = apps.get_model("transactions", "RecipientReport")
    for reporter, reason, detail in DEMO_REPORTERS:
        RecipientReport.objects.get_or_create(
            recipient_account_id=DEMO_ACCOUNT,
            reported_by_user_id=reporter,
            defaults={
                "recipient_bank": "OPay",
                "recipient_name": "Community Watch Demo",
                "reason": reason,
                "detail": detail,
            },
        )


def remove_seed_reports(apps, schema_editor):
    RecipientReport = apps.get_model("transactions", "RecipientReport")
    RecipientReport.objects.filter(
        recipient_account_id=DEMO_ACCOUNT,
        reported_by_user_id__in=[reporter for reporter, _reason, _detail in DEMO_REPORTERS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("transactions", "0002_transaction_cooldown_until_transaction_description_and_more")]

    operations = [migrations.RunPython(seed_reports, remove_seed_reports)]
