from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: int
    name: str
    position_general: str | None
    country_name: str | None
    # score non esposto nell'API pubblica — usato solo internamente per il ranking
    score: int = Field(exclude=True, default=0)


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


class TeamResult(BaseModel):
    id: int
    name: str
