
from django.urls import path
from . import views

urlpatterns = [
    path('ping/', views.ping, name="ping"),
    path('create/', views.create, name="create"),
    path('get/<int:collection_id>/', views.get, name="get"),
    path('get_list/', views.get_list, name="get_list"),
    path('update/<string:collection_id>/', views.update, name="update"),
    path('delete/<string:collection_id>/', views.delete, name="delete"),
]
