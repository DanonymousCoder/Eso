from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserSerializer, PaymentPinSetSerializer
from . import services


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Body: {"username": "...", "email": "...", "password": "..."}
    Returns access + refresh tokens so the frontend can log the user
    straight in after registering, no separate login call needed.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """GET /api/auth/me/ — confirms who the current token belongs to."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PaymentPinView(APIView):
    """GET PIN status; POST creates or changes a PIN after password confirmation."""

    def get(self, request):
        return Response(services.payment_pin_status(request.user))

    def post(self, request):
        serializer = PaymentPinSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.set_payment_pin(
                user=request.user,
                current_password=serializer.validated_data["current_password"],
                pin=serializer.validated_data["pin"],
            )
        except services.PaymentPinError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.payment_pin_status(request.user))
