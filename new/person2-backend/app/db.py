from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.config import get_settings

def make_database(settings):
    engine = create_async_engine(settings.connection_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
