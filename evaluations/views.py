from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """Evaluations placeholder."""
    return render(request, 'evaluations/index.html')
