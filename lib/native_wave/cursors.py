"""Pure read-cursor reduction for durable native-wave event streams."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .event_types import CursorState, EventValidationError

MAX_CURSOR_SPAN = 10_000


def advance_cursor(
    current: CursorState,
    *,
    observed_sequences: Iterable[int],
    scanned_through: int,
) -> CursorState:
    """Return the deterministic cursor after one bounded scan.

    ``sparse_sequences`` records observed rows above the contiguous point;
    ``gaps`` records holes explicitly.  Seeing a missing sequence later closes
    its gap and may advance through already observed sparse rows.  This is only
    read evidence: it cannot produce assignment acceptance.
    """

    if scanned_through < current.highest_contiguous:
        raise EventValidationError("cursor scan cannot move backwards")
    if scanned_through - current.highest_contiguous > MAX_CURSOR_SPAN:
        raise EventValidationError("cursor scan span exceeds the bounded page size")

    observed = set(observed_sequences)
    if any(sequence <= 0 or sequence > scanned_through for sequence in observed):
        raise EventValidationError("observed cursor sequence is outside the scanned range")

    sparse = set(current.sparse_sequences)
    gaps = set(current.gaps)
    for sequence in observed:
        if sequence > current.highest_contiguous:
            sparse.add(sequence)
            gaps.discard(sequence)

    for sequence in range(current.highest_contiguous + 1, scanned_through + 1):
        if sequence not in sparse:
            gaps.add(sequence)

    highest = current.highest_contiguous
    while highest + 1 in sparse:
        highest += 1
        sparse.remove(highest)
        gaps.discard(highest)

    sparse = {sequence for sequence in sparse if sequence > highest}
    gaps = {sequence for sequence in gaps if sequence > highest}
    return replace(
        current,
        highest_contiguous=highest,
        sparse_sequences=tuple(sorted(sparse)),
        gaps=tuple(sorted(gaps)),
    )


def merge_cursor(current: CursorState, recovered: CursorState) -> CursorState:
    """Merge two observations for the exact same reader generation."""

    identity = (current.wave_id, current.role_id, current.thread_id, current.generation_id)
    other_identity = (recovered.wave_id, recovered.role_id, recovered.thread_id, recovered.generation_id)
    if identity != other_identity:
        raise EventValidationError("cannot merge cursors from different reader generations")
    highest = max(current.highest_contiguous, recovered.highest_contiguous)
    sparse = {sequence for sequence in current.sparse_sequences + recovered.sparse_sequences if sequence > highest}
    gaps = {sequence for sequence in current.gaps + recovered.gaps if sequence > highest}
    gaps.difference_update(sparse)

    while highest + 1 in sparse:
        highest += 1
        sparse.remove(highest)
        gaps.discard(highest)

    return replace(
        current,
        highest_contiguous=highest,
        sparse_sequences=tuple(sorted(sparse)),
        gaps=tuple(sorted(gaps)),
    )


__all__ = ["MAX_CURSOR_SPAN", "advance_cursor", "merge_cursor"]
