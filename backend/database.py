import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
database_url = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "database" / "clinical.db"}')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
is_sqlite = database_url.startswith('sqlite:')
if os.getenv('VERCEL') and is_sqlite:
    raise RuntimeError('Set DATABASE_URL to a persistent hosted PostgreSQL database on Vercel; local SQLite cannot persist across function instances.')
if is_sqlite:
    (ROOT / 'database').mkdir(exist_ok=True)
engine = create_engine(database_url, connect_args={'check_same_thread': False} if is_sqlite else {}, pool_pre_ping=True)
@event.listens_for(engine, 'connect')
def foreign_keys(connection, _):
    if is_sqlite:
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
def get_db():
    with SessionLocal() as db:
        yield db
