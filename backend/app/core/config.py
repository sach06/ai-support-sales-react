"""
Configuration management for the AI Sales Application (React Backend)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings"""

    # Project paths
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"

    # Azure OpenAI settings
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    # Alternative: Standard OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Web Search API (for enrichment)
    BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    # Database
    DB_PATH = DATA_DIR / "sales_app.db"

    # Model settings
    PREDICTION_MODEL_PATH = BASE_DIR / "models" / "sales_predictor.pkl"
    XGB_MODEL_PATH = BASE_DIR / "models" / "xgb_priority_v1.pkl"

    @property
    def use_azure_openai(self) -> bool:
        return bool(self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT)

    @property
    def use_openai(self) -> bool:
        return bool(self.OPENAI_API_KEY)


settings = Settings()
