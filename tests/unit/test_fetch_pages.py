import asyncio

import httpx
import pytest

from legismex._http import fetch_pages
from legismex.campeche_po import CampechePoClient
from legismex.qroo_po import QrooPoClient


async def test_fetch_pages_limits_concurrency_and_preserves_order():
    active = 0
    peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.001)
        active -= 1
        return httpx.Response(200, text=request.url.params["page"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        pages = await fetch_pages(
            client,
            [("https://example.gob.mx/list", {"page": n}) for n in range(1, 8)],
            concurrency=2,
        )
    assert [page.text for page in pages] == [str(n) for n in range(1, 8)]
    assert peak == 2
    assert active == 0


@pytest.mark.parametrize("error_kind", ["status", "network"])
async def test_fetch_pages_raises_after_all_workers_finish(error_kind):
    finished = []

    async def handler(request):
        page = request.url.params["page"]
        finished.append(page)
        if page == "2":
            if error_kind == "network":
                raise httpx.ReadTimeout("timeout", request=request)
            return httpx.Response(503)
        await asyncio.sleep(0.001)
        return httpx.Response(200)

    error = httpx.ReadTimeout if error_kind == "network" else httpx.HTTPStatusError
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(error):
            await fetch_pages(
                client,
                [("https://example.gob.mx/list", {"page": n}) for n in range(1, 5)],
                concurrency=2,
            )
    assert sorted(finished) == ["1", "2", "3", "4"]


@pytest.mark.parametrize("client_class", [CampechePoClient, QrooPoClient])
@pytest.mark.parametrize("concurrency", [0, -1])
def test_invalid_concurrency(client_class, concurrency):
    with pytest.raises(ValueError, match="concurrency"):
        client_class(concurrency=concurrency)


@pytest.mark.parametrize("client_class", [CampechePoClient, QrooPoClient])
@pytest.mark.parametrize("error_kind", ["status", "network"])
async def test_async_pagination_does_not_return_partial_results(
    client_class, error_kind
):
    def handler(request):
        page = request.url.params.get("page") or request.url.params.get("Pagina") or "1"
        if page == "2":
            if error_kind == "network":
                raise httpx.ConnectError("unavailable", request=request)
            return httpx.Response(500)
        if client_class is CampechePoClient:
            return httpx.Response(
                200,
                text="""<ul class="pagination">
                <li><a href="?page=2">Última</a></li></ul>""",
            )
        return httpx.Response(
            200,
            text="""<form name="FormularioPaginado">
            <select name="Pagina"><option>1</option><option>2</option>
            </select></form>""",
        )

    client = client_class(transport=httpx.MockTransport(handler))
    arguments = (2026,) if client_class is CampechePoClient else (2026, 3)
    error = httpx.ConnectError if error_kind == "network" else httpx.HTTPStatusError
    with pytest.raises(error):
        await client.a_obtener_publicaciones(*arguments)


def test_sync_qroo_pagination_does_not_return_partial_results():
    def handler(request):
        if request.url.params.get("Pagina") == "2":
            return httpx.Response(500)
        return httpx.Response(
            200,
            text="""<form name="FormularioPaginado">
            <select name="Pagina"><option>1</option><option>2</option>
            </select></form>""",
        )

    client = QrooPoClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.obtener_publicaciones(2026, 3)
