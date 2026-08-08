import os
import logging
from dotenv import load_dotenv


class Settings:
    def __init__(self):
        load_dotenv()

        self.TEMP_STORAGE_DIR = Settings.get_env_or_error("TEMP_STORAGE_DIR")

        try:
            self.OPENAI_ORG = Settings.get_env_or_error("OPENAI_ORG")
            self.OPENAI_PROJECT = Settings.get_env_or_error("OPENAI_PROJECT")
            self.OPENAI_API_KEY = Settings.get_env_or_error("OPENAI_API_KEY")
            self.HAS_OPENAI = True
        except EnvironmentError:
            logging.warning("No OpenAI credentials configured. Features will be limited")
            self.HAS_OPENAI = False

        self.POSTGRES_CONN_STR = Settings.get_env_or_error("POSTGRES_CONN_STR")

        self.REDIS_HOST = Settings.get_env_or_error("REDIS_HOST")
        self.REDIS_PORT = int(Settings.get_env_or_error("REDIS_PORT"))
        self.REDIS_DB = int(Settings.get_env_or_error("REDIS_DB"))
        self.REDIS_CONN_STR = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        self.MINIO_HOST = Settings.get_env_or_error("MINIO_HOST")
        self.MINIO_SECURE = Settings.get_env_or_error("MINIO_SECURE").lower() != 'false'
        self.MINIO_USER = Settings.get_env_or_error("MINIO_USER")
        self.MINIO_PASS = Settings.get_env_or_error("MINIO_PASS")
        self.MINIO_BUCKET = Settings.get_env_or_error("MINIO_BUCKET")


    @classmethod
    def get_env_or_error(cls, name: str) -> str:
        x = os.getenv(name)
        if x is None:
            raise EnvironmentError(f"Environment variable {name} unset.")

        return x

