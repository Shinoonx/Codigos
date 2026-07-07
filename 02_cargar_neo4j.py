"""
Carga las playlists de Spotify en Neo4j como un grafo usuario-cancion.
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

ARCHIVO_PLAYLISTS_POR_DEFECTO = "spotify_dataset.csv"
LIMITE_CARGA_POR_DEFECTO = 100_000
COLUMNA_USUARIO = "user_id"
COLUMNA_CANCION = "trackname"
COLUMNA_ARTISTA = "artistname"
COLUMNA_PLAYLIST = "playlistname"
CSV_SEPARADOR = ","
CSV_COMILLAS = '"'
CSV_ESCAPE = "\\"
CSV_LINEAS_INVALIDAS = "skip"

QUERY_CARGA = f"""
UNWIND $filas AS fila
MERGE (u:{config.ETIQUETA_USUARIO} {{{config.PROP_ID_USUARIO}: fila.{COLUMNA_USUARIO}}})
MERGE (c:{config.ETIQUETA_CANCION} {{{config.PROP_NOMBRE}: fila.{COLUMNA_CANCION}, {config.PROP_ARTISTA}: fila.{COLUMNA_ARTISTA}}})
MERGE (u)-[:{config.RELACION_AGREGO_PLAYLIST} {{{config.PROP_PLAYLIST}: fila.{COLUMNA_PLAYLIST}}}]->(c)
"""


def crear_indices(driver) -> None:
    """Crea indices para acelerar los MERGE de la carga."""
    sentencias = [
        (
            f"CREATE CONSTRAINT usuario_id IF NOT EXISTS "
            f"FOR (u:{config.ETIQUETA_USUARIO}) REQUIRE u.{config.PROP_ID_USUARIO} IS UNIQUE"
        ),
        (
            f"CREATE INDEX cancion_nombre_artista IF NOT EXISTS "
            f"FOR (c:{config.ETIQUETA_CANCION}) "
            f"ON (c.{config.PROP_NOMBRE}, c.{config.PROP_ARTISTA})"
        ),
    ]
    with driver.session() as session:
        for sentencia in sentencias:
            session.run(sentencia)
    log.info("Indices/constraints verificados.")


def limpiar_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    columnas_requeridas = [
        COLUMNA_USUARIO,
        COLUMNA_CANCION,
        COLUMNA_ARTISTA,
        COLUMNA_PLAYLIST,
    ]
    chunk.columns = chunk.columns.str.strip().str.replace('"', "")
    chunk = chunk.dropna(subset=columnas_requeridas)
    chunk[COLUMNA_PLAYLIST] = chunk[COLUMNA_PLAYLIST].str.strip()
    return chunk


def cargar_grafos(
    archivo_csv: str,
    limite: int | None = LIMITE_CARGA_POR_DEFECTO,
) -> None:
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
                sep=CSV_SEPARADOR,
                quotechar=CSV_COMILLAS,
                escapechar=CSV_ESCAPE,
                on_bad_lines=CSV_LINEAS_INVALIDAS,
                chunksize=config.LOTE_SIZE,
            )
        except FileNotFoundError:
            log.error("No se encontro el archivo: %s", archivo_csv)
            sys.exit(1)

        total_procesadas = 0
        with driver.session() as session:
            for i, chunk in enumerate(lector, start=1):
                chunk = limpiar_chunk(chunk)
                if limite is not None and total_procesadas >= limite:
                    break
                if limite is not None:
                    chunk = chunk.head(limite - total_procesadas)

                datos = chunk.to_dict("records")
                if not datos:
                    continue

                session.execute_write(lambda tx, filas: tx.run(QUERY_CARGA, filas=filas), datos)
                total_procesadas += len(datos)
                log.info("Progreso: %d procesados (chunk %d)", total_procesadas, i)

    log.info("Grafo construido con exito. Total de filas cargadas: %d", total_procesadas)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga un CSV de playlists en Neo4j.")
    parser.add_argument(
        "archivo",
        nargs="?",
        default=ARCHIVO_PLAYLISTS_POR_DEFECTO,
        help="Ruta al CSV de entrada",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=LIMITE_CARGA_POR_DEFECTO,
        help="Maximo de filas a cargar (usar 0 para cargar todo)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cargar_grafos(args.archivo, limite=args.limite)
