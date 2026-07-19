from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from .models import PaymentProfile
from . import services


class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/auth/register/"

    def test_register_success(self):
        data = {"username": "testuser", "email": "test@example.com", "password": "testpass123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "testuser")

    def test_register_duplicate_username(self):
        User.objects.create_user(username="testuser", password="testpass123")
        data = {"username": "testuser", "email": "test@example.com", "password": "testpass123"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password(self):
        data = {"username": "testuser", "password": "short"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_fields(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/auth/me/"
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")

    def test_me_unauthenticated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PaymentPinTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="pinuser", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_pin_status_starts_unset(self):
        response = self.client.get("/api/auth/payment-pin/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["has_pin"])

    def test_set_pin_stores_hash_not_raw_value(self):
        response = self.client.post(
            "/api/auth/payment-pin/",
            {
                "current_password": "testpass123",
                "pin": "2580",
                "pin_confirmation": "2580",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = PaymentProfile.objects.get(user=self.user)
        self.assertNotEqual(profile.pin_hash, "2580")
        self.assertTrue(response.data["has_pin"])

    def test_set_pin_requires_account_password(self):
        response = self.client.post(
            "/api/auth/payment-pin/",
            {
                "current_password": "wrong-password",
                "pin": "2580",
                "pin_confirmation": "2580",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_predictable_pin_is_rejected(self):
        with self.assertRaisesMessage(services.PaymentPinError, "less predictable"):
            services.set_payment_pin(self.user, "testpass123", "1234")

    def test_five_wrong_attempts_lock_payment_authorization(self):
        services.set_payment_pin(self.user, "testpass123", "2580")
        for _attempt in range(4):
            with self.assertRaises(services.PaymentPinError):
                services.verify_payment_pin(self.user, "2581")
        with self.assertRaisesMessage(services.PaymentPinError, "locked for 15 minutes"):
            services.verify_payment_pin(self.user, "2581")
        status_data = services.payment_pin_status(self.user)
        self.assertTrue(status_data["is_locked"])
