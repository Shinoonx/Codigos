"""
Carga el catálogo técnico de canciones (Spotify dataset) en MongoDB.
Mejoras sobre la versión original:
  - Credenciales fuera del código (config.py + .env)
  - Logging en vez de print
  - Lectura del CSV en chunks (no carga todo en memoria de una vez)
  - insert_many(ordered=False) para no frenar toda la carga por un
    documento problemático, con reporte de errores
  - Índice único para evitar duplicados en cargas repetidas, en vez de
    borrar toda la colección cada vez (comportamiento configurable)
  - argparse para poder reutilizar el script con distintos archivos
"""
import argparse
import logging
import sys

import pandas as pd
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

CHUNK_SIZE = config.LOTE_SIZE


def cargar_catalogo_mongodb(ruta_archivo: str, vaciar_coleccion: bool = False) -> None:
    config.validar_config()

    log.info("Conectando a MongoDB en %s ...", config.MONGO_URI)
    cliente = MongoClient(config.MONGO_URI)
    coleccion = cliente[config.MONGO_DB][config.MONGO_COLLECTION]

    if vaciar_coleccion:
        log.warning("Vaciando la colección '%s' antes de cargar...", config.MONGO_COLLECTION)
        coleccion.delete_many({})

    # Índice único sobre track_id (o track_name si no existe track_id) para
    # que cargas repetidas del mismo dataset no generen duplicados.
    campo_llave = "track_id"
    try:
        coleccion.create_index([(campo_llave, ASCENDING)], unique=True, sparse=True)
    except Exception as exc:
        log.warning("No se pudo crear índice único en '%s': %s", campo_llave, exc)

    total_insertados = 0
    total_duplicados = 0

    try:
        lector = pd.read_csv(ruta_archivo, escapechar="\\", chunksize=CHUNK_SIZE)
    except FileNotFoundError:
        log.error("No se encontró el archivo en la ruta: %s", ruta_archivo)
        sys.exit(1)

    for i, chunk in enumerate(lector, start=1):
        if "Unnamed: 0" in chunk.columns:
            chunk = chunk.drop(columns=["Unnamed: 0"])

        documentos = chunk.to_dict(orient="records")
        if not documentos:
            continue

        try:
            resultado = coleccion.insert_many(documentos, ordered=False)
            total_insertados += len(resultado.inserted_ids)
        except BulkWriteError as bwe:
            insertados = bwe.details.get("nInserted", 0)
            duplicados = sum(
                1 for e in bwe.details.get("writeErrors", []) if e.get("code") == 11000
            )
            total_insertados += insertados
            total_duplicados += duplicados
            log.warning(
                "Chunk %d: %d insertados, %d duplicados/ignorados", i, insertados, duplicados
            )
        else:
            log.info("Chunk %d: %d documentos insertados", i, len(documentos))

    log.info(
        "Carga finalizada. Total insertados: %d | Duplicados ignorados: %d",
        total_insertados,
        total_duplicados,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga un CSV de canciones en MongoDB.")
    parser.add_argument("archivo", nargs="?", default="dataset.csv", help="Ruta al CSV de entrada")
    parser.add_argument(
        "--vaciar",
        action="store_true",
        help="Borra la colección antes de insertar (comportamiento del script original)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cargar_catalogo_mongodb(args.archivo, vaciar_coleccion=args.vaciar)
