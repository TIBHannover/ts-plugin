from .search_agent.urls import urlpatterns as search_urlpatterns
from .term_request_assist.urls import urlpatterns as term_request_urlpatterns
from .annotator_assist.urls import urlpatterns as annotator_urlpatterns

urlpatterns = [
    term_request_urlpatterns[0],
    search_urlpatterns[0],
    *annotator_urlpatterns,
    *term_request_urlpatterns[1:],
]
