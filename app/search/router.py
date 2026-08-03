from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.search.repository import SearchRepository, SearchRepositoryInterface
from app.search.schemas import SearchResponse, SearchSuggestionsResponse
from app.search.service import SearchService, SearchServiceInterface

router = APIRouter(prefix="/search", tags=["Search"])


def get_search_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SearchRepositoryInterface:
    return SearchRepository(session=session)


def get_search_service(
    session: AsyncSession = Depends(get_db_session),
    search_repo: SearchRepositoryInterface = Depends(get_search_repository),
) -> SearchServiceInterface:
    return SearchService(session=session, search_repo=search_repo)


@router.get(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search restaurants, dishes, and categories",
    description="Public search endpoint supporting multi-entity discovery, filtering, location awareness, and sorting.",
)
async def search(
    q: str | None = Query(None, description="Query string"),
    type: str = Query(
        "all", description="Entity filter ('all', 'restaurant', 'dish', 'category')"
    ),
    is_veg: bool | None = Query(None, description="Filter for vegetarian items"),
    cuisine: str | None = Query(None, description="Filter by cuisine tag"),
    min_price: float | None = Query(None, ge=0.0, description="Minimum dish price"),
    max_price: float | None = Query(None, ge=0.0, description="Maximum dish price"),
    is_active_only: bool = Query(
        True, description="Filter active operating stores (INV-SRCH-001)"
    ),
    latitude: float | None = Query(
        None, ge=-90.0, le=90.0, description="Customer latitude"
    ),
    longitude: float | None = Query(
        None, ge=-180.0, le=180.0, description="Customer longitude"
    ),
    radius_km: float | None = Query(
        10.0, ge=0.1, le=100.0, description="Max delivery radius in KM"
    ),
    sort_by: str = Query(
        "relevance",
        description="Sorting criterion ('relevance', 'name', 'price_asc', 'price_desc', 'distance')",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search_service: SearchServiceInterface = Depends(get_search_service),
) -> SearchResponse:
    return await search_service.execute_search(
        q=q,
        entity_type=type,
        is_veg=is_veg,
        cuisine=cuisine,
        min_price=min_price,
        max_price=max_price,
        is_active_only=is_active_only,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/suggestions",
    response_model=SearchSuggestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get typeahead search suggestions",
    description="Public endpoint returning typeahead suggestions for search queries.",
)
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Typeahead search prefix"),
    limit: int = Query(10, ge=1, le=20),
    search_service: SearchServiceInterface = Depends(get_search_service),
) -> SearchSuggestionsResponse:
    return await search_service.get_suggestions(q=q, limit=limit)
