from pathlib import Path
import os
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    @property
    def db_host(self) -> str:
        return os.getenv("DB_HOST", "127.0.0.1")

    @property
    def db_port(self) -> int:
        return int(os.getenv("DB_PORT", "3306"))

    @property
    def db_user(self) -> str:
        return os.getenv("DB_USER", "root")

    @property
    def db_password(self) -> str:
        return os.getenv("DB_PASSWORD", "")

    @property
    def db_name(self) -> str:
        return os.getenv("DB_NAME", "karyawan_assistant")

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"

    @property
    def database_url(self) -> str:
        pwd = self.db_password
        auth = f"{self.db_user}:{pwd}" if pwd else self.db_user
        return f"mysql+pymysql://{auth}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    def update_ai_settings(self, api_key: str | None = None, model: str | None = None) -> None:
        if not ENV_PATH.exists():
            ENV_PATH.write_text("", encoding="utf-8")
        if api_key is not None:
            clean_key = api_key.strip()
            set_key(str(ENV_PATH), "GEMINI_API_KEY", clean_key)
            os.environ["GEMINI_API_KEY"] = clean_key
        if model is not None:
            clean_model = model.strip() or "gemini-3.8-flash"
            set_key(str(ENV_PATH), "GEMINI_MODEL", clean_model)
            os.environ["GEMINI_MODEL"] = clean_model


settings = Settings()
