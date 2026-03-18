"""
Configuration management for the AI Sales Application (React Backend)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the backend root first, then fall back to a repo-root .env.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")


class Settings:
    """Application settings"""

    # Project paths
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"

    # Azure OpenAI settings
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    # Alternative: Standard OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Web Search API (for enrichment)
    BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    # Database
    DB_PATH = DATA_DIR / "sales_app.db"
    INTERNAL_KNOWLEDGE_DIR = DATA_DIR / "internal_knowledge"
    INTERNAL_KNOWLEDGE_NETWORK_ROOT = Path(
        os.getenv("INTERNAL_KNOWLEDGE_NETWORK_ROOT", r"P:\SDE-TS-Customer-Projects")
    )
    INTERNAL_KNOWLEDGE_INDEX_TARGETS = tuple(
        filter(
            None,
            (
                part.strip()
                for part in os.getenv(
                    "INTERNAL_KNOWLEDGE_INDEX_TARGETS",
                    "06_Allgemeine Informationen;Literatur;Cooperation Agreements;08_Projektmanagement;07_SCIFORMA/acceptence_reports;07_SCIFORMA/field_services_reports;07_SCIFORMA/timesheet_reports",
                ).split(";")
            ),
        )
    )

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
