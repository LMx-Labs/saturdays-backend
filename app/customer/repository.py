import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.customer.models import CustomerAddress, CustomerFavorite, CustomerProfile


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
    async def update_profile(self, profile: CustomerProfile, update_data: dict) -> CustomerProfile:
        pass

    @abstractmethod
    async def get_addresses(self, customer_profile_id: uuid.UUID) -> Sequence[CustomerAddress]:
        pass

    @abstractmethod
    async def get_address_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None:
        pass

    @abstractmethod
    async def create_address(self, address: CustomerAddress) -> CustomerAddress:
        pass

    @abstractmethod
    async def update_address(self, address: CustomerAddress, update_data: dict) -> CustomerAddress:
        pass

    @abstractmethod
    async def clear_primary_addresses(self, customer_profile_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def delete_address(self, address_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def get_favorites(self, customer_profile_id: uuid.UUID) -> Sequence[CustomerFavorite]:
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
    async def remove_favorite(self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        pass


class CustomerRepository(CustomerRepositoryInterface):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> CustomerProfile | None:
        stmt = select(CustomerProfile).where(
            CustomerProfile.id == customer_id, CustomerProfile.deleted_at.is_(None)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

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

    async def update_profile(self, profile: CustomerProfile, update_data: dict) -> CustomerProfile:
        for key, val in update_data.items():
            if hasattr(profile, key) and val is not None:
                setattr(profile, key, val)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_addresses(self, customer_profile_id: uuid.UUID) -> Sequence[CustomerAddress]:
        stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.customer_profile_id == customer_profile_id,
                CustomerAddress.deleted_at.is_(None),
            )
            .order_by(CustomerAddress.is_primary.desc(), CustomerAddress.created_at.desc())
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

    async def update_address(self, address: CustomerAddress, update_data: dict) -> CustomerAddress:
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

    async def get_favorites(self, customer_profile_id: uuid.UUID) -> Sequence[CustomerFavorite]:
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

    async def remove_favorite(self, customer_profile_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        stmt = delete(CustomerFavorite).where(
            CustomerFavorite.customer_profile_id == customer_profile_id,
            CustomerFavorite.branch_id == branch_id,
        )
        await self.session.execute(stmt)
