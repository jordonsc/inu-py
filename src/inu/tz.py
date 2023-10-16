import re
import time
from datetime import datetime, date, timezone

from .error import BadRequest


def to_str(src: str) -> str:
    """
    Takes an input and converts it to a NATS-expected timestamp in the format "2023-09-13T10:17:59Z".

    Valid inputs relative to current time:
        4s
        3m4s
        20h3m4s
        82d20h3m4s

    Valid absolute inputs:
        2023-04-02
        2023-04-02T20:04
        2023-04-02T20:04:30
        2023-04-02T20:04:30.343

    Today-specific time:
        20:04
        20:04:30
        20:04:30.123

    Absolute formats MUST be in UTC. No time zone should be included.
    """
    src = src.replace(" ", "").upper()
    if src[-1:] == "Z":
        src = src[:-1]

    # Absolute dates
    if re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", src):
        return f"{src}T00:00:00Z"

    if re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}$", src):
        return f"{src}:00Z"

    if re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", src):
        return f"{src}Z"

    if re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{1,6}$", src):
        return f"{src}Z"

    # Time relative to today
    if re.match("^[0-9]{2}:[0-9]{2}$", src):
        return f"{date.today().strftime('%Y-%m-%d')}T{src}:00Z"

    if re.match("^[0-9]{2}:[0-9]{2}:[0-9]{2}$", src):
        return f"{date.today().strftime('%Y-%m-%d')}T{src}Z"

    if re.match("^[0-9]{2}:[0-9]{2}:[0-9]{2}\\.[0-9]{1,6}$", src):
        return f"{date.today().strftime('%Y-%m-%d')}T{src}Z"

    # Relative times
    cursor = time.time()
    history = []
    parts = re.findall(r"[0-9]+[A-Z]", src)

    recon = "".join(parts)
    if recon != src or len(parts) == 0:
        raise BadRequest(f"Invalid date format: {src}")

    for part in parts:
        mod = part[-1:]
        offset = int(part[:-1])

        if mod in history:
            raise BadRequest(f"Duplicate time modifier: {mod}")

        if not offset:
            raise BadRequest(f"Invalid time offset: {part[:-1]}")

        history.append(mod)

        if mod == "S":
            cursor = cursor - offset
        elif mod == "M":
            cursor = cursor - (offset * 60)
        elif mod == "H":
            cursor = cursor - (offset * 3600)
        elif mod == "D":
            cursor = cursor - (offset * 86400)

    if cursor == time.time():
        # not entirely sure how this can happen, but just in case -
        raise BadRequest(f"Invalid date format: {src}")

    return datetime.fromtimestamp(cursor, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
