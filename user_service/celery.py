import os
from celery import Celery as CeleryApp

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_service.settings")

app = CeleryApp("user_service")
app.set_default()
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
