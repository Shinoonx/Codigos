"""
Carga las playlists de Spotify en Neo4j como un grafo Usuario-[:AGREGO_A_PLAYLIST]->Cancion.
Mejoras sobre la versión original:
  - Credenciales fuera del código (config.py + .env)
  - Logging en vez de print
  - Lectura del CSV en chunks (evita cargar 100k+ filas completas en memoria)
  - Índices/constraints creados antes de la carga para que los MERGE sean rápidos
  - execute_write en vez de session.run directo -> reintentos automáticos
    ante fallos transitorios de conexión
  - argparse para reutilizar el script con distintos archivos y tamaños de lote
"""
import argparse
import logging
import sys

import pandas as pd
from neo4j import GraphDatabase

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

QUERY_CARGA = """
UNWIND $filas AS fila
MERGE (u:Usuario {id: fila.user_id})
MERGE (c:Cancion {nombre: fila.trackname, artista: fila.artistname})
MERGE (u)-[:AGREGO_A_PLAYLIST {playlist: fila.playlistname}]->(c)
"""


def crear_indices(driver):
    """Constraints/índices para que los MERGE no hagan table scans."""
    sentencias = [
        "CREATE CONSTRAINT usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE",
        # Neo4j Community no soporta constraints de unicidad compuestos,
        # así que usamos un índice compuesto (no único) para acelerar el MERGE.
        "CREATE INDEX cancion_nombre_artista IF NOT EXISTS FOR (c:Cancion) ON (c.nombre, c.artista)",
    ]
    with driver.session() as session:
        for s in sentencias:
            session.run(s)
    log.info("Índices/constraints verificados.")


def limpiar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk.columns = chunk.columns.str.strip().str.replace('"', "")
    chunk = chunk.dropna(subset=["user_id", "trackname", "artistname", "playlistname"])
    chunk["playlistname"] = chunk["playlistname"].str.strip()
    return chunk


def cargar_grafos(archivo_csv: str, limite: int | None = 100_000) -> None:
    if limite == 0:
        limite = None
    config.validar_config()

    log.info("Conectando a Neo4j en %s ...", config.NEO4J_URI)
    with GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    ) as driver:
        driver.verify_connectivity()
        crear_indices(driver)

        try:
            lector = pd.read_csv(
                archivo_csv,
                sep=",",
                quotechar='"',
                escapechar="\\",
                on_bad_lines="skip",
                chunksize=config.LOTE_SIZE,
            )
        except FileNotFoundError:
            log.error("No se encontró el archivo: %s", archivo_csv)
            sys.exit(1)

        total_procesadas = 0
        with driver.session() as session:
            for i, chunk in enumerate(lector, start=1):
                chunk = limpiar_chunk(chunk)
                if limite is not None and total_procesadas >= limite:
                    break
                if limite is not None:
                    restante = limite - total_procesadas
                    chunk = chunk.head(restante)

                datos = chunk.to_dict("records")
                if not datos:
                    continue

                session.execute_write(lambda tx, filas: tx.run(QUERY_CARGA, filas=filas), datos)
                total_procesadas += len(datos)
                log.info("Progreso: %d procesados (chunk %d)", total_procesadas, i)

    log.info("¡Grafo construido con éxito! Total de filas cargadas: %d", total_procesadas)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga un CSV de playlists en Neo4j.")
    parser.add_argument(
        "archivo", nargs="?", default="spotify_dataset.csv", help="Ruta al CSV de entrada"
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=100_000,
        help="Máximo de filas a cargar (por defecto: 100000, usar 0 para cargar todo)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cargar_grafos(args.archivo, limite=args.limite)
