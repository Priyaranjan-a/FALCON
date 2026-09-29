"""Entry point of the bundled FALCON engine (built with PyInstaller).

``freeze_support`` must run first: scan workers are separate processes started
by re-running this executable, and it routes them to their worker code.
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from falcon.__main__ import main

    sys.exit(main(sys.argv[1:] or ["desktop"]))
