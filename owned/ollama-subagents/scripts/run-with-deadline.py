#!/usr/bin/env python3
import math
import os
import signal
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: run-with-deadline.py SECONDS COMMAND [ARG ...]", file=sys.stderr)
        return 2

    try:
        seconds = float(sys.argv[1])
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError
    except ValueError:
        print(f"invalid deadline: {sys.argv[1]}", file=sys.stderr)
        return 2

    process = subprocess.Popen(sys.argv[2:], start_new_session=True)
    try:
        return process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        print(f"timed out after {seconds:g} seconds", file=sys.stderr)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
