"""
Data models for the order/promo-code subsystem.

Domain overview
---------------
Category  – product category (used to restrict promo-codes to a subset of goods).
Good      – product with a price; may be marked as `promo_excluded` so that no
            discount ever applies to it.
PromoCode – a percentage-off voucher with optional expiry, usage cap and
            category restriction.
Order / OrderItem – a placed order with line-item detail.
PromoCodeUsage    – one row per (user, promo-code) pair to enforce the
                    "one use per user" rule.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=128, unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Good(models.Model):
    name = models.CharField(max_length=256)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="goods"
    )
    # Goods flagged here are excluded from every promotional discount.
    promo_excluded = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.name} ({self.price})"


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    discount = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001")), MaxValueValidator(Decimal("1"))],
        help_text="Fractional discount, e.g. 0.1 means 10 % off.",
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    max_usages = models.PositiveIntegerField(
        help_text="Maximum total number of times this code may be used."
    )
    # When set, the code applies only to goods in this category.
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promo_codes",
        help_text="If set, discount applies only to goods in this category.",
    )

    def __str__(self) -> str:
        return f"{self.code} ({self.discount * 100:.1f}%)"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    # Snapshot totals stored for quick reads and audit trail.
    price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Order #{self.pk} by user {self.user_id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    good = models.ForeignKey(Good, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Unit price at order time.")
    discount = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0"),
        help_text="Discount fraction applied to this line item."
    )
    total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self) -> str:
        return f"OrderItem {self.good_id} x{self.quantity} for Order #{self.order_id}"


class PromoCodeUsage(models.Model):
    """Tracks which users have already redeemed a given promo-code."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="promo_usages")
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="usages")
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "promo_code")]

    def __str__(self) -> str:
        return f"User {self.user_id} used {self.promo_code_id}"


class MailingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    SENT    = "sent",    "Sent"
    FAILED  = "failed",  "Failed"


class MailingRecord(models.Model):
    # Idempotency key: unique identifier in the external system.
    external_id = models.CharField(max_length=255, unique=True, db_index=True)

    user_id = models.PositiveIntegerField()
    email   = models.EmailField()
    subject = models.CharField(max_length=998)  # RFC 2822 subject line limit
    message = models.TextField()

    status     = models.CharField(
        max_length=10,
        choices=MailingStatus.choices,
        default=MailingStatus.PENDING,
        db_index=True,
    )
    error      = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Mailing Record"
        verbose_name_plural = "Mailing Records"

    def __str__(self) -> str:
        return f"[{self.status}] {self.external_id} → {self.email}"