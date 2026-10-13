from contextlib import contextmanager
from typing import Iterator, Optional

import httpx


class LegismexError(Exception):
    """Excepción base para todos los errores en legismex."""
    pass


class LegismexConnectionError(LegismexError):
    """
    Excepción lanzada cuando hay un error de conexión con el servidor 
    del Congreso o Periódico Oficial (ej. Timeout, SSL inválido no manejado).
    """
    pass


class HTMLParsingError(LegismexError):
    """
    Excepción lanzada cuando la estructura del HTML ha cambiado y 
    no se pueden encontrar los elementos esperados usando BeautifulSoup/lxml.
    """
    pass


class APIResponseError(LegismexError):
    """
    Excepción lanzada cuando el backend interconectado (JSON/REST)
    devuelve un status code de error (e.g. 500) o un payload inesperado.
    """
    pass


class DocumentNotFoundError(LegismexError):
    """
    Excepción lanzada cuando se busca una gaceta, iniciativa o documento
    específico por parámetros (año, id) y no existe en los registros.
    """
    pass


@contextmanager
def wrap_httpx_errors(url: Optional[str] = None) -> Iterator[None]:
    """
    Mapea excepciones de ``httpx`` a la jerarquía tipada de ``legismex``.

    - ``httpx.HTTPStatusError`` (raise_for_status) → :class:`APIResponseError`
    - ``httpx.RequestError`` (timeouts, SSL, conexión, etc.) → :class:`LegismexConnectionError`

    Uso::

        with httpx.Client(...) as client, wrap_httpx_errors(url):
            r = client.get(url)
            r.raise_for_status()
    """
    try:
        yield
    except httpx.HTTPStatusError as e:
        target = url or str(e.request.url)
        raise APIResponseError(
            f"HTTP {e.response.status_code} en {target}"
        ) from e
    except httpx.RequestError as e:
        if url:
            target = url
        else:
            try:
                target = str(e.request.url)
            except RuntimeError:
                # httpx errors may be raised before a Request is attached.
                target = "?"
        raise LegismexConnectionError(
            f"Error de conexión a {target}: {e.__class__.__name__}: {e}"
        ) from e
