"""Starts the operator app on this computer only (127.0.0.1), and opens it in the browser.

Run it from the folder that holds the site's site-agent.toml, or pass --site. Nothing is reachable from other computers.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

from site_agent import __version__


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from site_agent.errors import SiteAgentError
    from site_agent.web.app import create_app

    parser = argparse.ArgumentParser(prog="site-agent-app", description="The CIR website operator app.")
    parser.add_argument("--site", type=Path, default=Path("."), help="folder of the website (default: current folder)")
    parser.add_argument("--port", type=int, default=8765, help="port on this computer (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        app = create_app(args.site)
    except SiteAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{args.port}/"
    print(f"The operator app is running at {url}. Press Ctrl+C to stop it.")
    if not args.no_browser:
        threading.Thread(target=_open_later, args=(url,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def _open_later(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


if __name__ == "__main__":
    raise SystemExit(main())
