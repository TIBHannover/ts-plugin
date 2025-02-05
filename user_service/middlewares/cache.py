from django.utils.cache import patch_cache_control

class DisableCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        patch_cache_control(response, no_cache=True, no_store=True, must_revalidate=True)
        return response
