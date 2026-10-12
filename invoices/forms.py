
from django import forms
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    discount = forms.DecimalField(
        required=False,
        initial=0,
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )
    template = forms.ChoiceField(
        choices=[
            ("template_1", "Template 1 - Classic Professional"),
            ("template_2", "Template 2 - Luxury"),
            ("template_3", "Template 3 - Modern Corporate"),
            ("template_4", "Template 4 - Creative Freelancer"),
        ],
        widget=forms.Select(attrs={"id": "id_template"}),
        label="Invoice Design",
    )

    class Meta:
        model = Invoice
        fields = [
            "invoice_number",
            "seller_name",
            "seller_address",
            "seller_mobile",
            "customer_name",
            "customer_address",
            "customer_mobile",
            "customer_state",
            "invoice_date",
            "due_date",
            "discount",
            "gst_type",
            "template",
            "notes",
        ]

        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "seller_address": forms.Textarea(attrs={"rows": 2}),
            "customer_address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }



class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = [
            "description",
            "quantity",
            "unit_price",
            "tax_rate",
        ]

    def clean(self):
        cleaned_data = super().clean()

        # Allow a row marked for deletion to have empty fields.
        if cleaned_data.get("DELETE"):
            return cleaned_data

        return cleaned_data


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
)
