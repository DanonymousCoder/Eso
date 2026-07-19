from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff"]


class PaymentPinSetSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    pin = serializers.RegexField(regex=r"^\d{4}$", write_only=True)
    pin_confirmation = serializers.RegexField(regex=r"^\d{4}$", write_only=True)

    def validate(self, attrs):
        if attrs["pin"] != attrs["pin_confirmation"]:
            raise serializers.ValidationError({"pin_confirmation": "The payment PINs do not match."})
        return attrs
