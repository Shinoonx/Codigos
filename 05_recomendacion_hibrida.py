"""
Recomendación híbrida para usuarios nuevos / de baja actividad.

Estrategia (resuelve el problema de "cold start"):
  1. Identificar canciones POPULARES en Neo4j.
  2. Normalizar los nombres de forma extrema (Regex) para maximizar cruce.
  3. Buscar canciones con perfil de audio SIMILAR en MongoDB.
  4. Recomendar la canción popular + sus vecinas similares poco conocidas.
"""
import argparse
import logging
import math
import re
import unicodedata

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


def obtener_popularidad(driver) -> dict:
    """nombre_normalizado -> suma de playlists distintas."""
    query = """
    MATCH (c:Cancion)<-[r:AGREGO_A_PLAYLIST]-()
    RETURN c.nombre AS nombre, count(DISTINCT r.playlist) AS num_playlists
    """
    pop = {}
    with driver.session() as session:
        res = session.run(query)
        for rec in res:
            if rec["nombre"]:
                clave = normalizar_titulo_extremo(rec["nombre"])
                if clave:
                    # Sumar popularidad si varias versiones convergen al mismo nombre
                    pop[clave] = pop.get(clave, 0) + rec["num_playlists"]
    return pop


def obtener_perfiles_audio(coleccion) -> dict:
    """nombre_normalizado -> dict con track_name original y atributos de audio."""
    proyeccion = {"track_name": 1, "track_genre": 1, **{a: 1 for a in ATRIBUTOS_AUDIO}}
    res = coleccion.find({}, proyeccion)
    perfiles = {}
    for doc in res:
        nombre = doc.get("track_name")
        if not isinstance(nombre, str) or any(doc.get(a) is None for a in ATRIBUTOS_AUDIO):
            continue
        clave = normalizar_titulo_extremo(nombre)
        if clave and clave not in perfiles:
            perfiles[clave] = doc
    return perfiles


def calcular_estadisticas(perfiles: dict) -> dict:
    stats = {}
    n = len(perfiles)
    for atributo in ATRIBUTOS_AUDIO:
        valores = [p[atributo] for p in perfiles.values()]
        media = sum(valores) / n
        varianza = sum((v - media) ** 2 for v in valores) / n
        stats[atributo] = (media, math.sqrt(varianza) or 1.0)
    return stats


def vector_normalizado(perfil: dict, stats: dict) -> list:
    return [(perfil[a] - stats[a][0]) / stats[a][1] for a in ATRIBUTOS_AUDIO]


def distancia_euclidiana(v1: list, v2: list) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def generar_recomendaciones(
    top_populares: int = 15,
    max_playlists_oculta: int = 2,
    similares_por_popular: int = 3,
    mismo_genero: bool = True,
):
    config.validar_config()

    with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as driver:
        driver.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]

            log.info("Calculando popularidad en Neo4j y normalizando claves...")
            popularidad = obtener_popularidad(driver)

            log.info("Cargando perfiles de audio desde MongoDB con claves normalizadas...")
            perfiles = obtener_perfiles_audio(coleccion)

            popularidad_cruzada = {
                clave: n_playlists
                for clave, n_playlists in popularidad.items()
                if clave in perfiles
            }
            log.info("-> %d canciones con popularidad + perfil de audio disponibles para recomendar.",
                      len(popularidad_cruzada))

            stats = calcular_estadisticas(perfiles)
            semillas = sorted(popularidad_cruzada.items(), key=lambda kv: kv[1], reverse=True)[:top_populares]
            ocultas = [clave for clave, n_playlists in popularidad_cruzada.items() if n_playlists <= max_playlists_oculta]

            print("\n=== 🎯 Recomendación híbrida: Populares + Similares poco conocidas ===\n")

            for clave_popular, n_playlists in semillas:
                perfil_popular = perfiles[clave_popular]
                vector_popular = vector_normalizado(perfil_popular, stats)
                genero_popular = perfil_popular.get("track_genre")

                candidatas = []
                for clave_oculta in ocultas:
                    if clave_oculta == clave_popular:
                        continue
                    perfil_oculta = perfiles[clave_oculta]
                    if mismo_genero and perfil_oculta.get("track_genre") != genero_popular:
                        continue
                    vector_oculta = vector_normalizado(perfil_oculta, stats)
                    dist = distancia_euclidiana(vector_popular, vector_oculta)
                    candidatas.append((dist, clave_oculta, perfil_oculta))

                candidatas.sort(key=lambda x: x[0])
                similares = candidatas[:similares_por_popular]

                print(f"🔥 Popular: '{perfil_popular['track_name']}' "
                      f"(género: {genero_popular}, en {n_playlists} playlists)")
                if similares:
                    print("   Recomendaciones de descubrimiento (similares, poco conocidas):")
                    for dist, clave_oculta, perfil in similares:
                        print(f"      🌱 '{perfil['track_name']}' "
                              f"(distancia: {dist:.3f}, en {popularidad_cruzada.get(clave_oculta, 0)} playlists)")
                else:
                    print("   (no se encontraron canciones similares de baja exposición)")
                print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recomendación híbrida: canciones populares + similares poco conocidas.")
    parser.add_argument("--top-populares", type=int, default=15)
    parser.add_argument("--max-playlists-oculta", type=int, default=2)
    parser.add_argument("--similares-por-popular", type=int, default=3)
    parser.add_argument("--todos-los-generos", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generar_recomendaciones(
        top_populares=args.top_populares,
        max_playlists_oculta=args.max_playlists_oculta,
        similares_por_popular=args.similares_por_popular,
        mismo_genero=not args.todos_los_generos,
    )