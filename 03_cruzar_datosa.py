"""
Cruza el catálogo técnico de canciones (MongoDB) con el grafo social de
playlists (Neo4j) para encontrar canciones presentes en ambos sistemas.

Mejoras sobre la versión original:
  - Credenciales fuera del código (config.py + .env)
  - Logging en vez de print
  - Índices en ambos motores para que las búsquedas por nombre no
    escaneen toda la colección/grafo
  - Se consulta el perfil técnico de las coincidencias con UNA sola
    consulta ($in) en vez de un find_one() por cada canción
  - Número de ejemplos a mostrar configurable por CLI
  - Cierre garantizado de ambas conexiones (context managers)
"""
import argparse
import logging

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def obtener_nombres_neo4j(driver) -> dict:
    query = "MATCH (c:Cancion) RETURN DISTINCT c.nombre AS nombre"
    with driver.session() as session:
        res = session.run(query)
        return {
            str(r["nombre"]).strip().lower(): r["nombre"] for r in res if r["nombre"]
        }


def obtener_nombres_mongo(coleccion) -> dict:
    res = coleccion.find({}, {"track_name": 1})
    dict_mongo = {}
    for doc in res:
        nombre = doc.get("track_name")
        if isinstance(nombre, str):
            dict_mongo[nombre.strip().lower()] = nombre
    return dict_mongo


def mostrar_ejemplos(coleccion, driver, coincidencias, dict_mongo, dict_neo, n_ejemplos):
    nombres_a_mostrar = list(coincidencias)[:n_ejemplos]
    nombres_originales_mongo = [dict_mongo[n] for n in nombres_a_mostrar]

    # Una sola consulta a Mongo para todos los ejemplos, en vez de un
    # find_one() por cada canción.
    perfiles = {
        doc["track_name"]: doc
        for doc in coleccion.find({"track_name": {"$in": nombres_originales_mongo}})
    }

    query_playlists = """
    MATCH (u:Usuario)-[r:AGREGO_A_PLAYLIST]->(c:Cancion {nombre: $nombre})
    RETURN r.playlist AS playlist LIMIT 3
    """

    print("\n=======================================================")
    print("🎉 ¡CRUCE DE INFORMACIÓN EXITOSO! (MongoDB + Neo4j) 🎉")
    print("=======================================================\n")

    with driver.session() as session:
        for nombre_normalizado in nombres_a_mostrar:
            nombre_original_mongo = dict_mongo[nombre_normalizado]
            nombre_original_neo = dict_neo[nombre_normalizado]

            perfil = perfiles.get(nombre_original_mongo, {})
            genero = perfil.get("track_genre", "Desconocido")
            energia = perfil.get("energy", "N/A")
            bailabilidad = perfil.get("danceability", "N/A")

            res_playlists = session.run(query_playlists, nombre=nombre_original_neo)
            playlists = [rec["playlist"] for rec in res_playlists]

            print(f"🎵 Pista: '{nombre_original_mongo}'")
            print("   📊 Perfil Técnico (MongoDB):")
            print(f"      - Género: {genero} | Energía: {energia} | Bailabilidad: {bailabilidad}")
            print("   👥 Interacciones (Neo4j):")
            print(f"      - Guardada en las playlists: {', '.join(playlists)}\n")


def cruce_definitivo(n_ejemplos: int = 5) -> None:
    config.validar_config()

    log.info("Conectando a los motores de bases de datos...")
    with GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    ) as driver_neo:
        driver_neo.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion_mongo = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]
            # Índice para que futuras búsquedas por nombre sean rápidas.
            coleccion_mongo.create_index("track_name")

            log.info("Extrayendo nombres desde Neo4j...")
            dict_neo = obtener_nombres_neo4j(driver_neo)
            log.info("-> %d canciones únicas en el grafo.", len(dict_neo))

            log.info("Extrayendo nombres desde MongoDB...")
            dict_mongo = obtener_nombres_mongo(coleccion_mongo)
            log.info("-> %d canciones únicas en Mongo.", len(dict_mongo))

            log.info("Realizando el cruce en memoria (intersección)...")
            coincidencias = set(dict_neo.keys()) & set(dict_mongo.keys())
            log.info("-> %d coincidencias exactas (ignorando formato).", len(coincidencias))

            if not coincidencias:
                log.info("No hay coincidencias entre los datasets.")
                return

            mostrar_ejemplos(
                coleccion_mongo, driver_neo, coincidencias, dict_mongo, dict_neo, n_ejemplos
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cruza canciones entre MongoDB y Neo4j.")
    parser.add_argument(
        "--ejemplos", type=int, default=5, help="Cantidad de coincidencias a mostrar en detalle"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cruce_definitivo(n_ejemplos=args.ejemplos)
