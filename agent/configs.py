from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    llm_api_key: str = Field(alias="LLM_API_KEY", default="super-secret")
    llm_base_url: str = Field(alias="LLM_BASE_URL", default="https://api.openai.com/v1")
    llm_model_id: str = Field(alias="LLM_MODEL_ID", default="gpt-4o-mini")
    llm_model_id_code: str = Field(alias="LLM_MODEL_ID_CODE", default="gpt-4o-mini")
    llm_model_provider: str = Field(alias="LLM_MODEL_PROVIDER", default="local-ai")

    # app state
    app_env: str = Field(alias="APP_ENV", default="development")

    # Server
    host: str = Field(alias="HOST", default="0.0.0.0")
    port: int = Field(alias="PORT", default=80)

    opencode_host: str = Field(alias="OPENCODE_HOST", default="localhost")
    opencode_port: int = Field(alias="OPENCODE_PORT", default=4096)
    opencode_directory: str = Field(alias="OPENCODE_DIRECTORY", default="./opencode-workspace")
    
    tavily_api_key: str = Field(alias="TAVILY_API_KEY", default="")
    financial_datasets_api_key: str = Field(alias="FINANCIAL_DATASETS_API_KEY", default="")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

# Global settings instance
settings = Settings() 