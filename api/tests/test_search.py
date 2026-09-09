"""Test per il motore di ricerca fuzzy."""

import pytest
from app.services.search import search_players, normalize, build_index


class TestNormalize:
    def test_minuscolo(self):
        assert normalize("Ronaldo") == "ronaldo"

    def test_accenti(self):
        assert normalize("André") == "andre"

    def test_spazi_multipli(self):
        assert normalize("del  piero") == "del piero"

    def test_punteggiatura(self):
        assert normalize("CR7!") == "cr7"


class TestSearch:
    def test_nome_esatto(self, db, sample_player):
        results = search_players("Test Campionissimo")
        assert len(results) > 0
        assert results[0].name == "Test Campionissimo"
        assert results[0].score == 100 or results[0].score > 80

    def test_nome_parziale(self, db, sample_player):
        results = search_players("Campionissimo")
        assert any(r.name == "Test Campionissimo" for r in results)

    def test_nome_invertito(self, db, sample_player):
        results = search_players("Campionissimo Test")
        assert any(r.name == "Test Campionissimo" for r in results)

    def test_query_vuota(self, db, sample_player):
        results = search_players("")
        assert results == []

    def test_limit(self, db, sample_player):
        results = search_players("Test", limit=1)
        assert len(results) <= 1

    def test_giocatore_inesistente(self, db, sample_player):
        results = search_players("xyzxyzxyz123nonsense")
        assert len(results) == 0


class TestSearchEndpoint:
    def test_endpoint_base(self, client, sample_player):
        resp = client.get("/search?q=Test")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "Test"

    def test_endpoint_limit(self, client, sample_player):
        resp = client.get("/search?q=Test&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 1

    def test_endpoint_query_vuota(self, client, sample_player):
        resp = client.get("/search?q=")
        assert resp.status_code == 422  # validation error da FastAPI
