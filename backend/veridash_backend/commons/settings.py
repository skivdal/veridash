import os
from dotenv import load_dotenv


class Settings:
    def __init__(self):
        load_dotenv()

        self.OPENAI_ORG = os.getenv("OPENAI_ORG")
        self.OPENAI_PROJECT = os.getenv("OPENAI_PROJECT")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

