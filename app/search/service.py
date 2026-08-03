import math
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainInvariantError
from app.search.repository import SearchRepositoryInterface
from app.search.schemas import (
    SearchResponse,
    SearchResultItem,
    SearchSuggestionsResponse,
    SuggestionItem,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in KM between two (lat, lon) coordinates."""
    r = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class SearchServiceInterface(ABC):
    """Abstract service interface for search operations."""

    @abstractmethod
    async def execute_search(
        self,
        q: str | None = None,
        entity_type: str = "all",
        is_veg: bool | None = None,
        cuisine: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        is_active_only: bool = True,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float | None = 10.0,
        sort_by: str = "relevance",
        skip: int = 0,
        limit: int = 20,
    ) -> SearchResponse:
        """Execute multi-entity search query with filters and sorting."""

    @abstractmethod
    async def get_suggestions(
        self, q: str, limit: int = 10
    ) -> SearchSuggestionsResponse:
        """Fetch typeahead query suggestions."""


class SearchService(SearchServiceInterface):
    """Concrete implementation of SearchServiceInterface."""

    def __init__(
        self,
        session: AsyncSession,
        search_repo: SearchRepositoryInterface,
    ) -> None:
        self.session = session
        self.search_repo = search_repo

    async def execute_search(
        self,
        q: str | None = None,
        entity_type: str = "all",
        is_veg: bool | None = None,
        cuisine: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        is_active_only: bool = True,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float | None = 10.0,
        sort_by: str = "relevance",
        skip: int = 0,
        limit: int = 20,
    ) -> SearchResponse:
        query_str = (q or "").strip()
        current_time = datetime.now(UTC)

        restaurants_res: list[SearchResultItem] = []
        dishes_res: list[SearchResultItem] = []
        categories_res: list[SearchResultItem] = []

        # 1. Search Restaurants/Branches
        if entity_type in {"all", "restaurant"}:
            branch_rows = await self.search_repo.search_branches(
                q=query_str if query_str else None,
                cuisine=cuisine,
                is_active_only=is_active_only,
                current_time=current_time if is_active_only else None,
                skip=0,
                limit=limit * 2,
            )
            for branch, brand in branch_rows:
                dist = None
                if (
                    latitude is not None
                    and longitude is not None
                    and branch.latitude is not None
                    and branch.longitude is not None
                ):
                    dist = haversine_distance(
                        latitude,
                        longitude,
                        float(branch.latitude),
                        float(branch.longitude),
                    )
                    if radius_km is not None and dist > radius_km:
                        continue

                restaurants_res.append(
                    SearchResultItem(
                        entity_type="restaurant",
                        id=str(branch.id),
                        title=branch.name,
                        description=brand.description,
                        branch_id=str(branch.id),
                        branch_name=branch.name,
                        brand_name=brand.name,
                        is_available=branch.is_active,
                        image_url=brand.logo_url or brand.banner_url,
                        cuisine_types=brand.cuisine_types,
                        distance_km=dist,
                    )
                )

        # 2. Search Dishes/MenuItems
        if entity_type in {"all", "dish"}:
            item_rows = await self.search_repo.search_menu_items(
                q=query_str if query_str else None,
                is_veg=is_veg,
                min_price=min_price,
                max_price=max_price,
                is_active_only=is_active_only,
                skip=0,
                limit=limit * 2,
            )
            for item, category, _menu, branch, brand in item_rows:
                dist = None
                if (
                    latitude is not None
                    and longitude is not None
                    and branch.latitude is not None
                    and branch.longitude is not None
                ):
                    dist = haversine_distance(
                        latitude,
                        longitude,
                        float(branch.latitude),
                        float(branch.longitude),
                    )
                    if radius_km is not None and dist > radius_km:
                        continue

                dishes_res.append(
                    SearchResultItem(
                        entity_type="dish",
                        id=str(item.id),
                        title=item.name,
                        description=item.description,
                        branch_id=str(branch.id),
                        branch_name=branch.name,
                        brand_name=brand.name,
                        price=float(item.base_price),
                        is_veg=item.is_veg,
                        is_available=item.is_available and branch.is_active,
                        image_url=item.image_url,
                        distance_km=dist,
                    )
                )

        # 3. Search Categories
        if entity_type in {"all", "category"}:
            cat_rows = await self.search_repo.search_categories(
                q=query_str if query_str else None,
                is_active_only=is_active_only,
                skip=0,
                limit=limit * 2,
            )
            for cat, _menu, branch, brand in cat_rows:
                categories_res.append(
                    SearchResultItem(
                        entity_type="category",
                        id=str(cat.id),
                        title=cat.name,
                        branch_id=str(branch.id),
                        branch_name=branch.name,
                        brand_name=brand.name,
                        is_available=branch.is_active,
                    )
                )

        # Combine all results
        all_results = restaurants_res + dishes_res + categories_res

        # Sorting logic
        if sort_by == "name":
            all_results.sort(key=lambda x: x.title.lower())
        elif sort_by == "price_asc":
            all_results.sort(
                key=lambda x: x.price if x.price is not None else float("inf")
            )
        elif sort_by == "price_desc":
            all_results.sort(
                key=lambda x: x.price if x.price is not None else -1.0, reverse=True
            )
        elif sort_by == "distance":
            all_results.sort(
                key=lambda x: (
                    x.distance_km if x.distance_km is not None else float("inf")
                )
            )

        paginated_results = all_results[skip : skip + limit]

        return SearchResponse(
            query=query_str,
            total=len(all_results),
            restaurants=restaurants_res[:limit],
            dishes=dishes_res[:limit],
            categories=categories_res[:limit],
            results=paginated_results,
        )

    async def get_suggestions(
        self, q: str, limit: int = 10
    ) -> SearchSuggestionsResponse:
        query_str = q.strip()
        if not query_str:
            raise DomainInvariantError(
                message="Search query term cannot be empty.",
                error_code="EMPTY_SEARCH_QUERY",
            )

        rows = await self.search_repo.get_typeahead_suggestions(query_str, limit=limit)
        items = [
            SuggestionItem(text=text, type=stype, entity_id=str(eid) if eid else None)
            for text, stype, eid in rows
        ]
        return SearchSuggestionsResponse(query=query_str, suggestions=items)
