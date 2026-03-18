from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


@login_required
def dashboard(request):
    """Main dashboard — requires authentication."""
    return render(request, 'dashboard.html')


def health_check(request):
    """Health check endpoint for Docker / load balancers."""
    return JsonResponse({'status': 'ok'})
