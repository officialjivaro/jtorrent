#!/usr/bin/env python3
"""Build the static JTorrent JSON backend."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repository root without installing the package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from jtorrent_backend.builder import build_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build JTorrent static backend data")
    parser.add_argument("--config", default="config/sources.yml", help="Path to YAML config")
    parser.add_argument("--offline", action="store_true", help="Do not perform network requests; manual items only")
    parser.add_argument("--strict", action="store_true", help="Fail the build on source fetch errors")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_index(Path(args.config), offline=args.offline, strict=args.strict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
