
from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('ping/', views.ping, name="ping"),
    path('create/', csrf_exempt(views.create), name="create"),
    path('get/<int:collection_id>/', views.get, name="get"),
    path('get_list/', views.get_list, name="get_list"),
    path('update/<int:collection_id>/', csrf_exempt(views.update), name="update"),
    path('delete/<int:collection_id>/', csrf_exempt(views.delete), name="delete"),
    path('bioregistry_collections/', views.get_bioregistry_collections, name="bioregistry_collections")
]
