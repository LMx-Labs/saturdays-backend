import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import get_current_user
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.customer.repository import CustomerRepository, CustomerRepositoryInterface
from app.review.repository import ReviewRepository, ReviewRepositoryInterface
from app.review.schemas import (
    RestaurantRatingSummary,
    ReviewCreate,
    ReviewModerateRequest,
    ReviewReply,
    ReviewResponse,
)
from app.review.service import ReviewService, ReviewServiceInterface

router = APIRouter(prefix="", tags=["Review"])


def get_review_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ReviewRepositoryInterface:
    return ReviewRepository(session=session)


def get_customer_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CustomerRepositoryInterface:
    return CustomerRepository(session=session)


def get_review_service(
    session: AsyncSession = Depends(get_db_session),
    review_repo: ReviewRepositoryInterface = Depends(get_review_repository),
    customer_repo: CustomerRepositoryInterface = Depends(get_customer_repository),
) -> ReviewServiceInterface:
    return ReviewService(
        session=session, review_repo=review_repo, customer_repo=customer_repo
    )


@router.post(
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a verified order review",
)
async def create_review(
    req: ReviewCreate,
    current_user: UserClaims = Depends(get_current_user),
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> ReviewResponse:
    return await review_service.create_review(
        user_id=uuid.UUID(current_user.sub), req=req
    )


@router.get(
    "/branches/{branch_id}/reviews",
    response_model=list[ReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="Get customer reviews for a branch",
)
async def list_branch_reviews(
    branch_id: uuid.UUID,
    include_hidden: bool = Query(False),
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> list[ReviewResponse]:
    return await review_service.get_branch_reviews(
        branch_id=branch_id, include_hidden=include_hidden
    )


@router.get(
    "/branches/{branch_id}/rating-summary",
    response_model=RestaurantRatingSummary,
    status_code=status.HTTP_200_OK,
    summary="Get restaurant rating distribution summary",
)
async def get_branch_rating_summary(
    branch_id: uuid.UUID,
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> RestaurantRatingSummary:
    return await review_service.get_branch_rating_summary(branch_id=branch_id)


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get review by ID",
)
async def get_review(
    review_id: uuid.UUID,
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> ReviewResponse:
    return await review_service.get_review(review_id=review_id)


@router.post(
    "/reviews/{review_id}/reply",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Add merchant reply to review",
)
async def reply_to_review(
    review_id: uuid.UUID,
    req: ReviewReply,
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> ReviewResponse:
    return await review_service.reply_to_review(review_id=review_id, req=req)


@router.put(
    "/reviews/{review_id}/moderate",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Moderate review visibility",
)
async def moderate_review(
    review_id: uuid.UUID,
    req: ReviewModerateRequest,
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> ReviewResponse:
    return await review_service.moderate_review(review_id=review_id, req=req)


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete review",
)
async def delete_review(
    review_id: uuid.UUID,
    review_service: ReviewServiceInterface = Depends(get_review_service),
) -> None:
    await review_service.delete_review(review_id=review_id)
