from django.urls import path
from .views import assistant_page, invoice_assistant

urlpatterns = [
    path("", assistant_page, name="assistant_page"),
    path(
        "invoice-assistant/",
        invoice_assistant,
        name="invoice_assistant",
    ),
]