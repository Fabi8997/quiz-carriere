from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from .config import settings


def _make_engine():
    kwargs = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, **kwargs)

    # WAL mode + FK enforced su SQLite
    if settings.DATABASE_URL.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_game_tables() -> None:
    """Crea le tabelle di gioco se non esistono ancora.

    Le tabelle dei giocatori (players, clubs, careers, …) sono gestite
    dagli script di scraping — qui si creano solo le tabelle di sessione.
    """
    from .models import game  # noqa: F401 — registra i modelli su Base

    Base.metadata.create_all(bind=engine, checkfirst=True)
