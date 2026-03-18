from django.urls import path
from . import views

app_name = 'evaluations'

urlpatterns = [
    path('', views.index, name='index'),
]
