"""Small shared helpers."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence


def human_bytes(size: Optional[float]) -> str:
    """Format a byte count for display (base-1024)."""
    if size is None:
        return "?"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024.0 or unit == "TiB":
            precision = 0 if unit == "B" else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1024.0
    raise AssertionError("unreachable")


def parse_year_spec(spec: str, valid: Optional[Iterable[int]] = None) -> List[int]:
    """Parse a year selection such as ``"1992-1995,2000,2010-2012"``.

    Returns a sorted, de-duplicated list. When ``valid`` is given, any year
    outside it raises ``ValueError``.
    """
    years: set[int] = set()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" in token.lstrip("-"):
            start_text, _, end_text = token.partition("-")
            try:
                start, end = int(start_text), int(end_text)
            except ValueError:
                raise ValueError(f"invalid year range: {token!r}") from None
            if start > end:
                raise ValueError(f"reversed year range: {token!r}")
            years.update(range(start, end + 1))
        else:
            try:
                years.add(int(token))
            except ValueError:
                raise ValueError(f"invalid year: {token!r}") from None

    if not years:
        raise ValueError(f"no years selected from {spec!r}")

    if valid is not None:
        allowed = set(valid)
        unknown = sorted(years - allowed)
        if unknown:
            bounds = f"{min(allowed)}-{max(allowed)}" if allowed else "none"
            raise ValueError(
                f"year(s) not in dataset ({bounds}): "
                + ", ".join(str(y) for y in unknown)
            )
    return sorted(years)


def format_table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> str:
    """Render a simple left-aligned text table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append(
            "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip()
        )
    return "\n".join(lines)
