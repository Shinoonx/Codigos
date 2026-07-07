"""
Algoritmo "Taste Breaker" (Descubridor Transversal de Géneros).
"""
import argparse
import logging
import math
import re
import unicodedata
from collections import Counter

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ATRIBUTOS_AUDIO = ["energy", "danceability", "tempo", "valence"]


def normalizar_titulo_extremo(nombre: str) -> str:
    if not isinstance(nombre, str):
        return ""
    n = nombre.lower()
    n = re.sub(r'[\(\[].*?[\)\]]', '', n)
    n = re.sub(r'\b(feat\.?|ft\.?|remix|remastered|version|radio edit|live)\b.*', '', n)
    n = re.sub(r'-.*', '', n)
    n = unicodedata.normalize('NFKD', n).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-z0-9]', '', n)


def obtener_usuario_aleatorio(driver) -> str:
    query = """
    MATCH (u:Usuario)-[r:AGREGO_A_PLAYLIST]->(c:Cancion)
    WITH u, count(c) as total_canciones
    WHERE total_canciones >= 10 AND total_canciones <= 50
    RETURN u.id AS user_id 
    ORDER BY rand() 
    LIMIT 1
    """
    with driver.session() as session:
        res = session.run(query).single()
        return res["user_id"] if res else None


def obtener_canciones_usuario_normalizadas(driver, user_id: str) -> list:
    query = """
    MATCH (u:Usuario {id: $user_id})-[:AGREGO_A_PLAYLIST]->(c:Cancion)
    RETURN DISTINCT c.nombre AS nombre
    """
    with driver.session() as session:
        return [normalizar_titulo_extremo(rec["nombre"]) for rec in session.run(query, user_id=user_id) if rec["nombre"]]


def obtener_diccionario_traduccion_mongo(coleccion) -> dict:
    """Crea un mapa: clave_limpia -> track_name original de MongoDB para poder consultarlo."""
    res = coleccion.find({}, {"track_name": 1})
    mapa = {}
    for doc in res:
        nombre = doc.get("track_name")
        if isinstance(nombre, str):
            clave = normalizar_titulo_extremo(nombre)
            if clave:
                mapa[clave] = nombre
    return mapa


def distancia_euclidiana(v1: list, v2: list) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def ejecutar_taste_breaker(user_id_obj: str = None, n_recomendaciones: int = 5):
    config.validar_config()

    with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as driver_neo:
        driver_neo.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]

            # Construir el mapa de traducción en memoria
            log.info("Generando mapa de traducción de nombres en MongoDB...")
            mapa_mongo = obtener_diccionario_traduccion_mongo(coleccion)

            perfiles_usuario = []
            target_user = user_id_obj
            intentos = 0
            max_intentos = 15 

            while not perfiles_usuario and intentos < max_intentos:
                if not user_id_obj:
                    target_user = obtener_usuario_aleatorio(driver_neo)
                
                if not target_user:
                    log.error("No se encontró un usuario válido en Neo4j.")
                    return

                canciones_normalizadas_neo4j = obtener_canciones_usuario_normalizadas(driver_neo, target_user)
                
                # Traducir los nombres aplastados de Neo4j a los nombres originales de Mongo
                nombres_originales_mongo = [mapa_mongo[n] for n in canciones_normalizadas_neo4j if n in mapa_mongo]

                if nombres_originales_mongo:
                    perfiles_usuario = list(coleccion.find(
                        {"track_name": {"$in": nombres_originales_mongo}},
                        {"track_name": 1, "track_genre": 1, **{a: 1 for a in ATRIBUTOS_AUDIO}}
                    ))

                if len(perfiles_usuario) < 3:
                    if user_id_obj:
                        log.warning("El usuario no tiene suficientes canciones cruzadas en Mongo.")
                        return
                    else:
                        perfiles_usuario = []
                        intentos += 1
            
            if not perfiles_usuario:
                log.error("Se superó el límite de intentos buscando un usuario con datos cruzados.")
                return

            log.info(f"¡Usuario perfilado exitosamente! ({target_user})")
            log.info(f"-> Canciones originales en su playlist: {len(canciones_normalizadas_neo4j)}")
            log.info(f"-> Cruce en MongoDB: {len(perfiles_usuario)} canciones para calcular ADN.")
            
            generos = [doc.get("track_genre") for doc in perfiles_usuario if doc.get("track_genre")]
            top_generos = [g for g, _ in Counter(generos).most_common(3)]
            
            adn_usuario = {}
            for attr in ATRIBUTOS_AUDIO:
                valores_validos = [doc[attr] for doc in perfiles_usuario if doc.get(attr) is not None]
                adn_usuario[attr] = sum(valores_validos) / len(valores_validos) if valores_validos else 0

            print("\n=======================================================")
            print("🧬 PERFIL DEL USUARIO (LA BURBUJA)")
            print("=======================================================")
            print(f"🎸 Géneros favoritos (Zona de confort): {', '.join(top_generos)}")
            print("📊 ADN Acústico Promedio:")
            for attr in ATRIBUTOS_AUDIO:
                print(f"   - {attr.capitalize()}: {adn_usuario[attr]:.3f}")

            log.info("Buscando canciones fuera de su zona de confort...")
            query_rompe_burbujas = {
                "track_genre": {"$nin": top_generos}, 
                "energy": {"$ne": None},
                "danceability": {"$ne": None}
            }
            
            candidatos = coleccion.find(query_rompe_burbujas, {"track_name": 1, "track_genre": 1, **{a: 1 for a in ATRIBUTOS_AUDIO}})
            
            vector_adn = [adn_usuario[a] for a in ATRIBUTOS_AUDIO]
            
            recomendaciones = []
            for doc in candidatos:
                vector_candidato = [doc.get(a, 0) for a in ATRIBUTOS_AUDIO]
                distancia = distancia_euclidiana(vector_adn, vector_candidato)
                recomendaciones.append((distancia, doc))

            recomendaciones.sort(key=lambda x: x[0])
            mejores_taste_breakers = recomendaciones[:n_recomendaciones]

            print("\n=======================================================")
            print("🔥 TASTE BREAKERS (RECOMENDACIONES TRANSVERSALES)")
            print("=======================================================")
            print("Canciones de géneros que NO suele escuchar, pero que suenan")
            print("exactamente como la música que le gusta:\n")
            
            for rank, (dist, doc) in enumerate(mejores_taste_breakers, 1):
                print(f"{rank}. 🎵 '{doc['track_name']}'")
                print(f"   💥 Género Nuevo: {doc['track_genre']}")
                print(f"   📐 Distancia al ADN del usuario: {dist:.3f}")
                print(f"   📊 Perfil: Energy {doc.get('energy', 0):.2f} | Dance {doc.get('danceability', 0):.2f} | Tempo {doc.get('tempo', 0):.0f}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Algoritmo Taste Breaker con Normalización Extrema.")
    parser.add_argument("--usuario", type=str, default=None)
    parser.add_argument("--recomendaciones", type=int, default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ejecutar_taste_breaker(user_id_obj=args.usuario, n_recomendaciones=args.recomendaciones)