from fastapi import HTTPException, status


class GameNotFound(HTTPException):
    def __init__(self, token: str):
        # Non echo del token nel messaggio — evita information leakage
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partita non trovata.",
        )


class GameAlreadyOver(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="La partita è già terminata.",
        )


class HintAlreadyUnlocked(HTTPException):
    def __init__(self, hint_type: str):
        # Non rivela il tipo di indizio nel dettaglio dell'errore
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Indizio già sbloccato.",
        )


class NoPlayersFound(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nessun giocatore trovato con i filtri selezionati.",
        )


class ChallengeNotFound(HTTPException):
    def __init__(self, token: str):
        # Non echo del token — stesso messaggio di GameNotFound per non distinguere i casi
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sfida non trovata.",
        )
