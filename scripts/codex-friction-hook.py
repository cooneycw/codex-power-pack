#!/usr/bin/env python3
"""Codex hook entrypoint for fail-open friction telemetry."""

from __future__ import annotations

import sys

from lib.friction.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["hook", *sys.argv[1:]]))
