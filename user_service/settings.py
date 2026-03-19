from pathlib import Path
import environ
import os
from corsheaders.defaults import default_methods
from corsheaders.defaults import default_headers

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


env = environ.Env()
environ.Env.read_env()

SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG_MODE", default=False)


ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".service.tib.eu",
    ".terminilogy.nfdi4chem.de",
    ".terminilogy.nfdi4ing.de",
    ".terminilogy.tib.eu",
]
FORCE_SCRIPT_NAME = env("SUB_PATH", default="")
AUTH_PROVIDERS = ["github", "orcid", "gitlab", "native", "apikey"]
CLIENT_TERMINOLOGY_SERVICES = ["general", "nfdi4chem", "nfdi4ing"]

CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost",
    "http://127.0.0.1:3000",
    "http://ols02.develop.service.tib.eu",
    "https://terminology.nfdi4chem.de",
    "https://terminology.nfdi4ing.de",
    "https://terminology.tib.eu",
    "http://ols03.develop.service.tib.eu",
    "https://service.tib.eu",
]

CSRF_TRUSTED_ORIGINS = [
    "https://service.tib.eu",
    "http://localhost:3000",
    "http://localhost",
    "https://terminology.nfdi4chem.de",
    "https://terminology.nfdi4ing.de",
    "https://terminology.tib.eu",
]

CORS_ALLOW_METHODS = (*default_methods,)

CORS_ALLOW_HEADERS = (
    *default_headers,
    "Authorization",
    "X-TS-Frontend-Id",
    "X-TS-Frontend-Token",
    "X-TS-Auth-Provider",
    "X-TS-Auth-APP-Code",
    "X-TS-Orcid-Id",
    "X-TS-User-Token",
    "X-TS-User-Name",
    "X-CSRF-Token",
    "X-Auth-Token",
)


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "drf_yasg",
    "corsheaders",
    "user",
    "report",
    "ontology_suggestion",
    "note",
    "github",
    "contact",
    "collection",
    "admin.apps.AdminConfig",
    "admin_cli",
    "term_set",
    "ts",
    "django_celery_beat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "user_service.middlewares.client_id.ClientIdMiddleware",
    "user_service.middlewares.request.RequestMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "user_service.middlewares.cache.DisableCacheMiddleware",
]

ROOT_URLCONF = "user_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "user_service.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

SWAGGER_SETTINGS = {"USE_SESSION_AUTH": False}


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/ts-plugin/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")


CELERY_BROKER_URL="redis://redis:6379/0"
CELERY_RESULT_BACKEND="redis://redis:6379/0"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


SUB_PATH = env("SUB_PATH", default="")
GITHUB_TS_USER_API_TOKEN = env("GITHUB_TS_USER_API_TOKEN", default=None)
GITLAB_TS_USER_API_TOKEN = env("GITLAB_TS_USER_API_TOKEN", default=None)
CONTACT_REQUEST_RECEIVER_REPO = env("CONTACT_REQUEST_RECEIVER_REPO", default=None)
GITLAB_API_BASE_URL = env("GITLAB_API_BASE_URL", default=None)
ONTOLOGY_SUGGESTION_REPO = env("ONTOLOGY_SUGGESTION_REPO", default=None)
ONTOLOGY_SHAPE_TEST_URL = env("ONTOLOGY_SHAPE_TEST_URL", default=None)
NFDI4CHEM_GITLAB_ADMIN_IDS = env("NFDI4CHEM_GITLAB_ADMIN_IDS", default=None)
SYSTEM_EMAIL = env("SYSTEM_EMAIL", default=None)
EMAIL_SERVER_HOST = env("EMAIL_SERVER_HOST", default=None)
EMAIL_SERVER_PORT = env("EMAIL_SERVER_PORT", default=None)
# CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="erthrt")
# CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=None)
DEFAULT_FRONTEND_REDIRECT_URL = env("DEFAULT_FRONTEND_REDIRECT_URL", default=None)
DEFAULT_GITHUB_CLIENT_ID = env("DEFAULT_GITHUB_CLIENT_ID", default=None)
DEFAULT_GITHUB_CLIENT_SECRET = env("DEFAULT_GITHUB_CLIENT_SECRET", default=None)
GENERAL_FRONTEND_REDIRECT_URL = env("GENERAL_FRONTEND_REDIRECT_URL", default=None)
GENERAL_GITHUB_CLIENT_ID = env("GENERAL_GITHUB_CLIENT_ID", default=None)
GENERAL_GITHUB_CLIENT_SECRET = env("GENERAL_GITHUB_CLIENT_SECRET", default=None)
NFDI4CHEM_FRONTEND_REDIRECT_URL = env("NFDI4CHEM_FRONTEND_REDIRECT_URL", default=None)
NFDI4CHEM_GITHUB_CLIENT_ID = env("NFDI4CHEM_GITHUB_CLIENT_ID", default=None)
NFDI4CHEM_GITHUB_CLIENT_SECRET = env("NFDI4CHEM_GITHUB_CLIENT_SECRET", default=None)
NFDI4ING_FRONTEND_REDIRECT_URL = env("NFDI4ING_FRONTEND_REDIRECT_URL", default=None)
NFDI4ING_GITHUB_CLIENT_ID = env("NFDI4ING_GITHUB_CLIENT_ID", default=None)
NFDI4ING_GITHUB_CLIENT_SECRET = env("NFDI4ING_GITHUB_CLIENT_SECRET", default=None)
GITHUB_TOKEN_URL = env("GITHUB_TOKEN_URL", default=None)
GITHUB_USER_URL = env("GITHUB_USER_URL", default=None)
GITHUB_REPOS_URL = env("GITHUB_REPOS_URL", default=None)
ORCID_CLIENT_ID = env("ORCID_CLIENT_ID", default=None)
ORCID_CLIENT_SECRET = env("ORCID_CLIENT_SECRET", default=None)
ORCID_TOKEN_URL = env("ORCID_TOKEN_URL", default=None)
ORCID_READ_RECORD_BASE_URL = env("ORCID_READ_RECORD_BASE_URL", default=None)
GITLAB_CLIENT_ID = env("GITLAB_CLIENT_ID", default=None)
GITLAB_CLIENT_SECRET = env("GITLAB_CLIENT_SECRET", default=None)
GITLAB_TOKEN_URL = env("GITLAB_TOKEN_URL", default=None)
GITLAB_USER_URL = env("GITLAB_USER_URL", default=None)
AAI_CLIENT_SECRET = env("AAI_CLIENT_SECRET", default=None)
AAI_CLIENT_ID = env("AAI_CLIENT_ID", default=None)
AAI_TOKEN_URL = env("AAI_TOKEN_URL", default=None)
AAI_USER_URL = env("AAI_USER_URL", default=None)
OLS_API_BASE_URL = env("OLS_API_BASE_URL", default=None)
MAX_PIN_NOTES = env("MAX_PIN_NOTES", default=None)
TIB_GENERAL_FRONTEND_ADDRESS = env("TIB_GENERAL_FRONTEND_ADDRESS", default=None)
NFDI4CHEM_FRONTEND_ADDRESS = env("NFDI4CHEM_FRONTEND_ADDRESS", default=None)
NFDI4ING_FRONTEND_ADDRESS = env("NFDI4ING_FRONTEND_ADDRESS", default=None)
BASIC_AUTH_USERNAME = env("BASIC_AUTH_USERNAME", default=None)
BASIC_AUTH_PASSWORD = env("BASIC_AUTH_PASSWORD", default=None)
GITHUB_TEST_ACCESS_TOKEN = env("GITHUB_TEST_ACCESS_TOKEN", default=None)
ORCID_TEST_ACCESS_TOKEN = env("ORCID_TEST_ACCESS_TOKEN", default=None)
ORCID_LOGIN_USERNAME = env("ORCID_LOGIN_USERNAME", default=None)
GITHUB_LOGIN_USERNAME = env("GITHUB_LOGIN_USERNAME", default=None)
GITHUB_USER_TS_TOKEN = env("GITHUB_USER_TS_TOKEN", default=None)
ORCID_USER_TS_TOKEN = env("ORCID_USER_TS_TOKEN", default=None)
GITHUB_LOGIN_CODE = env("GITHUB_LOGIN_CODE", default=None)
ORCID_LOGIN_CODE = env("ORCID_LOGIN_CODE", default=None)
STATS_API_TOKEN = env("STATS_API_TOKEN", default=None)
BIOREGISTRY_ENDPOINT = env("BIOREGISTRY_ENDPOINT", default=None)
NFDI4CHEM_SEARCH_SERVICE_ENDPOINT = env(
    "NFDI4CHEM_SEARCH_SERVICE_ENDPOINT", default=None
)
