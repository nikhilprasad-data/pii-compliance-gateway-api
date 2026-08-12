from pydantic_settings import BaseSettings

class Settings(BaseSettings):
     APP_NAME: str = "PII Compliance Gateway API"
     APP_VERSION: str = "1.0.0"
     API_V1_STR: str = "/api/v1"

     # --- AI Providers ---
     GROQ_API_KEY: str | None = None
     GOOGLE_API_KEY: str | None = None

     # --- LangChain Tracing ---
     LANGCHAIN_API_KEY: str | None = None
     LANGCHAIN_TRACING_V2: bool = True

     # --- Database ---
     DB_HOST: str | None = None
     DB_USER: str | None = None
     DB_PASSWORD: str | None = None
     DB_NAME: str | None = None
     DB_PORT: int = 5432

     # --- JWT ---
     ALGORITHM: str | None = None
     JWT_TOKEN_EXPIRATION_TIME_MINUTES: int | None = None
     JWT_SECRET_KEY: str | None = None

     # --- Redis ---
     REDIS_HOST: str | None = None
     REDIS_PORT: int | None = None
     REDIS_PASSWORD: str | None = None
     REDIS_DB: int | None = None

     class Config:
         env_file = ".env"
         case_sensitive = True

settings = Settings()
