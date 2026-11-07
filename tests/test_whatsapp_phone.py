import pytest

from app.notification.phone import mask_phone, normalize_phone


@pytest.mark.parametrize(
    "typed",
    [
        "9876543210",
        "98765 43210",
        "98765-43210",
        "09876543210",
        "+91 98765 43210",
        "+919876543210",
        "919876543210",
        "0091 98765 43210",
        "(91) 98765 43210",
        "  +91-98765-43210  ",
    ],
)
def test_the_ways_people_write_an_indian_mobile_all_give_the_same_number(typed):
    assert normalize_phone(typed) == "919876543210"


@pytest.mark.parametrize(
    "typed",
    [
        None,
        "",
        "   ",
        "abc",
        "12345",  # far too short
        "98765432",  # nine digits missing one
        "5876543210",  # Indian mobiles start 6-9
        "987654321012",  # too long for a plain number
        "+91 12345 67890",  # +91 then a number that is not a mobile
        "04162223344",  # a landline
        "+0 98765 43210",
    ],
)
def test_anything_that_cannot_be_a_mobile_number_is_refused(typed):
    assert normalize_phone(typed) is None


def test_a_foreign_number_with_a_plus_is_accepted():
    assert normalize_phone("+1 415 555 2671") == "14155552671"
    assert normalize_phone("+44 7911 123456") == "447911123456"
    assert normalize_phone("0044 7911 123456") == "447911123456"


def test_another_home_country_can_be_configured():
    assert normalize_phone("14155552671", default_country_code="1") == "14155552671"
    assert normalize_phone("9876543210", default_country_code="1") is None


def test_the_log_form_hides_most_of_the_number():
    masked = mask_phone("919876543210")
    assert masked.endswith("210")
    assert "98765" not in masked
    assert masked.startswith("+91")
    assert mask_phone(None) == "(none)"
