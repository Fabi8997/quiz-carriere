"""Modelli ORM in sola lettura — rispecchiano lo schema gestito dagli script di scraping."""

from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True)
    tm_id = Column(Text)
    name = Column(Text, nullable=False)
    flag_url = Column(Text)

    players = relationship("Player", back_populates="country")


class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True)
    tm_id = Column(Text, unique=True)
    slug = Column(Text, unique=True)
    name = Column(Text, nullable=False)
    crest_url = Column(Text)
    crest_downloaded_at = Column(Text)

    careers = relationship("Career", back_populates="club")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    tm_id = Column(Text, unique=True)
    slug = Column(Text, unique=True)
    name = Column(Text, nullable=False)
    normalized_name = Column(Text)
    birth_date = Column(Text)
    birth_place = Column(Text)
    height_cm = Column(Integer)
    country_id = Column(Integer, ForeignKey("countries.id"))
    position_general = Column(Text)
    position_detailed = Column(Text)
    photo_url = Column(Text)
    photo_downloaded_at = Column(Text)

    country = relationship("Country", back_populates="players")
    careers = relationship("Career", back_populates="player", order_by="Career.season")
    aliases = relationship("PlayerAlias", back_populates="player")


class Career(Base):
    __tablename__ = "careers"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    club_id = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    season = Column(Integer, nullable=False)
    appearances = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    competitions = Column(Text)
    source_id = Column(Integer)

    player = relationship("Player", back_populates="careers")
    club = relationship("Club", back_populates="careers")


class PlayerAlias(Base):
    __tablename__ = "player_aliases"

    # alias è PK nello schema reale (TEXT PRIMARY KEY in db_v2.py)
    alias = Column(Text, primary_key=True, nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)

    player = relationship("Player", back_populates="aliases")
