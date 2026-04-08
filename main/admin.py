"""
Django admin registrations — useful for manual inspection during development.
"""

from django.contrib import admin

from .models import Category, Good, Order, OrderItem, PromoCode, PromoCodeUsage, MailingRecord, MailingStatus


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


@admin.register(MailingRecord)
class MailingRecordAdmin(admin.ModelAdmin):
    list_display  = ("id", "external_id", "user_id", "email", "subject", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("external_id", "email", "user_id")
    readonly_fields = ("created_at", "updated_at", "error")
    ordering       = ("-created_at",)

admin.site.register(Category)
admin.site.register(PromoCodeUsage)
