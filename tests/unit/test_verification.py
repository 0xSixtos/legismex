import importlib.util
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from legismex import AguascalientesClient

ROOT = Path(__file__).parents[2]


def test_verification_script_propagates_scraper_error():
    request = httpx.Request("GET", "https://example.gob.mx")
    error = httpx.ConnectError("offline", request=request)
    with patch.object(AguascalientesClient, "obtener_promociones", side_effect=error):
        with pytest.raises(httpx.ConnectError):
            runpy.run_path(
                str(ROOT / "tests/verify_aguascalientes_congreso.py"),
                run_name="__main__",
            )


def test_verification_runner_rejects_unmatched_state(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["verify.py", "--estado", "estado_inexistente"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(ROOT / "verify.py"), run_name="__main__")
    assert exc_info.value.code == 1


def test_verification_runner_preserves_stdout_diagnostics(tmp_path):
    spec = importlib.util.spec_from_file_location("legismex_verify", ROOT / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    script = tmp_path / "fails.py"
    script.write_text('print("Provider is unavailable")\nraise SystemExit(1)\n')
    success, output = module.run_script(str(script))
    assert not success
    assert "Provider is unavailable" in output
