from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    llm_api_key: str = Field(alias="LLM_API_KEY", default="super-secret")
    llm_base_url: str = Field(alias="LLM_BASE_URL", default="http://localhost:65534/v1")
    llm_model_id: str = Field(alias="LLM_MODEL_ID", default="local-model")

    # app state
    app_env: str = Field(alias="APP_ENV", default="development")

    # Server
    host: str = Field(alias="HOST", default="0.0.0.0")
    port: int = Field(alias="PORT", default=80)

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings() 