import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.models import User
from app.customer.models import CustomerAddress, CustomerFavorite, CustomerProfile
from app.order.models import Order


class CustomerRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, customer_id: uuid.UUID) -> CustomerProfile | None:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> CustomerProfile | None:
        pass

    @abstractmethod
    async def create_profile(self, profile: CustomerProfile) -> CustomerProfile:
        pass

    @abstractmethod
    async def update_profile(
        self, profile: CustomerProfile, update_data: dict
    ) -> CustomerProfile:
        pass

    @abstractmethod
    async def list_customers(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[CustomerProfile]:
        pass

    @abstractmethod
    async def get_customer_order_stats(
        self, customer_profile_id: uuid.UUID
    ) -> tuple[int, float]:
        pass

    @abstractmethod
    async def get_addresses(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[CustomerAddress]:
        pass

    @abstractmethod
    async def get_address_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None:
        pass

    @abstractmethod
    async def create_address(self, address: CustomerAddress) -> CustomerAddress:
        pass

    @abstractmethod
    async def update_address(
        self, address: CustomerAddress, update_data: dict
    ) -> CustomerAddress:
        pass

    @abstractmethod
    async def clear_primary_addresses(self, customer_profile_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def delete_address(self, address_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def get_favorites(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[CustomerFavorite]:
        pass

    @abstractmethod
    async def get_favorite(
        self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID
    ) -> CustomerFavorite | None:
        pass

    @abstractmethod
    async def add_favorite(self, favorite: CustomerFavorite) -> CustomerFavorite:
        pass

    @abstractmethod
    async def remove_favorite(
        self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID
    ) -> None:
        pass


class CustomerRepository(CustomerRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> CustomerProfile | None:
        stmt = (
            select(CustomerProfile)
            .options(joinedload(CustomerProfile.user))
            .where(
                CustomerProfile.id == customer_id, CustomerProfile.deleted_at.is_(None)
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_customers(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[CustomerProfile]:
        stmt = (
            select(CustomerProfile)
            .join(CustomerProfile.user)
            .options(joinedload(CustomerProfile.user))
            .where(CustomerProfile.deleted_at.is_(None))
        )
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    CustomerProfile.full_name.ilike(search_pattern),
                    CustomerProfile.phone_number.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                )
            )
        stmt = stmt.order_by(CustomerProfile.created_at.desc()).offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_customer_order_stats(
        self, customer_profile_id: uuid.UUID
    ) -> tuple[int, float]:
        stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0.0),
        ).where(Order.customer_profile_id == customer_profile_id)
        res = await self.session.execute(stmt)
        row = res.one()
        return (row[0] or 0, float(row[1] or 0.0))

    async def get_by_user_id(self, user_id: uuid.UUID) -> CustomerProfile | None:
        stmt = select(CustomerProfile).where(
            CustomerProfile.user_id == user_id, CustomerProfile.deleted_at.is_(None)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_profile(self, profile: CustomerProfile) -> CustomerProfile:
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def update_profile(
        self, profile: CustomerProfile, update_data: dict
    ) -> CustomerProfile:
        for key, val in update_data.items():
            if hasattr(profile, key) and val is not None:
                setattr(profile, key, val)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_addresses(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[CustomerAddress]:
        stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.customer_profile_id == customer_profile_id,
                CustomerAddress.deleted_at.is_(None),
            )
            .order_by(
                CustomerAddress.is_primary.desc(), CustomerAddress.created_at.desc()
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_address_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None:
        stmt = select(CustomerAddress).where(
            CustomerAddress.id == address_id, CustomerAddress.deleted_at.is_(None)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_address(self, address: CustomerAddress) -> CustomerAddress:
        self.session.add(address)
        await self.session.flush()
        await self.session.refresh(address)
        return address

    async def update_address(
        self, address: CustomerAddress, update_data: dict
    ) -> CustomerAddress:
        for key, val in update_data.items():
            if hasattr(address, key) and val is not None:
                setattr(address, key, val)
        await self.session.flush()
        await self.session.refresh(address)
        return address

    async def clear_primary_addresses(self, customer_profile_id: uuid.UUID) -> None:
        stmt = (
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_profile_id == customer_profile_id,
                CustomerAddress.deleted_at.is_(None),
            )
            .values(is_primary=False)
        )
        await self.session.execute(stmt)

    async def delete_address(self, address_id: uuid.UUID) -> None:
        stmt = delete(CustomerAddress).where(CustomerAddress.id == address_id)
        await self.session.execute(stmt)

    async def get_favorites(
        self, customer_profile_id: uuid.UUID
    ) -> Sequence[CustomerFavorite]:
        stmt = (
            select(CustomerFavorite)
            .where(CustomerFavorite.customer_profile_id == customer_profile_id)
            .order_by(CustomerFavorite.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_favorite(
        self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID
    ) -> CustomerFavorite | None:
        stmt = select(CustomerFavorite).where(
            CustomerFavorite.customer_profile_id == customer_profile_id,
            CustomerFavorite.branch_id == branch_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_favorite(self, favorite: CustomerFavorite) -> CustomerFavorite:
        self.session.add(favorite)
        await self.session.flush()
        await self.session.refresh(favorite)
        return favorite

    async def remove_favorite(
        self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID
    ) -> None:
        stmt = delete(CustomerFavorite).where(
            CustomerFavorite.customer_profile_id == customer_profile_id,
            CustomerFavorite.branch_id == branch_id,
        )
        await self.session.execute(stmt)
