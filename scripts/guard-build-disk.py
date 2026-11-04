"""Check free disk space and stop a development build near the reserve."""

import os
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path


GIB = 1024**3
DISK_RESERVE = 2 * GIB


def existing_parent(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path


def check_space(paths, report=False):
    free, path = min((shutil.disk_usage(path).free, path) for path in paths)
    if free <= DISK_RESERVE:
        print(
            f"Build stopped: {free / GIB:.2f} GiB free on {path}. "
            "Free more disk space before retrying (2 GiB reserve).",
            file=sys.stderr,
            flush=True,
        )
        return False
    if report:
        print(f"Available build disk: {free / GIB:.2f} GiB on {path}.")
        if free < 20 * GIB:
            print("Starting below the 20 GiB estimate. Build size is unmeasured.")
    return True


def stop_on_term(signum, _frame):
    raise SystemExit(128 + signum)


def main(command):
    cargo_home = os.environ.get("CARGO_HOME") or Path.home() / ".cargo"
    target = os.environ.get("CARGO_TARGET_DIR") or os.environ.get("CARGO_BUILD_TARGET_DIR") or "target"
    paths = {existing_parent(path) for path in (".", cargo_home, target)}
    if not check_space(paths, report=not command):
        return 1
    if not command:
        return 0

    signal.signal(signal.SIGTERM, stop_on_term)
    process = subprocess.Popen(command, start_new_session=True)
    try:
        while True:
            try:
                status = process.wait(timeout=2)
                return status if status >= 0 else 128 - status
            except subprocess.TimeoutExpired:
                if not check_space(paths):
                    return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if process.returncode is None:
            # Stop Cargo and its compiler subprocesses before they write more data.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except OSError as error:
        sys.exit(f"Build disk check could not continue: {error}")
