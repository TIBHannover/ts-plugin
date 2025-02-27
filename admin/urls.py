
from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('is_entity_admin/', csrf_exempt(views.is_entity_admin), name="is_entity_admin"),
    path('is_system_admin/', csrf_exempt(views.is_system_admin), name="is_system_admin"),
]
