from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Configuration locale du système QA.

    Les valeurs sensibles viennent de .env et ne sont jamais affichées
    dans les rapports ni envoyées aux agents.
    """

    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash"
    gemini_api_key: str = ""
    llm_fallback_provider: str = "groq"
    groq_api_key: str = ""
    mistral_api_key: str = ""

    telegram_bot_token: str = ""
    telegram_allowed_user_id: str = ""

    test_api_url: str = "http://localhost:8002"
    test_ui_url: str = "http://localhost:5175"
    test_user1_email: str = "qa.user1@example.com"
    test_user1_password: str = "QaTest123!"
    test_user2_email: str = "qa.user2@example.com"
    test_user2_password: str = "QaTest123!"

    real_agents_enabled: bool = False
    llm_timeout_seconds: float = 60.0
    api_probe_timeout_seconds: float = 15.0
    automation_timeout_seconds: float = 300.0
    ui_automation_timeout_seconds: float = 240.0
    ui_browser_headless: bool = True

    mission_db_path: Path = PROJECT_ROOT / "workspace" / "missions.db"
    reports_dir: Path = PROJECT_ROOT / "reports" / "missions"
    workspace_dir: Path = PROJECT_ROOT / "workspace"
    postman_dir: Path = PROJECT_ROOT / "postman"
    allure_results_dir: Path = PROJECT_ROOT / "reports" / "allure-results"

    # Agent 6 DevOps (phase 7) : la publication Git est strictement opt-in.
    devops_publish_enabled: bool = False
    devops_repo_dir: Path = PROJECT_ROOT
    devops_remote: str = "origin"
    devops_base_branch: str = "main"
    devops_timeout_seconds: float = 120.0

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
