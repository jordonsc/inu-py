from .. import error


class Headers:
    PROTOCOL = "Protocol"
    STATUS_CODE = "Status"
    STATUS_DESC = "Description"


def parse_headers(data: bytes | str) -> dict:
    """
    Parse HTTP-style headers into a dict.
    """
    if isinstance(data, bytes) or isinstance(data, bytearray):
        data = data.decode()

    headers = {}
    data = data.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for line in data:
        if not line:
            continue

        # Standard header, split by colon
        parts = line.split(": ", 1)

        if len(parts) < 2:
            # This would be a 'status' line, eg:
            # NATS/1.0 100
            # NATS/1.0 100 Idle Heartbeat
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                headers[Headers.PROTOCOL] = parts[0]
                headers[Headers.STATUS_CODE] = parts[1]
                if len(parts) > 2:
                    headers[Headers.STATUS_DESC] = parts[2]
            else:
                raise error.Malformed(f"Malformed header: {line}")
        else:
            headers[parts[0]] = parts[1]

    return headers
