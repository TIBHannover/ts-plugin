from django.conf import settings


def debug_auth(message):
    if settings.DEBUG:
        print(f"[auth] {message}", flush=True)
