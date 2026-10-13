"""Live verification of Quintana Roo's official gazette."""
from legismex import QrooPoClient


def main():
    publications = QrooPoClient().obtener_publicaciones(2026, 3)
    if not publications:
        raise RuntimeError('No se encontraron publicaciones de Quintana Roo')
    print(f'Quintana Roo: {len(publications)} publicaciones en marzo de 2026')
    for publication in publications[:3]:
        print(publication.fecha, publication.numero, publication.url_pdf)


if __name__ == '__main__':
    main()
