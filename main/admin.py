"""
Django admin registrations — useful for manual inspection during development.
"""

from django.contrib import admin

from .models import Category, Good, Order, OrderItem, PromoCode, PromoCodeUsage


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("good", "quantity", "price", "discount", "total")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "promo_code", "price", "discount", "total", "created_at")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount", "valid_from", "valid_until", "max_usages", "category")


@admin.register(Good)
class GoodAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "category", "promo_excluded")


admin.site.register(Category)
admin.site.register(PromoCodeUsage)
