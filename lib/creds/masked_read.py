"""Read repository text through the shared secret masker before emitting it."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from .masking import OutputMasker


def read_masked_paths(
    paths: Sequence[str | Path],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    masker: OutputMasker | None = None,
) -> int:
    """Mask selected files in memory and emit only the sanitized result."""
    output_masker = masker or OutputMasker()
    output_stream = stdout if stdout is not None else sys.stdout
    error_stream = stderr if stderr is not None else sys.stderr
    multiple = len(paths) > 1
    rendered: list[tuple[str, str]] = []

    for index, raw_path in enumerate(paths):
        path = Path(raw_path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(
                f"masked-read: file {index + 1} could not be read",
                file=error_stream,
            )
            return 2

        masked = output_masker.mask(text)
        masked_path = output_masker.mask(str(path))
        if _has_detection_only_match(masked, output_masker) or _has_detection_only_match(
            masked_path, output_masker
        ):
            print(
                f"masked-read: file {index + 1} still contains an unmaskable "
                "secret-shaped value; no content was emitted",
                file=error_stream,
            )
            return 3
        rendered.append((masked_path, masked))

    for index, (masked_path, masked) in enumerate(rendered):
        if multiple:
            if index:
                output_stream.write("\n")
            output_stream.write(f"==> {masked_path} <==\n")
        output_stream.write(masked)
        if masked and not masked.endswith("\n"):
            output_stream.write("\n")

    return 0


def _has_detection_only_match(text: str, masker: OutputMasker) -> bool:
    return any(
        replacement is None and re.search(pattern, text, re.IGNORECASE)
        for pattern, replacement in masker.patterns
    )
