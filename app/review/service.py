import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    EntityNotFoundError,
    UnprocessableEntityError,
)
from app.customer.repository import CustomerRepositoryInterface
from app.review.models import Review
from app.review.repository import ReviewRepositoryInterface
from app.review.schemas import (
    RestaurantRatingSummary,
    ReviewCreate,
    ReviewModerateRequest,
    ReviewReply,
    ReviewResponse,
)


class ReviewServiceInterface(ABC):
    @abstractmethod
    async def create_review(
        self, user_id: uuid.UUID, req: ReviewCreate
    ) -> ReviewResponse:
        pass

    @abstractmethod
    async def get_branch_reviews(
        self, branch_id: uuid.UUID, include_hidden: bool = False
    ) -> list[ReviewResponse]:
        pass

    @abstractmethod
    async def get_branch_rating_summary(
        self, branch_id: uuid.UUID
    ) -> RestaurantRatingSummary:
        pass

    @abstractmethod
    async def get_review(self, review_id: uuid.UUID) -> ReviewResponse:
        pass

    @abstractmethod
    async def reply_to_review(
        self, review_id: uuid.UUID, req: ReviewReply
    ) -> ReviewResponse:
        pass

    @abstractmethod
    async def moderate_review(
        self, review_id: uuid.UUID, req: ReviewModerateRequest
    ) -> ReviewResponse:
        pass

    @abstractmethod
    async def delete_review(self, review_id: uuid.UUID) -> None:
        pass


class ReviewService(ReviewServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        review_repo: ReviewRepositoryInterface,
        customer_repo: CustomerRepositoryInterface,
    ):
        self.session = session
        self.review_repo = review_repo
        self.customer_repo = customer_repo

    async def create_review(
        self, user_id: uuid.UUID, req: ReviewCreate
    ) -> ReviewResponse:
        # 1. Check customer profile existence
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            raise EntityNotFoundError(
                message="Customer profile not found.", error_code="CUSTOMER_NOT_FOUND"
            )

        # 2. Verified purchase validation (INV-0007)
        order = await self.review_repo.get_order_by_id(req.order_id)
        if not order:
            raise EntityNotFoundError(
                message="Order not found.", error_code="ORDER_NOT_FOUND"
            )

        if order.customer_profile_id != profile.id:
            raise UnprocessableEntityError(
                message="You can only review orders placed by your account.",
                error_code="ORDER_OWNERSHIP_MISMATCH",
            )

        allowed_statuses = ("COMPLETED", "DELIVERED")
        if order.status.upper() not in allowed_statuses:
            raise UnprocessableEntityError(
                message="Reviews can only be submitted for completed orders.",
                error_code="ORDER_NOT_COMPLETED",
            )

        # 3. Duplicate review check
        existing_review = await self.review_repo.get_by_order_id(req.order_id)
        if existing_review:
            raise ConflictError(
                message="A review has already been submitted for this order.",
                error_code="REVIEW_ALREADY_EXISTS",
            )

        # 4. Rating range check (INV-REV-001)
        if req.rating < 1 or req.rating > 5:
            raise UnprocessableEntityError(
                message="Rating must be an integer between 1 and 5.",
                error_code="INVALID_RATING_RANGE",
            )

        review = Review(
            order_id=req.order_id,
            customer_profile_id=profile.id,
            branch_id=order.branch_id,
            rating=req.rating,
            comment=req.comment,
            is_hidden=False,
        )

        created = await self.review_repo.create_review(review)
        await self.session.commit()
        return ReviewResponse.model_validate(created)

    async def get_branch_reviews(
        self, branch_id: uuid.UUID, include_hidden: bool = False
    ) -> list[ReviewResponse]:
        reviews = await self.review_repo.get_branch_reviews(
            branch_id=branch_id, include_hidden=include_hidden
        )
        return [ReviewResponse.model_validate(r) for r in reviews]

    async def get_branch_rating_summary(
        self, branch_id: uuid.UUID
    ) -> RestaurantRatingSummary:
        summary_dict = await self.review_repo.get_branch_rating_summary(branch_id)
        return RestaurantRatingSummary(**summary_dict)

    async def get_review(self, review_id: uuid.UUID) -> ReviewResponse:
        review = await self.review_repo.get_by_id(review_id)
        if not review:
            raise EntityNotFoundError(
                message="Review not found.", error_code="REVIEW_NOT_FOUND"
            )
        return ReviewResponse.model_validate(review)

    async def reply_to_review(
        self, review_id: uuid.UUID, req: ReviewReply
    ) -> ReviewResponse:
        review = await self.review_repo.get_by_id(review_id)
        if not review:
            raise EntityNotFoundError(
                message="Review not found.", error_code="REVIEW_NOT_FOUND"
            )

        updated = await self.review_repo.update_review(
            review, {"merchant_reply": req.merchant_reply}
        )
        await self.session.commit()
        return ReviewResponse.model_validate(updated)

    async def moderate_review(
        self, review_id: uuid.UUID, req: ReviewModerateRequest
    ) -> ReviewResponse:
        review = await self.review_repo.get_by_id(review_id)
        if not review:
            raise EntityNotFoundError(
                message="Review not found.", error_code="REVIEW_NOT_FOUND"
            )

        updated = await self.review_repo.update_review(
            review, {"is_hidden": req.is_hidden}
        )
        await self.session.commit()
        return ReviewResponse.model_validate(updated)

    async def delete_review(self, review_id: uuid.UUID) -> None:
        review = await self.review_repo.get_by_id(review_id)
        if not review:
            raise EntityNotFoundError(
                message="Review not found.", error_code="REVIEW_NOT_FOUND"
            )

        await self.review_repo.delete_review(review_id)
        await self.session.commit()
