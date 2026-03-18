from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """Tryout sessions placeholder."""
    return render(request, 'tryouts/index.html')
