"""
Carga el catalogo tecnico de canciones en MongoDB.
"""
import argparse
import logging
import sys

import pandas as pd
from pymongo import ASCENDING, MongoClient
from pymongo.errors import BulkWriteError

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ARCHIVO_CATALOGO_POR_DEFECTO = "dataset.csv"
LIMITE_CARGA_POR_DEFECTO = 0
CAMPO_ID_CANCION = "track_id"
COLUMNAS_A_IGNORAR = ["Unnamed: 0"]
CODIGO_ERROR_DUPLICADO = 11000
CSV_ESCAPE = "\\"


def cargar_catalogo_mongodb(
    ruta_archivo: str,
    vaciar_coleccion: bool = False,
    limite: int | None = LIMITE_CARGA_POR_DEFECTO,
) -> None:
    if limite == 0:
        limite = None
    config.validar_config()

    log.info("Conectando a MongoDB en %s ...", config.MONGO_URI)
    cliente = MongoClient(config.MONGO_URI)
    coleccion = cliente[config.MONGO_DB][config.MONGO_COLLECTION]

    if vaciar_coleccion:
        log.warning("Vaciando la coleccion '%s' antes de cargar...", config.MONGO_COLLECTION)
        coleccion.delete_many({})

    campo_llave = CAMPO_ID_CANCION
    try:
        coleccion.create_index([(campo_llave, ASCENDING)], unique=True, sparse=True)
    except Exception as exc:
        log.warning("No se pudo crear indice unico en '%s': %s", campo_llave, exc)

    total_insertados = 0
    total_duplicados = 0
    total_procesados = 0

    try:
        lector = pd.read_csv(
            ruta_archivo,
            escapechar=CSV_ESCAPE,
            chunksize=config.LOTE_SIZE,
        )
    except FileNotFoundError:
        log.error("No se encontro el archivo en la ruta: %s", ruta_archivo)
        sys.exit(1)

    for i, chunk in enumerate(lector, start=1):
        if limite is not None and total_procesados >= limite:
            break
        if limite is not None:
            chunk = chunk.head(limite - total_procesados)

        columnas_a_ignorar = [
            columna for columna in COLUMNAS_A_IGNORAR if columna in chunk.columns
        ]
        if columnas_a_ignorar:
            chunk = chunk.drop(columns=columnas_a_ignorar)

        documentos = chunk.to_dict(orient="records")
        if not documentos:
            continue

        try:
            resultado = coleccion.insert_many(documentos, ordered=False)
            total_insertados += len(resultado.inserted_ids)
        except BulkWriteError as error_bulk:
            insertados = error_bulk.details.get("nInserted", 0)
            duplicados = sum(
                1
                for error in error_bulk.details.get("writeErrors", [])
                if error.get("code") == CODIGO_ERROR_DUPLICADO
            )
            total_insertados += insertados
            total_duplicados += duplicados
            log.warning(
                "Chunk %d: %d insertados, %d duplicados/ignorados",
                i,
                insertados,
                duplicados,
            )
        else:
            log.info("Chunk %d: %d documentos insertados", i, len(documentos))

        total_procesados += len(documentos)

    log.info(
        "Carga finalizada. Total insertados: %d | Duplicados ignorados: %d",
        total_insertados,
        total_duplicados,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga un CSV de canciones en MongoDB.")
    parser.add_argument(
        "archivo",
        nargs="?",
        default=ARCHIVO_CATALOGO_POR_DEFECTO,
        help="Ruta al CSV de entrada",
    )
    parser.add_argument(
        "--vaciar",
        action="store_true",
        help="Borra la coleccion antes de insertar",
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
    cargar_catalogo_mongodb(args.archivo, vaciar_coleccion=args.vaciar, limite=args.limite)
