"""Live verification of two pages of Campeche's official gazette."""
from datetime import date

from legismex import CampechePoClient


def main():
    publications = CampechePoClient().obtener_publicaciones(date.today().year, paginas=2)
    if not publications:
        raise RuntimeError('No se encontraron publicaciones de Campeche')
    print(f'Campeche: {len(publications)} publicaciones en dos páginas')
    for publication in publications[:3]:
        print(publication.fecha, publication.titulo, publication.url_pdf)


if __name__ == '__main__':
    main()
