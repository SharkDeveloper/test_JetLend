"""
Serializers for order creation with promo-code support.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Good, Order, OrderItem, PromoCode, PromoCodeUsage

User = get_user_model()


# ---------------------------------------------------------------------------
# Input serializers
# ---------------------------------------------------------------------------


class OrderItemInputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    goods = serializers.ListField(child=OrderItemInputSerializer(), min_length=1)
    promo_code = serializers.CharField(required=False, allow_blank=False, max_length=64)

    # ---- cross-field validation ----

    def validate_user_id(self, value: int) -> int:
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        goods_input: list[dict] = attrs["goods"]

        # Ensure all good_ids are unique in the request.
        good_ids = [item["good_id"] for item in goods_input]
        if len(good_ids) != len(set(good_ids)):
            raise serializers.ValidationError({"goods": "Duplicate good_id entries are not allowed."})

        # Fetch goods from DB in a single query.
        goods_qs = Good.objects.select_related("category").filter(pk__in=good_ids)
        goods_map: dict[int, Good] = {g.pk: g for g in goods_qs}

        missing = set(good_ids) - goods_map.keys()
        if missing:
            raise serializers.ValidationError({"goods": f"Goods not found: {sorted(missing)}"})

        attrs["_goods_map"] = goods_map

        # Validate promo-code if provided.
        raw_code: str | None = attrs.get("promo_code")
        if raw_code:
            attrs["_promo"] = self._validate_promo_code(raw_code, attrs["user_id"])

        return attrs

    def _validate_promo_code(self, code: str, user_id: int) -> PromoCode:
        now = timezone.now()

        try:
            promo = PromoCode.objects.select_related("category").get(code=code)
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError({"promo_code": "Promo code does not exist."})

        if not (promo.valid_from <= now <= promo.valid_until):
            raise serializers.ValidationError({"promo_code": "Promo code has expired or is not yet active."})

        if promo.usages.count() >= promo.max_usages:
            raise serializers.ValidationError({"promo_code": "Promo code usage limit has been reached."})

        if PromoCodeUsage.objects.filter(user_id=user_id, promo_code=promo).exists():
            raise serializers.ValidationError({"promo_code": "You have already used this promo code."})

        return promo


# ---------------------------------------------------------------------------
# Output serializers
# ---------------------------------------------------------------------------


class OrderItemOutputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField()
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=5, decimal_places=4)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class OrderOutputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    order_id = serializers.IntegerField(source="id")
    goods = OrderItemOutputSerializer(source="items", many=True)
    price = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount = serializers.DecimalField(max_digits=5, decimal_places=4)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
