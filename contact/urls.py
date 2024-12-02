from django.urls import path
from . import views

urlpatterns = [
    path('ping/', views.ping, name="ping"),
    path('create/', views.create, name="create"),
]
