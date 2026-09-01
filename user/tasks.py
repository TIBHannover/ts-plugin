from celery import shared_task
from django.utils import timezone

from user.models import OAuthLoginTransaction


@shared_task
def cleanup_expired_oauth_login_transactions():
    OAuthLoginTransaction.objects.filter(expires_at__lt=timezone.now()).delete()
