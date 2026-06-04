"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    startup_trace.py

Description:
    Shared helper for appending timestamped lines to a startup trace log.

Functions:
    append_startup_trace_line:
        Append one timestamped line to the given trace file path.

Dependencies:
    datetime
    pathlib
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def append_startup_trace_line(trace_path: Path, message: str) -> None:
    """
    Append one timestamped line to a startup trace file.

    Creates the parent directory if it does not yet exist.  Each line is
    written with an ISO-8601 timestamp at seconds precision.

    Parameters:
        trace_path:
            Destination file path for the trace log.
        message:
            Trace message to append.

    Raises:
        OSError:
            Propagated to the caller so that write failures remain
            diagnosable.  Callers that intentionally suppress failures may
            catch ``OSError`` themselves.
    """
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec='seconds')
    with trace_path.open('a', encoding='utf-8') as handle:
        handle.write(f'[{timestamp}] {message}\n')
