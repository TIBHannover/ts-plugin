from .search_agent.urls import urlpatterns as search_urlpatterns
from .term_request_assist.urls import urlpatterns as term_request_urlpatterns

urlpatterns = [
    term_request_urlpatterns[0],
    search_urlpatterns[0],
    *term_request_urlpatterns[1:],
]
