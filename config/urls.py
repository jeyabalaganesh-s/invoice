from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("invoices/", include("invoices.urls")),
    path("ai/", include("ai_agent.urls")),
]