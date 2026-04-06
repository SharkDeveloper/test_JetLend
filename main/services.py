"""
Business-logic layer for order creation.

Keeping this separate from the view and serializer layers keeps each piece
small and independently testable.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from .models import Good, Order, OrderItem, PromoCode, PromoCodeUsage


def _round(value: Decimal) -> Decimal:
    """Round monetary value to 2 decimal places."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _item_discount(good: Good, promo: PromoCode | None) -> Decimal:
    """
    Return the discount fraction for a single good.

    Rules (in order of precedence):
    1. If the good is promo-excluded → no discount.
    2. If the promo is restricted to a category and the good's category
       doesn't match → no discount.
    3. Otherwise apply the promo discount.
    """
    if promo is None:
        return Decimal("0")
    if good.promo_excluded:
        return Decimal("0")
    if promo.category_id is not None and good.category_id != promo.category_id:
        return Decimal("0")
    return promo.discount


@transaction.atomic
def create_order(
    user_id: int,
    goods_input: list[dict],
    goods_map: dict[int, Good],
    promo: PromoCode | None,
) -> Order:
    """
    Create and persist an Order with its line items.

    The entire operation runs inside a single DB transaction so that a
    concurrent request cannot sneak in a duplicate promo-code usage between
    our validation and the INSERT.  We use select_for_update on the promo-code
    usage count to make this race-condition-safe.

    Returns the saved Order instance (with prefetched items).
    """
    # Re-check usage count inside the transaction with a row lock to prevent
    # race conditions when two requests try to use the last available slot.
    if promo is not None:
        locked_usage_count = (
            PromoCodeUsage.objects.select_for_update()
            .filter(promo_code=promo)
            .count()
        )
        if locked_usage_count >= promo.max_usages:
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError(
                {"promo_code": "Promo code usage limit has been reached."}
            )

    # Build line items and aggregate totals.
    items: list[OrderItem] = []
    order_price = Decimal("0")
    order_total = Decimal("0")

    for entry in goods_input:
        good: Good = goods_map[entry["good_id"]]
        qty: int = entry["quantity"]
        discount_fraction = _item_discount(good, promo)

        line_price = good.price * qty
        line_total = _round(line_price * (1 - discount_fraction))

        order_price += line_price
        order_total += line_total

        items.append(
            OrderItem(
                good=good,
                quantity=qty,
                price=good.price,
                discount=discount_fraction,
                total=line_total,
            )
        )

    order_price = _round(order_price)
    order_total = _round(order_total)

    # Compute the effective overall discount fraction for the order snapshot.
    # If price is zero (edge case with free goods) avoid division by zero.
    if order_price > 0:
        effective_discount = ((order_price - order_total) / order_price).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
    else:
        effective_discount = Decimal("0")

    # Persist the order.
    order = Order.objects.create(
        user_id=user_id,
        promo_code=promo,
        price=order_price,
        discount=effective_discount,
        total=order_total,
    )

    # Bulk-insert line items.
    for item in items:
        item.order = order
    OrderItem.objects.bulk_create(items)

    # Record promo usage.
    if promo is not None:
        PromoCodeUsage.objects.create(user_id=user_id, promo_code=promo)

    # Return a fresh instance with prefetched items for serialization.
    return Order.objects.prefetch_related("items__good").get(pk=order.pk)
