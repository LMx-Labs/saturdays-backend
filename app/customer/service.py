import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, EntityNotFoundError
from app.customer.models import CustomerAddress, CustomerFavorite, CustomerProfile
from app.customer.repository import CustomerRepositoryInterface
from app.customer.schemas import (
    CustomerAddressCreate,
    CustomerAddressResponse,
    CustomerFavoriteResponse,
    CustomerProfileResponse,
    CustomerProfileUpdate,
)


class CustomerServiceInterface(ABC):
    @abstractmethod
    async def get_or_create_profile(
        self, user_id: uuid.UUID, default_name: str = "Customer"
    ) -> CustomerProfileResponse:
        pass

    @abstractmethod
    async def update_profile(
        self, user_id: uuid.UUID, req: CustomerProfileUpdate
    ) -> CustomerProfileResponse:
        pass

    @abstractmethod
    async def get_addresses(self, user_id: uuid.UUID) -> list[CustomerAddressResponse]:
        pass

    @abstractmethod
    async def add_address(
        self, user_id: uuid.UUID, req: CustomerAddressCreate
    ) -> CustomerAddressResponse:
        pass

    @abstractmethod
    async def set_primary_address(
        self, user_id: uuid.UUID, address_id: uuid.UUID
    ) -> CustomerAddressResponse:
        pass

    @abstractmethod
    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def get_favorites(self, user_id: uuid.UUID) -> list[CustomerFavoriteResponse]:
        pass

    @abstractmethod
    async def add_favorite(
        self, user_id: uuid.UUID, branch_id: uuid.UUID
    ) -> CustomerFavoriteResponse:
        pass

    @abstractmethod
    async def remove_favorite(self, user_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        pass


class CustomerService(CustomerServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        customer_repo: CustomerRepositoryInterface,
    ):
        self.session = session
        self.customer_repo = customer_repo

    async def get_or_create_profile(
        self, user_id: uuid.UUID, default_name: str = "Customer"
    ) -> CustomerProfileResponse:
        # INV-CUST-001: Strict 1:1 user mapping
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            profile = CustomerProfile(
                user_id=user_id,
                full_name=default_name,
                phone_number=None,
            )
            profile = await self.customer_repo.create_profile(profile)
            await self.session.commit()
        return CustomerProfileResponse.model_validate(profile)

    async def update_profile(
        self, user_id: uuid.UUID, req: CustomerProfileUpdate
    ) -> CustomerProfileResponse:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            profile = CustomerProfile(
                user_id=user_id,
                full_name=req.full_name or "Customer",
                phone_number=req.phone_number,
            )
            profile = await self.customer_repo.create_profile(profile)
        else:
            update_data = req.model_dump(exclude_unset=True)
            profile = await self.customer_repo.update_profile(profile, update_data)

        await self.session.commit()
        return CustomerProfileResponse.model_validate(profile)

    async def get_addresses(self, user_id: uuid.UUID) -> list[CustomerAddressResponse]:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            return []
        addresses = await self.customer_repo.get_addresses(profile.id)
        return [CustomerAddressResponse.model_validate(a) for a in addresses]

    async def add_address(
        self, user_id: uuid.UUID, req: CustomerAddressCreate
    ) -> CustomerAddressResponse:
        # Ensure profile exists
        profile_resp = await self.get_or_create_profile(user_id)
        profile_id = profile_resp.id

        existing_addresses = await self.customer_repo.get_addresses(profile_id)

        # INV-CUST-002 (Primary Address Constraint):
        # If this is the first address or req.is_primary is True, clear existing primaries
        is_first = len(existing_addresses) == 0
        should_be_primary = req.is_primary or is_first

        if should_be_primary:
            await self.customer_repo.clear_primary_addresses(profile_id)

        address = CustomerAddress(
            customer_profile_id=profile_id,
            address_line=req.address_line,
            building_name=req.building_name,
            campus_zone=req.campus_zone,
            is_primary=should_be_primary,
        )

        created_address = await self.customer_repo.create_address(address)
        await self.session.commit()
        return CustomerAddressResponse.model_validate(created_address)

    async def set_primary_address(
        self, user_id: uuid.UUID, address_id: uuid.UUID
    ) -> CustomerAddressResponse:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            raise EntityNotFoundError(
                message="Customer profile not found.", error_code="CUSTOMER_NOT_FOUND"
            )

        address = await self.customer_repo.get_address_by_id(address_id)
        if not address or address.customer_profile_id != profile.id:
            raise EntityNotFoundError(
                message="Address not found for this customer.",
                error_code="ADDRESS_NOT_FOUND",
            )

        await self.customer_repo.clear_primary_addresses(profile.id)
        updated_address = await self.customer_repo.update_address(
            address, {"is_primary": True}
        )
        await self.session.commit()
        return CustomerAddressResponse.model_validate(updated_address)

    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            raise EntityNotFoundError(
                message="Customer profile not found.", error_code="CUSTOMER_NOT_FOUND"
            )

        address = await self.customer_repo.get_address_by_id(address_id)
        if not address or address.customer_profile_id != profile.id:
            raise EntityNotFoundError(
                message="Address not found for this customer.",
                error_code="ADDRESS_NOT_FOUND",
            )

        was_primary = address.is_primary
        await self.customer_repo.delete_address(address_id)

        # Enforce INV-CUST-002: if deleted address was primary, make the most recent remaining address primary
        if was_primary:
            remaining = await self.customer_repo.get_addresses(profile.id)
            if remaining:
                await self.customer_repo.update_address(
                    remaining[0], {"is_primary": True}
                )

        await self.session.commit()

    async def get_favorites(self, user_id: uuid.UUID) -> list[CustomerFavoriteResponse]:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            return []
        favorites = await self.customer_repo.get_favorites(profile.id)
        return [CustomerFavoriteResponse.model_validate(f) for f in favorites]

    async def add_favorite(
        self, user_id: uuid.UUID, branch_id: uuid.UUID
    ) -> CustomerFavoriteResponse:
        profile_resp = await self.get_or_create_profile(user_id)
        profile_id = profile_resp.id

        # INV-CUST-003 (Favorite Uniqueness)
        existing = await self.customer_repo.get_favorite(profile_id, branch_id)
        if existing:
            raise ConflictError(
                message="Branch already added to customer favorites.",
                error_code="FAVORITE_ALREADY_EXISTS",
            )

        favorite = CustomerFavorite(
            customer_profile_id=profile_id,
            branch_id=branch_id,
        )
        created_fav = await self.customer_repo.add_favorite(favorite)
        await self.session.commit()
        return CustomerFavoriteResponse.model_validate(created_fav)

    async def remove_favorite(self, user_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            return

        existing = await self.customer_repo.get_favorite(profile.id, branch_id)
        if not existing:
            raise EntityNotFoundError(
                message="Favorite branch bookmark not found.",
                error_code="FAVORITE_NOT_FOUND",
            )

        await self.customer_repo.remove_favorite(profile.id, branch_id)
        await self.session.commit()
