from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "Customer"
    KITCHEN_STAFF = "KitchenStaff"
    BRANCH_MANAGER = "BranchManager"
    MERCHANT_OWNER = "MerchantOwner"
    PLATFORM_ADMIN = "PlatformAdmin"


CANONICAL_ROLES = frozenset(role.value for role in Role)
STAFF_ROLES = frozenset({Role.KITCHEN_STAFF.value, Role.BRANCH_MANAGER.value})
PRIVILEGED_ROLES = CANONICAL_ROLES - {Role.CUSTOMER.value}


def normalize_role(role: str) -> str:
    value = role.strip()
    if value == "Admin":
        return Role.PLATFORM_ADMIN.value
    for canonical in CANONICAL_ROLES:
        if canonical.casefold() == value.casefold():
            return canonical
    raise ValueError(f"Unknown role: {role}")
