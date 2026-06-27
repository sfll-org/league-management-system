from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm


def login_view(request):
    """Email/password login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login(request, form.user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Log out and redirect to login page."""
    logout(request)
    return redirect('accounts:login')
