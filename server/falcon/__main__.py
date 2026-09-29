"""Command line entry point.

    python -m falcon                     # serve the platform
    python -m falcon serve --demo        # first run: seed a demo organisation, admin account and scans
    python -m falcon serve --reload      # development server with auto-reload
    python -m falcon migrate             # apply schema migrations
    python -m falcon revision "message"  # autogenerate a migration (development)
    python -m falcon recover-owner       # owner locked out: print a one-time sign-in link
    python -m falcon desktop             # engine for the desktop app (started by the shell)

Offline, for pipelines (no server, no database):

    python -m falcon scan PATH --format sarif --fail-on high
    python -m falcon keygen --out keys
    python -m falcon verify cbom.dsse.json --key keys/falcon-attestation.pub.pem
"""
from __future__ import annotations

import argparse

from .settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="falcon", description="FALCON server")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="run the API and console")
    serve.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    serve.add_argument("--demo", action="store_true",
                       help="on a fresh installation, create a demo organisation, admin account, systems and scans")
    sub.add_parser("migrate", help="apply database migrations")
    rev = sub.add_parser("revision", help="autogenerate a migration")
    rev.add_argument("message")
    sub.add_parser("recover-owner", help="reset the owner's access and print a one-time sign-in link")
    sub.add_parser("desktop", help="run the engine for the desktop app (started by the desktop shell)")
    from .cli import add_commands

    add_commands(sub)
    args = parser.parse_args(argv)

    if getattr(args, "handler", None):
        return args.handler(args)

    if args.command == "desktop":
        from .desktop import run

        return run()

    if args.command == "recover-owner":
        from .domains.identity.service import recover_owner
        from .kernel.database import get_sessionmaker
        from .kernel.migrate import upgrade

        upgrade()
        settings = get_settings()
        with get_sessionmaker()() as db:
            owner, invitation, secret = recover_owner(db)
        print(f"Access reset for {owner.name} <{owner.email}>. All their sessions and tokens were revoked.")
        print(f"One-time link (valid until {invitation.expires_at:%Y-%m-%d %H:%M} UTC):")
        print(f"  http://{settings.host}:{settings.port}/activate#{secret}")
        return 0

    if args.command == "migrate":
        from .kernel.migrate import upgrade

        upgrade()
        return 0
    if args.command == "revision":
        from .kernel.migrate import revision

        revision(args.message)
        return 0

    import os

    import uvicorn

    if getattr(args, "demo", False):
        # Read by the app factory (it may run in a reloader child process).
        os.environ["FALCON_DEMO"] = "true"
        get_settings.cache_clear()
    settings = get_settings()
    uvicorn.run(
        "falcon.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=bool(getattr(args, "reload", False)),
        proxy_headers=False,
        server_header=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
