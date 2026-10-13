import httpx
from bs4 import BeautifulSoup
from typing import List
from datetime import date
import calendar
from urllib.parse import urljoin

from legismex._http import fetch_pages

from .models import QrooPoPublicacion


class QrooPoClient:
    """Cliente para el Periódico Oficial del Estado de Quintana Roo."""
    BASE_URL = "http://po.segob.qroo.gob.mx/sitiopo"

    def __init__(self, concurrency: int = 5, **kwargs):
        if concurrency < 1:
            raise ValueError("concurrency debe ser al menos 1")
        self.concurrency = concurrency
        self.client_kwargs = {
            "timeout": 30.0,
            "verify": False,
            "follow_redirects": True,
            **kwargs
        }

    def _preparar_parametros(self, anio: int, mes: int, pagina: int = 1) -> dict:
        _, ultimo_dia = calendar.monthrange(anio, mes)
        fecha_inicio = f"{anio}-{mes:02d}-01"
        fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia:02d}"

        params = {
            "Titulo": "",
            "FechaPublicacion": fecha_inicio,
            "FechaPublicacion2": fecha_fin,
            "IdTipo": "0",  # Todos
            "IdEpoca": "0",  # Todos
            "Buscar": "1"
        }
        if pagina > 1:
            params["Pagina"] = str(pagina)

        return params

    def _extraer_publicaciones_de_html(self, html: str) -> List[QrooPoPublicacion]:
        soup = BeautifulSoup(html, "html.parser")
        resultados = []

        meses_es = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        }
        # The publication table is now the only table on the page. Identify
        # data rows by their columns instead of assuming a second table.
        for row in soup.select("table tr"):
            cols = row.find_all("td", recursive=False)
            if len(cols) < 8:
                continue
            link_tag = cols[1].find("a", href=True)
            if not link_tag:
                continue
            try:
                mes_num = meses_es.get(cols[3].get_text(strip=True).lower())
                if mes_num is None:
                    continue
                fecha = date(
                    int(cols[4].get_text(strip=True)),
                    mes_num,
                    int(cols[2].get_text(strip=True)),
                )
                resultados.append(QrooPoPublicacion(
                    fecha=fecha,
                    tipo=cols[5].get_text(strip=True),
                    numero=cols[6].get_text(strip=True),
                    tomo=cols[7].get_text(strip=True),
                    url_pdf=urljoin(f"{self.BASE_URL}/", link_tag["href"]),
                ))
            except (ValueError, TypeError):
                continue

        return resultados

    def _obtener_total_paginas(self, html: str) -> int:
        soup = BeautifulSoup(html, "html.parser")
        pag = soup.find("form", {"name": "FormularioPaginado"})
        if pag:
            texto = pag.get_text(strip=True)
            # Ej: Mostrando 1 - 24 de un total de 28 registros.Número de página:1, 2
            # Evaluamos cuantas opciones hay en el select
            select = pag.find("select", {"name": "Pagina"})
            if select:
                opts = select.find_all("option")
                return max(len(opts), 1)
        return 1

    def obtener_publicaciones(self, anio: int, mes: int) -> List[QrooPoPublicacion]:
        """Obtiene las publicaciones del Periódico Oficial para un mes y año específicos (Síncrono)."""
        publicaciones = []
        with httpx.Client(**self.client_kwargs) as client:
            url = f"{self.BASE_URL}/BusquedaAvanzada.php"

            # Request inicial
            params = self._preparar_parametros(anio, mes, 1)
            resp = client.get(url, params=params)
            resp.raise_for_status()

            html = resp.text
            publicaciones.extend(self._extraer_publicaciones_de_html(html))

            total_paginas = self._obtener_total_paginas(html)

            # Iterar resto
            for p in range(2, total_paginas + 1):
                params_p = self._preparar_parametros(anio, mes, p)
                resp_p = client.get(url, params=params_p)
                resp_p.raise_for_status()
                publicaciones.extend(
                    self._extraer_publicaciones_de_html(resp_p.text))

        return publicaciones

    async def a_obtener_publicaciones(self, anio: int, mes: int) -> List[QrooPoPublicacion]:
        """Obtiene las publicaciones del Periódico Oficial para un mes y año específicos (Asíncrono)."""
        publicaciones = []
        async with httpx.AsyncClient(**self.client_kwargs) as client:
            url = f"{self.BASE_URL}/BusquedaAvanzada.php"

            # Request inicial
            params = self._preparar_parametros(anio, mes, 1)
            resp = await client.get(url, params=params)
            resp.raise_for_status()

            html = resp.text
            publicaciones.extend(self._extraer_publicaciones_de_html(html))

            total_paginas = self._obtener_total_paginas(html)

            if total_paginas > 1:
                requests = [
                    (url, self._preparar_parametros(anio, mes, page))
                    for page in range(2, total_paginas + 1)
                ]
                respuestas = await fetch_pages(
                    client, requests, concurrency=self.concurrency
                )
                for response in respuestas:
                    publicaciones.extend(
                        self._extraer_publicaciones_de_html(response.text))

        # Evitar traslape ordenando todo
        publicaciones.sort(key=lambda x: x.fecha, reverse=True)
        return publicaciones
