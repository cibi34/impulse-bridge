"""Query-parameter parsing shared by the Impulse API and the web app API."""


def pagination(o: str | None, c: str | None) -> tuple[int, int | None]:
    """Offset and count per the Impulse spec: both are optional positive
    integers, and "in case of illegal values the entire result set shall be
    returned" — so anything unparsable or out of range means no pagination."""
    try:
        offset = int(o) if o else 0
        count = int(c) if c else None
    except ValueError:
        return 0, None
    if offset < 0 or (count is not None and count < 1):
        return 0, None
    return offset, count
