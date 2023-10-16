from .. import model, error


def parse_server(server: str) -> model.Server:
    def has_proto(proto: str) -> bool:
        return server[:len(proto) + 3] == f"{proto}://"

    try:
        if has_proto(model.Server.Protocol.NATS):
            # nats://127.0.0.1:4222
            # nats://hostname:4222
            # nats://hostname
            parts = server[len(model.Server.Protocol.NATS) + 3:].split(':')

            if len(parts) > 2:
                raise error.Malformed(f"Syntax error in server string '{server}'")
            elif len(parts) == 1:
                return model.Server(parts[0], proto=model.Server.Protocol.NATS)
            else:
                return model.Server(parts[0], int(parts[1]), proto=model.Server.Protocol.NATS)

        else:
            raise error.Malformed(f"Unsupported protocol for server '{server}'")

    except ValueError as e:
        raise error.Malformed(f"ValueError in server string '{server}': {e}")
