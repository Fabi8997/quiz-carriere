"""Modelli ORM per le sessioni di gioco — creati automaticamente all'avvio."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base


def _new_token() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GameSession(Base):
    """Una partita singola, identificata da un token UUID opaco."""

    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True)
    token = Column(Text, unique=True, nullable=False, default=_new_token)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    nickname = Column(Text)
    # playing | won | surrendered
    status = Column(Text, nullable=False, default="playing")
    filters_json = Column(Text)
    created_at = Column(Text, nullable=False, default=_now)
    completed_at = Column(Text)

    player = relationship("Player")
    guesses = relationship("GameGuess", back_populates="session", order_by="GameGuess.id")
    hints = relationship("GameHint", back_populates="session")


class GameGuess(Base):
    """Un singolo tentativo all'interno di una sessione."""

    __tablename__ = "game_guesses"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    guessed_player_id = Column(Integer, ForeignKey("players.id"))  # NULL se nome non trovato
    raw_input = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)
    guessed_at = Column(Text, nullable=False, default=_now)

    session = relationship("GameSession", back_populates="guesses")
    guessed_player = relationship("Player")


class GameHint(Base):
    """Un indizio sbloccato durante una sessione."""

    __tablename__ = "game_hints"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    # role | nationality | photo
    hint_type = Column(Text, nullable=False)
    unlocked_at = Column(Text, nullable=False, default=_now)

    session = relationship("GameSession", back_populates="hints")

    __table_args__ = (UniqueConstraint("session_id", "hint_type", name="uq_hint_per_session"),)


class ChallengeLink(Base):
    """Link di sfida condivisibile. Un token punta a un giocatore specifico."""

    __tablename__ = "challenge_links"

    id = Column(Integer, primary_key=True)
    token = Column(Text, unique=True, nullable=False, default=_new_token)
    creator_nickname = Column(Text, nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    created_at = Column(Text, nullable=False, default=_now)

    player = relationship("Player")
