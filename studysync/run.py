"""Backward-compatible Host launcher.

The dedicated Host entrypoint is `host.py`, but this file still starts the
Host so existing workflows keep working.
"""

from host import app, main


if __name__ == "__main__":
    main()