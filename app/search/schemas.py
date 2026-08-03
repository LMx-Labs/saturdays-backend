from pydantic import BaseModel, ConfigDict, Field


class SearchResultItem(BaseModel):
    """Schema representing an individual search result item."""

    model_config = ConfigDict(from_attributes=True)

    entity_type: str = Field(
        ..., description="Type of entity ('restaurant', 'dish', 'category')"
    )
    id: str = Field(..., description="Entity unique identifier")
    title: str = Field(..., description="Entity title/name")
    description: str | None = None
    branch_id: str | None = None
    branch_name: str | None = None
    brand_name: str | None = None
    price: float | None = None
    is_veg: bool | None = None
    is_available: bool = True
    image_url: str | None = None
    cuisine_types: list[str] | None = None
    distance_km: float | None = None


class SearchResponse(BaseModel):
    """Response payload for multi-entity search query."""

    query: str
    total: int
    restaurants: list[SearchResultItem]
    dishes: list[SearchResultItem]
    categories: list[SearchResultItem]
    results: list[SearchResultItem]


class SuggestionItem(BaseModel):
    """Schema for individual search suggestion."""

    text: str = Field(..., description="Suggested query text")
    type: str = Field(
        ..., description="Suggestion type ('restaurant', 'dish', 'cuisine')"
    )
    entity_id: str | None = None


class SearchSuggestionsResponse(BaseModel):
    """Response payload for typeahead query suggestions."""

    query: str
    suggestions: list[SuggestionItem]
