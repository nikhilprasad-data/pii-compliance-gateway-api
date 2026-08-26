from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import settings

db_url = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

engine = create_async_engine(
    db_url,
    echo= False
)

SessionLocal = async_sessionmaker(
     bind= engine,
     class_= AsyncSession,
     autocommit=False,
     autoflush=False,
     expire_on_commit=False
)

async def get_db(): 

     """FastAPI dependency to manage database session."""
     async with SessionLocal() as db:
          try:
               yield db
          finally:
               await db.close()
