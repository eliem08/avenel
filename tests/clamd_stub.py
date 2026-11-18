"""A stand-in clamd for the test suite, so production code needs no offline mode.

It speaks the parts of the clamd protocol AVENEL uses, over a real local TCP socket:
- `zINSTREAM\\0` then length-prefixed chunks: replies `stream: OK\\0`, or `stream: <name> FOUND\\0` when the
  EICAR test signature is in the bytes (the name real ClamAV uses);
- `PING`: replies `PONG`;
- `VERSION`: replies a version whose signature date is two hours old.

It is not a virus scanner. Only the EICAR test signature is "detected".
"""

from __future__ import annotations

import datetime
import socket
import socketserver
import struct
import threading

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
EICAR_NAME = "Win.Test.EICAR_HDB-1"


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("client closed the stream")
        buf += chunk
    return buf


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        sock: socket.socket = self.request
        head = sock.recv(10)
        if head.startswith(b"zINSTREAM"):
            data = b""
            while True:
                (size,) = struct.unpack(">I", _read_exact(sock, 4))
                if size == 0:
                    break
                data += _read_exact(sock, size)
            reply = f"stream: {EICAR_NAME} FOUND" if EICAR in data else "stream: OK"
            sock.sendall(reply.encode() + b"\0")
        elif head.startswith(b"PING"):
            sock.sendall(b"PONG\n")
        elif head.startswith(b"VERSION"):
            when = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
            sock.sendall(f"ClamAV 1.4.1/27654/{when.strftime('%a %b %d %H:%M:%S %Y')}\n".encode())


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start() -> int:
    """Starts the stand-in on a free local port, in a daemon thread, and returns the port."""
    server = _Server(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, name="clamd-stub", daemon=True).start()
    return int(server.server_address[1])
