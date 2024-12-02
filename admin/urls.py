
from django.urls import path
from . import views

urlpatterns = [
    path('is_entity_admin/', views.is_entity_admin, name="is_entity_admin"),
    path('is_system_admin/', views.is_system_admin, name="is_system_admin"),
]
