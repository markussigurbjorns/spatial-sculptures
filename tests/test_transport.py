"""Validate OSC wire format, disabled behavior, localhost delivery, and rate limiting."""

import importlib
import socket
import struct
import unittest
from unittest.mock import patch

from spatial_sculptures.transport.messages import state_messages
from spatial_sculptures.transport.osc import OSCTransport, encode_message, encode_state

prototype = importlib.import_module("prototypes.001_resonant_surface.build")
simulation = importlib.import_module("prototypes.001_resonant_surface.simulation")


def decode_bundle(packet: bytes) -> dict[str, float]:
    """Test-side parser for scalar messages (also checks padding and element lengths)."""
    assert packet[:16] == b"#bundle\0\0\0\0\0\0\0\0\1"
    values = {}
    offset = 16
    while offset < len(packet):
        length = struct.unpack_from(">i", packet, offset)[0]
        offset += 4
        element = packet[offset : offset + length]
        end = element.index(b"\0")
        address = element[:end].decode("ascii")
        start = (end + 4) // 4 * 4
        assert element[start : start + 4] == b",f\0\0"
        assert len(element) == start + 8
        values[address] = struct.unpack_from(">f", element, start + 4)[0]
        offset += length
    assert offset == len(packet)
    return values


class TransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = simulation.ResonantField(prototype.load_config()).step(3.2)

    def test_known_osc_scalar_wire_format(self) -> None:
        self.assertEqual(encode_message("/x", 1.0), b"/x\0\0,f\0\0?\x80\0\0")

    def test_bundle_paths_and_values(self) -> None:
        values = decode_bundle(encode_state(self.state))
        expected = dict(state_messages(self.state))
        self.assertEqual(set(values), set(expected))
        self.assertEqual(len(values), 12)
        self.assertEqual(values["/drop/impact"], 1)
        self.assertAlmostEqual(values["/exciter/2/frequency"], 61.3, places=4)
        for address, value in expected.items():
            self.assertAlmostEqual(values[address], value, places=5)

    def test_disabled_sender_never_opens_a_socket_or_needs_a_server(self) -> None:
        with patch(
            "spatial_sculptures.transport.osc.socket.socket",
            side_effect=AssertionError("Disabled OSC attempted networking"),
        ):
            transport = OSCTransport(enabled=False, host="host-that-does-not-exist.invalid")
            self.assertFalse(transport.send_state(self.state))
            transport.close()

    def test_actual_localhost_udp_delivery(self) -> None:
        try:
            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except PermissionError as error:
            self.skipTest(f"Sandbox blocks UDP socket creation: {error}")
        with receiver:
            try:
                receiver.bind(("127.0.0.1", 0))
            except PermissionError as error:
                self.skipTest(f"Sandbox blocks localhost UDP binding: {error}")
            receiver.settimeout(1)
            transport = OSCTransport(enabled=True, port=receiver.getsockname()[1])
            try:
                self.assertTrue(transport.send_state(self.state))
                packet, _sender = receiver.recvfrom(65535)
                self.assertEqual(packet, encode_state(self.state))
            finally:
                transport.close()

    def test_wall_clock_rate_limit_and_close(self) -> None:
        with patch("spatial_sculptures.transport.osc.socket.socket") as socket_factory:
            with patch(
                "spatial_sculptures.transport.osc.time.monotonic", side_effect=(1.0, 1.01, 1.04)
            ):
                transport = OSCTransport(enabled=True, send_rate=30)
                self.assertTrue(transport.send_state(self.state))
                self.assertFalse(transport.send_state(self.state))
                self.assertTrue(transport.send_state(self.state))
            self.assertEqual(socket_factory.return_value.sendto.call_count, 2)
            transport.close()
            socket_factory.return_value.close.assert_called_once()

    def test_invalid_message_values(self) -> None:
        for address, value in (("no-slash", 1), ("/x\0y", 1), ("/x", float("nan"))):
            with self.assertRaises(ValueError):
                encode_message(address, value)


if __name__ == "__main__":
    unittest.main()
