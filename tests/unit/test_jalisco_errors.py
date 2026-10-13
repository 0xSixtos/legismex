from unittest.mock import patch

import httpx
import pytest

from legismex import APIResponseError
from legismex.jalisco import JaliscoClient, JaliscoEvento


@pytest.mark.parametrize("failed_endpoint", ["orden.php", "suborden.php"])
def test_jalisco_reports_nested_http_error(failed_endpoint):
    def handler(request):
        if request.url.path.endswith("/" + failed_endpoint):
            return httpx.Response(503)
        return httpx.Response(200, text="mock HTML")

    event = JaliscoEvento(fecha="2026-10-12", titulo="Sesión", tipo=1, id_evento=1)
    points = [{"titulo": "Punto", "onclick_id": 1, "onclick_tipo": 1}]
    transport = httpx.Client(transport=httpx.MockTransport(handler))
    with patch("legismex.jalisco.client.httpx.Client", return_value=transport):
        with patch("legismex.jalisco.client.parse_eventos_dia", return_value=[event]):
            with patch("legismex.jalisco.client.parse_orden_dia", return_value=points):
                with pytest.raises(APIResponseError, match="HTTP 503"):
                    JaliscoClient().obtener_eventos_por_fecha("2026-10-12")
