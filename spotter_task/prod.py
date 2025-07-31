from settings import *
from decouple import config
import dj_database_url
SECRET_KEY = config("DJANGO_SECRET_KEY")

DEBUG = False



CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=False, cast=bool)


DATABASES = {
    'default': dj_database_url.config(),
}
