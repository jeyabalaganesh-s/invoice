
from django.contrib import admin
from .models import Invoice, InvoiceItem, Customer


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "customer_name",
        "seller_name",
        "status",
        "created_at",
    )

    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "customer_name")
    inlines = [InvoiceItemInline]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "invoice",
        "quantity",
        "unit_price",
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "mobile_number",
        "address",
        "state",
        "owner",
    )

    search_fields = ("name", "mobile_number")
    list_filter = ("state",)
