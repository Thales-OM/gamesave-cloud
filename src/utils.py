import socket
from src.exceptions import AvailablePortNotFoundError


def find_port(port: int, max_port: int = 49151) -> int:
    """Find a port not in ues starting at given port"""
    if port > max_port:
        raise AvailablePortNotFoundError(
            f"Failed to found an available port lesser than \
                or equal to {max_port}"
        )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            return find_port(port=port + 1)
        else:
            return port
