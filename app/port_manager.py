import socket
from app.config import PORT_CANDIDATES


def find_available_port() -> int:
    for port in PORT_CANDIDATES:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                print(f'[port] selected {port}')
                return port
    raise RuntimeError('No free port available in configured range')
