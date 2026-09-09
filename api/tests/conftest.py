"""Fixtures condivise tra tutti i test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.search import build_index


# ── DB in memoria per i test ──────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite://"  # in-memory: si resetta a ogni run di sessione test


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Importa tutti i modelli per registrarli su Base
    from app.models import player, game  # noqa: F401
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="session")
def _session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def db(_session_factory):
    """Sessione DB per ogni singolo test — tutto viene rollbackato alla fine."""
    connection = _session_factory.kw["bind"].connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """TestClient FastAPI con DB di test iniettata tramite dependency override."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Dati di test ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_player(db):
    """Crea un giocatore di test con la sua carriera e ricostruisce l'indice."""
    from app.models.player import Player, Club, Career, Country

    country = Country(name="Italia", tm_id="100", flag_url=None)
    db.add(country)
    db.flush()

    player = Player(
        tm_id="99999",
        slug="test-campionissimo",
        name="Test Campionissimo",
        normalized_name="test campionissimo",
        position_general="Attaccante",
        country_id=country.id,
    )
    db.add(player)
    db.flush()

    club_a = Club(tm_id="1001", slug="club-alpha", name="Club Alpha")
    club_b = Club(tm_id="1002", slug="club-beta", name="Club Beta")
    db.add_all([club_a, club_b])
    db.flush()

    careers = [
        Career(player_id=player.id, club_id=club_a.id, season=1995, appearances=30, goals=10),
        Career(player_id=player.id, club_id=club_a.id, season=1996, appearances=28, goals=8),
        Career(player_id=player.id, club_id=club_b.id, season=1997, appearances=25, goals=12),
    ]
    db.add_all(careers)
    db.commit()

    # L'indice fuzzy deve essere ricostruito con i dati del test DB
    build_index(db)

    return player
