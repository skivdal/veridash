"""Strict single-range parsing for authorized media playback."""

from dataclasses import dataclass


class InvalidRangeError(ValueError):
    """A Range header cannot be satisfied for the current representation."""


@dataclass(frozen=True, slots=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_byte_range(value: str | None, *, size_bytes: int) -> ByteRange | None:
    if value is None:
        return None
    if size_bytes <= 0 or not value.startswith("bytes="):
        raise InvalidRangeError

    specification = value.removeprefix("bytes=").strip()
    if "," in specification or "-" not in specification:
        raise InvalidRangeError
    start_text, end_text = specification.split("-", maxsplit=1)
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise InvalidRangeError
            start = max(size_bytes - suffix_length, 0)
            return ByteRange(start=start, end=size_bytes - 1)

        start = int(start_text)
        if start < 0 or start >= size_bytes:
            raise InvalidRangeError
        end = size_bytes - 1 if not end_text else int(end_text)
        if end < start:
            raise InvalidRangeError
        return ByteRange(start=start, end=min(end, size_bytes - 1))
    except ValueError as exception:
        raise InvalidRangeError from exception
