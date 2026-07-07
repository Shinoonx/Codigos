"""
Cruza el catálogo técnico de canciones (MongoDB) con el grafo social de
playlists (Neo4j) para encontrar canciones presentes en ambos sistemas.

Versión de Métricas: Normalización Extrema
  - Remueve tildes, caracteres extraños y muletillas de Spotify.
  - Aplasta las cadenas eliminando espacios y signos de puntuación.
"""
import argparse
import logging
import re
import unicodedata

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def normalizar_titulo_extremo(nombre: str) -> str:
    """
    Aplica limpieza extrema al título de la canción.
    """
    if not isinstance(nombre, str):
        return ""
    
    n = nombre.lower()
    
    # 1. Eliminar contenido entre paréntesis () o corchetes []
    n = re.sub(r'[\(\[].*?[\)\]]', '', n)
    
    # 2. Cortar muletillas comunes de Spotify (aunque no tengan paréntesis)
    n = re.sub(r'\b(feat\.?|ft\.?|remix|remastered|version|radio edit|live)\b.*', '', n)
    
    # 3. Eliminar todo desde un guion en adelante
    n = re.sub(r'-.*', '', n)
    
    # 4. Eliminar tildes y diacríticos (ej. á -> a, ö -> o)
    n = unicodedata.normalize('NFKD', n).encode('ASCII', 'ignore').decode('utf-8')
    
    # 5. Aplastar la cadena: eliminar TODOS los espacios y caracteres que no sean letras o números
    n = re.sub(r'[^a-z0-9]', '', n)
    
    return n


def obtener_nombres_neo4j(driver) -> dict:
    query = "MATCH (c:Cancion) RETURN DISTINCT c.nombre AS nombre"
    with driver.session() as session:
        res = session.run(query)
        dict_neo = {}
        for r in res:
            if r["nombre"]:
                clave_limpia = normalizar_titulo_extremo(r["nombre"])
                if clave_limpia:
                    dict_neo[clave_limpia] = r["nombre"]
        return dict_neo


def obtener_nombres_mongo(coleccion) -> dict:
    res = coleccion.find({}, {"track_name": 1})
    dict_mongo = {}
    for doc in res:
        nombre = doc.get("track_name")
        if isinstance(nombre, str):
            clave_limpia = normalizar_titulo_extremo(nombre)
            if clave_limpia:
                dict_mongo[clave_limpia] = nombre
    return dict_mongo


def cruce_definitivo() -> None:
    config.validar_config()

    log.info("Conectando a los motores de bases de datos...")
    with GraphDatabase.driver(
        config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
    ) as driver_neo:
        driver_neo.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion_mongo = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]
            
            coleccion_mongo.create_index("track_name")

            log.info("Extrayendo y aplicando limpieza extrema desde Neo4j...")
            dict_neo = obtener_nombres_neo4j(driver_neo)

            log.info("Extrayendo y aplicando limpieza extrema desde MongoDB...")
            dict_mongo = obtener_nombres_mongo(coleccion_mongo)

            log.info("Realizando la intersección de conjuntos en memoria...")
            coincidencias = set(dict_neo.keys()) & set(dict_mongo.keys())

            print("\n=======================================================")
            print("🚀 REPORTE FINAL DE CRUCE DE DATOS (ETL)")
            print("=======================================================")
            print(f"🔹 Canciones únicas extraídas de Neo4j:   {len(dict_neo):,}")
            print(f"🔹 Canciones únicas extraídas de MongoDB: {len(dict_mongo):,}")
            print("-------------------------------------------------------")
            print(f"✅ Total de coincidencias exactas:        {len(coincidencias):,}")
            print("=======================================================\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcula el total de canciones cruzadas aplicando limpieza extrema de cadenas.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cruce_definitivo()