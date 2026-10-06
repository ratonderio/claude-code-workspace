"""Effort buckets to relative workload points.

Points are a *relative* measure for questions like "62% of the remaining workload is in six
large tasks". They are not hours. Tasks without an effort estimate contribute zero points and
are counted separately by reports (decision D22).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from family_hq.domain.enums import Effort

DEFAULT_POINTS: dict[Effort, int] = {
    Effort.XS: 1,
    Effort.S: 2,
    Effort.M: 4,
    Effort.L: 8,
    Effort.XL: 16,
}


def points_for(effort: Effort | None, mapping: Mapping[Effort, int] = DEFAULT_POINTS) -> int:
    return 0 if effort is None else mapping[effort]


def total_points(
    efforts: Iterable[Effort | None], mapping: Mapping[Effort, int] = DEFAULT_POINTS
) -> int:
    return sum(points_for(e, mapping) for e in efforts)
