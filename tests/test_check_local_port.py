from __future__ import annotations

import importlib.util
import socket
from pathlib import Path


def load_port_check_module():
    path = Path(__file__).parents[1] / "scripts/check_local_port.py"
    spec = importlib.util.spec_from_file_location("check_local_port", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_port_check_detects_free_and_occupied_ports() -> None:
    port_check = load_port_check_module()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        occupied_port = listener.getsockname()[1]
        listener.listen()

        assert port_check.port_is_available("127.0.0.1", occupied_port) is False

    assert port_check.port_is_available("127.0.0.1", occupied_port) is True


def test_port_check_prints_actionable_override_for_occupied_port(capsys) -> None:
    port_check = load_port_check_module()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        occupied_port = listener.getsockname()[1]
        listener.listen()

        result = port_check.main(
            [
                "--host",
                "127.0.0.1",
                "--port",
                str(occupied_port),
                "--service",
                "Astro ABM API",
                "--retry-command",
                "make api API_PORT=18000",
            ]
        )

    output = capsys.readouterr().out
    assert result == 2
    assert f"127.0.0.1:{occupied_port} is already in use" in output
    assert "make api API_PORT=18000" in output
