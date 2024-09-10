"""
Setup Configuration for Application
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_HOSTNAME: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    PROJECT_ID: str
    LOCATION: str
    JOB_REQUEST_SUBSCRIPTION_ID: str
    JOB_START_TOPIC_PATH: str
    JOB_COMPLETION_SUBSCRIPTION: str
    JOB_COMPLETION_TOPIC: str
    CUSTOM_HEADER_FIELD: str
    JOB_COMPLETION_SUBSCRIPTION_ID: str
    ALLOWED_ROLES: str
    PROJECT_NAME: str
    MAX_WORKERS: int
    ROUTE_PREFIX: str
    API_VERSION: str
    SECRET_ID: str
    KEY_SERVER_URL: str
    SECRET_VERSION: int
    ENV: str
    CLOUD_STORAGE_TRIGGER_SUBSCRIPTION: str
    PROJECT_NAME_TOFFEE: str
    OUTPUT_BUCKET_TOFFEE: str
    MEDIA_CDN_BASE: str

    class Config:
        env_file = ".env"


settings = Settings()
