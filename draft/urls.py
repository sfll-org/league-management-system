from django.urls import path
from . import views

app_name = 'draft'

urlpatterns = [
    path('', views.index, name='index'),
]
