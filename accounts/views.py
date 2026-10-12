
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = AuthenticationForm(
        request=request,
        data=request.POST or None,
    )

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())

        next_url = request.POST.get("next") or request.GET.get("next")

        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)

        return redirect("dashboard")

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
        },
    )


def logout_view(request):
    if request.method == "POST":
        logout(request)

    return redirect("login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")

    return render(
        request,
        "accounts/register.html",
        {"form": form},
    )
