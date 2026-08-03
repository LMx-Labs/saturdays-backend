import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.order.models import Order
from app.review.models import Review


class ReviewRepositoryInterface(ABC):
    @abstractmethod
    async def create_review(self, review: Review) -> Review:
        pass

    @abstractmethod
    async def get_by_id(self, review_id: uuid.UUID) -> Review | None:
        pass

    @abstractmethod
    async def get_by_order_id(self, order_id: uuid.UUID) -> Review | None:
        pass

    @abstractmethod
    async def get_branch_reviews(
        self, branch_id: uuid.UUID, include_hidden: bool = False
    ) -> Sequence[Review]:
        pass

    @abstractmethod
    async def get_branch_rating_summary(self, branch_id: uuid.UUID) -> dict:
        pass

    @abstractmethod
    async def update_review(self, review: Review, update_data: dict) -> Review:
        pass

    @abstractmethod
    async def delete_review(self, review_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def get_order_by_id(self, order_id: uuid.UUID) -> Order | None:
        pass


class ReviewRepository(ReviewRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_review(self, review: Review) -> Review:
        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def get_by_id(self, review_id: uuid.UUID) -> Review | None:
        stmt = select(Review).where(Review.id == review_id, Review.deleted_at.is_(None))
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_order_id(self, order_id: uuid.UUID) -> Review | None:
        stmt = select(Review).where(
            Review.order_id == order_id, Review.deleted_at.is_(None)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_branch_reviews(
        self, branch_id: uuid.UUID, include_hidden: bool = False
    ) -> Sequence[Review]:
        stmt = select(Review).where(
            Review.branch_id == branch_id, Review.deleted_at.is_(None)
        )
        if not include_hidden:
            stmt = stmt.where(Review.is_hidden.is_(False))
        stmt = stmt.order_by(Review.created_at.desc())
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_branch_rating_summary(self, branch_id: uuid.UUID) -> dict:
        stmt = (
            select(Review.rating, func.count(Review.id))
            .where(
                Review.branch_id == branch_id,
                Review.deleted_at.is_(None),
                Review.is_hidden.is_(False),
            )
            .group_by(Review.rating)
        )
        res = await self.session.execute(stmt)
        rows = res.all()

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total_count = 0
        total_sum = 0

        for rating, count in rows:
            if rating in distribution:
                distribution[rating] = count
                total_count += count
                total_sum += rating * count

        avg_rating = round(total_sum / total_count, 2) if total_count > 0 else 0.0

        return {
            "branch_id": branch_id,
            "average_rating": avg_rating,
            "total_reviews": total_count,
            "rating_distribution": distribution,
        }

    async def update_review(self, review: Review, update_data: dict) -> Review:
        for key, val in update_data.items():
            if hasattr(review, key) and val is not None:
                setattr(review, key, val)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def delete_review(self, review_id: uuid.UUID) -> None:
        review = await self.get_by_id(review_id)
        if review:
            review.deleted_at = func.now()
            await self.session.flush()

    async def get_order_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = select(Order).where(Order.id == order_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
