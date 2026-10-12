
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("templates/", views.template_selection, name="template_selection"),
    path("create/", views.create_invoice, name="create_invoice"),
    path("<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path(
    "customer-lookup/",
    views.find_customer_by_mobile,
    name="customer_lookup",
),
    path(
    "edit/<int:invoice_id>/",
    views.edit_invoice,
    name="edit_invoice",
),
]
