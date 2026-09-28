"""Conservative one-URL downloader for approved public G2 sources."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_DOMAINS = {"vanban.chinhphu.vn", "vpub.hochiminhcity.gov.vn"}
USER_AGENT = "HanhChinhCong-G2-public-data/1.0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--allow-domain", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-bytes", type=int, default=20_000_000)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    raw_root = (root / "data/demo_public/raw").resolve()
    output = (root / args.output).resolve()
    parsed = urlsplit(args.url)
    allowed = DEFAULT_DOMAINS | {item.lower() for item in args.allow_domain}
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed
        or parsed.username
        or parsed.password
    ):
        print("DOWNLOAD_REJECTED: URL must be HTTPS on an allowlisted official domain.")
        return 2
    if not output.is_relative_to(raw_root) or output.exists():
        print(
            "DOWNLOAD_REJECTED: output must be a new file under data/demo_public/raw."
        )
        return 2
    if args.timeout <= 0 or args.max_bytes <= 0:
        print("DOWNLOAD_REJECTED: timeout and max-bytes must be positive.")
        return 2

    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    robots = urllib.robotparser.RobotFileParser()
    robots.set_url(robots_url)
    try:
        robots.read()
    except OSError:
        print(
            "DOWNLOAD_BLOCKED: robots.txt could not be verified; use an approved manual export."
        )
        return 3
    if not robots.can_fetch(USER_AGENT, args.url):
        print("DOWNLOAD_BLOCKED: robots.txt does not allow this URL.")
        return 3

    request = Request(args.url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with urlopen(request, timeout=args.timeout) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname not in allowed:
                raise ValueError("redirected outside allowlist")
            with tempfile.NamedTemporaryFile(delete=False, dir=output.parent) as handle:
                temporary = handle.name
                total = 0
                while chunk := response.read(64 * 1024):
                    total += len(chunk)
                    if total > args.max_bytes:
                        raise ValueError("response exceeds max-bytes")
                    handle.write(chunk)
        os.replace(temporary, output)
        temporary = None
    except (OSError, ValueError) as exc:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        print(f"DOWNLOAD_FAILED: {type(exc).__name__}")
        return 4

    value = hashlib.sha256(output.read_bytes()).hexdigest()
    print(
        f"DOWNLOAD_OK path={output.relative_to(root).as_posix()} bytes={output.stat().st_size}"
    )
    print(f"sha256={value}")
    print(
        "NEXT: add manifest metadata and obtain a second human review; download is not approval."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
