"""Small one-way OSC 1.0 UDP sender, independent of Blender and third-party packages.

Only scalar float32 messages and immediate bundles are needed for the first milestone.
This intentionally supplies no receiver, reliable event delivery, or audio streaming.
"""

import socket
import struct
import time
from math import isfinite

from spatial_sculptures.simulation.fields import FieldState

from .messages import state_messages


def encode_message(address: str, value: float) -> bytes:
    """Encode an OSC address, padded type tag and one big-endian float32 argument."""
    if not address.startswith("/") or "\0" in address:
        raise ValueError("OSC addresses must start with / and contain no NUL characters")
    if not isfinite(value):
        raise ValueError("OSC state values must be finite")
    path = address.encode("ascii") + b"\0"
    path += b"\0" * (-len(path) % 4)
    return path + b",f\0\0" + struct.pack(">f", value)


def encode_state(state: FieldState) -> bytes:
    """Bundle one state's messages with the OSC immediate timetag (1)."""
    elements = []
    for address, value in state_messages(state):
        packet = encode_message(address, value)
        elements.append(struct.pack(">i", len(packet)) + packet)
    return b"#bundle\0" + struct.pack(">Q", 1) + b"".join(elements)


class OSCTransport:
    """Lazy, closable UDP output capped by wall-clock send_rate.

    Disabled transport creates no socket and resolves no host. An enabled sender
    does not need an OSC server to exist, though it cannot know whether UDP arrives.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        host: str = "127.0.0.1",
        port: int = 57120,
        send_rate: float = 30.0,
    ):
        if not 1 <= port <= 65535 or not isfinite(send_rate) or send_rate <= 0:
            raise ValueError("OSC port must be 1..65535 and send_rate must be finite and positive")
        self.enabled = enabled
        self.destination = (host, port)
        self.send_rate = send_rate
        self._socket: socket.socket | None = None
        self._last_send: float | None = None

    def send_state(self, state: FieldState) -> bool:
        """Send an immediate snapshot, returning False when disabled or rate-limited."""
        if not self.enabled:
            return False
        now = time.monotonic()
        if self._last_send is not None and now - self._last_send < 1.0 / self.send_rate:
            return False
        packet = encode_state(state)
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.sendto(packet, self.destination)
        self._last_send = now
        return True

    def close(self) -> None:
        """Close the socket, allowing a later send to reopen it if still enabled."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._last_send = None
