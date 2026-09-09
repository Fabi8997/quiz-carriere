"""Test per le API di gioco."""

import pytest


class TestCreateGame:
    def test_crea_partita_base(self, client, sample_player):
        resp = client.post("/game", json={"nickname": "Luca", "filters": {}})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "playing"
        assert len(data["career"]) > 0
        assert data["attempt_count"] == 0
        assert data["player"] is None  # non rivelato finché non finisce

    def test_carriera_aggregata(self, client, sample_player):
        resp = client.post("/game", json={"filters": {}})
        data = resp.json()
        career = data["career"]
        # Club Alpha 1995+1996 → un solo entry aggregato
        alpha = next((e for e in career if e["club_name"] == "Club Alpha"), None)
        assert alpha is not None
        assert alpha["season_start"] == 1995
        assert alpha["season_end"] == 1996
        assert alpha["appearances"] == 58
        assert alpha["goals"] == 18

    def test_tutti_gli_indizi_bloccati(self, client, sample_player):
        resp = client.post("/game", json={"filters": {}})
        hints = resp.json()["hints"]
        for hint in hints.values():
            assert hint["unlocked"] is False

    def test_filtro_posizione_inesistente(self, client, sample_player):
        resp = client.post("/game", json={"filters": {"position": "Portiere"}})
        assert resp.status_code == 404


class TestGuess:
    def test_risposta_sbagliata(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/guess", json={"input": "Giocatore Sbagliato"})
        data = resp.json()
        assert data["status"] == "playing"
        assert data["attempt_count"] == 1
        assert data["guesses"][0]["correct"] is False

    def test_risposta_corretta(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/guess", json={"input": "Test Campionissimo"})
        data = resp.json()
        assert data["status"] == "won"
        assert data["guesses"][0]["correct"] is True
        assert data["player"] is not None
        assert data["player"]["name"] == "Test Campionissimo"

    def test_guess_su_partita_terminata(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        client.post(f"/game/{token}/surrender")
        resp = client.post(f"/game/{token}/guess", json={"input": "Qualcuno"})
        assert resp.status_code == 409

    def test_token_inesistente(self, client, sample_player):
        resp = client.post("/game/token-non-esiste/guess", json={"input": "Qualcuno"})
        assert resp.status_code == 404


class TestHints:
    def test_sblocca_ruolo(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/hint/role")
        data = resp.json()
        assert data["hints"]["role"]["unlocked"] is True
        assert data["hints"]["role"]["value"] == "Attaccante"
        assert data["hints_used"] == 1

    def test_sblocca_nazionalita(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/hint/nationality")
        data = resp.json()
        assert data["hints"]["nationality"]["unlocked"] is True
        assert data["hints"]["nationality"]["value"] == "Italia"

    def test_sblocca_foto(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/hint/photo")
        data = resp.json()
        assert data["hints"]["photo"]["unlocked"] is True
        assert data["hints"]["photo"]["value"] == str(sample_player.id)

    def test_sblocca_indizio_duplicato(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        client.post(f"/game/{token}/hint/role")
        resp = client.post(f"/game/{token}/hint/role")
        assert resp.status_code == 409

    def test_hint_su_partita_terminata(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        client.post(f"/game/{token}/surrender")
        resp = client.post(f"/game/{token}/hint/role")
        assert resp.status_code == 409


class TestSurrender:
    def test_resa_rivela_giocatore(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        resp = client.post(f"/game/{token}/surrender")
        data = resp.json()
        assert data["status"] == "surrendered"
        assert data["player"]["name"] == "Test Campionissimo"

    def test_doppia_resa(self, client, sample_player):
        token = client.post("/game", json={"filters": {}}).json()["token"]
        client.post(f"/game/{token}/surrender")
        resp = client.post(f"/game/{token}/surrender")
        assert resp.status_code == 409
