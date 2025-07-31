from settings import *
from decouple import config

SECRET_KEY = config("DJANGO_SECRET_KEY")

DEBUG = False



CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=False, cast=bool)

