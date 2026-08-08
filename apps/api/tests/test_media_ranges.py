import pytest
from veridash_api.media_ranges import InvalidRangeError, parse_byte_range


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("bytes=0-9", (0, 9)),
        ("bytes=10-", (10, 99)),
        ("bytes=-10", (90, 99)),
        ("bytes=95-200", (95, 99)),
    ],
)
def test_parse_single_byte_ranges(
    header: str | None,
    expected: tuple[int, int] | None,
) -> None:
    parsed = parse_byte_range(header, size_bytes=100)
    actual = None if parsed is None else (parsed.start, parsed.end)
    assert actual == expected


@pytest.mark.parametrize(
    "header",
    ["items=0-1", "bytes=", "bytes=100-", "bytes=20-10", "bytes=-0", "bytes=0-1,5-6"],
)
def test_reject_invalid_or_multiple_ranges(header: str) -> None:
    with pytest.raises(InvalidRangeError):
        parse_byte_range(header, size_bytes=100)
