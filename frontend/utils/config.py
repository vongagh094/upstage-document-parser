# project_path/frontend/utils/config.py

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Config(BaseSettings):
    """
    Streamlit frontend configuration.

    Stores backend API connection info and UI-related settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backend API connection
    HOST: str = "localhost"
    PORT: int = 8000

    @property
    def API_BASE_URL(self) -> str:
        """
        Return the backend API base URL.

        Returns:
            str: Backend API URL (e.g., http://localhost:8000/api/v1)
        """
        return f"http://{self.HOST}:{self.PORT}/api/v1"


# Shared config instance
config = Config()
