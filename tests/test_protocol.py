"""Tests for distributed protocol."""

from pycosim.distributed.protocol import Command, Request, Response


def test_request_roundtrip():
    req = Request(command=Command.STEP, params={"current_time": 0.5, "dt": 0.1})
    data = req.encode()
    decoded = Request.decode(data)
    assert decoded.command == Command.STEP
    assert decoded.params["current_time"] == 0.5
    assert decoded.params["dt"] == 0.1


def test_response_roundtrip():
    resp = Response(success=True, data=42.0)
    data = resp.encode()
    decoded = Response.decode(data)
    assert decoded.success is True
    assert decoded.data == 42.0


def test_error_response():
    resp = Response(success=False, error="something broke")
    decoded = Response.decode(resp.encode())
    assert not decoded.success
    assert decoded.error == "something broke"
