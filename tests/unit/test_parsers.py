from pathlib import Path

import httpx
import pytest

from legismex.dof.parser import DofParser
from legismex.durango_po import DurangoPoClient
from legismex.senado.parser import SenadoParser
from legismex.tlaxcala_po import TlaxcalaPoClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_durango_current_layout_and_duplicate_links():
    client = DurangoPoClient()
    editions = client._parsear_ediciones_lista(
        (FIXTURES / "durango_po_current.html").read_text()
    )
    assert len(editions) == 2
    assert editions[0].titulo == "No. 82 Normal 2026"
    assert editions[0].fecha == "domingo, 11 de octubre"
    assert editions[0].cantidad_publicaciones == "7 Publicaciones"
    assert not editions[0].es_extraordinario
    assert editions[1].es_extraordinario
    assert editions[1].es_bis


def test_durango_legacy_layout():
    html = """<div class="md:grid-cols-6"><h3>Edición 10 Bis</h3>
        <span class="text-gray-60">10 de marzo</span>
        <span class="text-gray-60">5 publicaciones</span>
        <a href="/periodicos/88a22e57-3dcf-43d6-b7f8-089326fe38a7">Ver</a></div>"""
    editions = DurangoPoClient()._parsear_ediciones_lista(html)
    assert len(editions) == 1
    assert editions[0].titulo == "Edición 10 Bis"
    assert editions[0].es_bis


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_durango_detail_http_failure_is_not_hidden(asynchronous):
    def handler(request):
        if request.url.path == "/periodicos":
            return httpx.Response(
                200, text=(FIXTURES / "durango_po_current.html").read_text()
            )
        return httpx.Response(403)

    client = DurangoPoClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        if asynchronous:
            await client.a_obtener_ediciones()
        else:
            client.obtener_ediciones()


@pytest.mark.parametrize(
    "href",
    [
        "nota_detalle.php?codigo=123",
        "/nota_detalle.php?codigo=123",
        "https://www.dof.gob.mx/nota_detalle.php?codigo=123",
        "//www.dof.gob.mx/nota_detalle.php?codigo=123",
    ],
)
def test_dof_absolute_document_urls(href):
    edition = DofParser.parse_edicion_dia(
        f'<table><tr><td><a class="enlaces" href="{href}">Decreto</a></td></tr></table>'
    )
    assert len(edition.documentos) == 1
    assert (
        edition.documentos[0].url
        == "https://www.dof.gob.mx/nota_detalle.php?codigo=123"
    )
    assert (
        edition.documentos[0].url_pdf
        == "https://www.dof.gob.mx/nota_to_pdf.php?codigo=123"
    )


@pytest.mark.parametrize(
    "href,expected",
    [
        ("/66/documento/123", "https://www.senado.gob.mx/66/documento/123"),
        ("66/documento/123", "https://www.senado.gob.mx/66/documento/123"),
        (
            "//www.senado.gob.mx/66/documento/123",
            "https://www.senado.gob.mx/66/documento/123",
        ),
        (
            "https://www.senado.gob.mx/66/documento/123",
            "https://www.senado.gob.mx/66/documento/123",
        ),
        (" javascript:void(0) ", None),
        ("   ", None),
        ("#documento", None),
    ],
)
def test_senado_resolves_document_urls(href, expected):
    assert SenadoParser._limpiar_url(href) == expected


def test_tlaxcala_uses_year_index_and_resolves_pdf_links():
    seen_urls = []

    def handler(request):
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            text="""<table>
            <tr><td>Fecha</td><td>No.</td><td>Contenido</td><td>PDF</td></tr>
            <tr><td>12/10/2026</td><td>82</td><td>Decreto</td>
            <td><a href="../2026/82.pdf">PDF</a></td></tr></table>""",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = TlaxcalaPoClient(client=transport)
        editions = client.obtener_ediciones(2026)
    assert seen_urls == ["https://publicaciones.tlaxcala.gob.mx/indices/2026.php"]
    assert len(editions) == 1
    assert editions[0].url_pdf == "https://publicaciones.tlaxcala.gob.mx/2026/82.pdf"


@pytest.mark.parametrize("prefix", ["", "<table><tr><td>Navegación</td></tr></table>"])
def test_qroo_parses_publication_table_without_positional_assumptions(prefix):
    from legismex.qroo_po import QrooPoClient

    html = prefix + (FIXTURES / "qroo_po_current.html").read_text()
    publications = QrooPoClient()._extraer_publicaciones_de_html(html)
    assert len(publications) == 2
    assert publications[0].fecha.isoformat() == "2026-03-31"
    assert publications[0].tipo == "EXTRAORDINARIO"
    assert publications[0].numero == "49"
    assert publications[0].url_pdf == (
        "http://po.segob.qroo.gob.mx/sitiopo/"
        "descargadocumento.php?Fecha=2026-03-31&Tipo=3&Numero=49"
    )


@pytest.mark.parametrize("tag", ["a", "embed", "iframe", "script"])
def test_durango_keeps_signed_pdf_query(tag):
    url = (
        "https://transp23.s3.amazonaws.com/periodico_oficial/2026/82.pdf"
        "?X-Amz-Expires=600&X-Amz-Signature=example"
    )
    escaped = url.replace("&", "&amp;")
    attribute = "href" if tag == "a" else "src"
    html = (
        f'<script>const pdf="{url}";</script>'
        if tag == "script"
        else f'<{tag} {attribute}="{escaped}"></{tag}>'
    )
    assert DurangoPoClient()._extraer_pdf(html) == url


def test_durango_unsigned_legacy_pdf_payload():
    url = "https://transp23.s3.amazonaws.com/old/document.pdf"
    assert DurangoPoClient()._extraer_pdf(f'<script>"{url}"</script>') == url
