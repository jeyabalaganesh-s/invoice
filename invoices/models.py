
from django.conf import settings
from django.db import models


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("finalized", "Finalized"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices",
    )

    invoice_number = models.CharField(max_length=50)
    seller_name = models.CharField(max_length=200)
    seller_address = models.TextField(blank=True)
    customer_name = models.CharField(max_length=200)
    customer_address = models.TextField(blank=True)
    customer_state = models.CharField(max_length=100, blank=True)

    
    seller_mobile = models.CharField(max_length=15, blank=True)
    customer_mobile = models.CharField(max_length=15, blank=True)

    GST_TYPE_CHOICES = [
        ("intra_state", "CGST + SGST (Intra-state)"),
        ("inter_state", "IGST (Inter-state)"),
    ]

    gst_type = models.CharField(
        max_length=20,
        choices=GST_TYPE_CHOICES,
        default="intra_state",
    )


    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    template = models.CharField(
        max_length=20,
        default="template_1",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "invoice_number"],
                name="unique_invoice_number_per_owner",
            )
        ]

    def __str__(self):
        return self.invoice_number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )

    description = models.CharField(max_length=250)

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    def __str__(self):
        return self.description



class Customer(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoice_customers",
    )
    mobile_number = models.CharField(max_length=15)
    name = models.CharField(max_length=150)
    address = models.TextField()
    state = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "mobile_number"],
                name="unique_customer_mobile_per_owner",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.mobile_number}"
