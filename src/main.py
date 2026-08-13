from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config.settings import settings

# Initialize FastAPI app
app = FastAPI(
     title=settings.APP_NAME,
     version=settings.APP_VERSION,
     openapi_url=f"{settings.API_V1_STR}/openapi.json",
     docs_url="/docs",
     redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
     CORSMiddleware,
     allow_origins=["*"],
     allow_headers=["*"],
     allow_credentials=True,
     allow_methods=["*"]
)

# Health Check
@app.get("/health", tags=["System"])
async def health_check():
     """
    Standard Health Check Endpoint.
    """
     return {
          "status"       : "online",
          "environment"  : "development" if settings.DEBUG else "production",
          "app_name"     : settings.APP_NAME,
          "version"      : settings.APP_VERSION
     }

