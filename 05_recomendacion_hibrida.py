"""
Recomendacion hibrida para usuarios nuevos o de baja actividad.
"""
import argparse
import heapq
import logging
import math
import re
import unicodedata

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOP_POPULARES_POR_DEFECTO = 15
MAX_PLAYLISTS_OCULTA_POR_DEFECTO = 2
SIMILARES_POR_POPULAR_POR_DEFECTO = 3
CODIFICACION_TEXTO = "utf-8"
CODIFICACION_ASCII = "ASCII"
NORMALIZACION_UNICODE = "NFKD"
PATRON_CONTENIDO_EXTRA = r"[\(\[].*?[\)\]]"
PATRON_MULETILLAS_SPOTIFY = r"\b(feat\.?|ft\.?|remix|remastered|version|radio edit|live)\b.*"
PATRON_DESDE_GUION = r"-.*"
PATRON_NO_ALFANUMERICO = r"[^a-z0-9]"


def normalizar_titulo_extremo(nombre: str) -> str:
    if not isinstance(nombre, str):
        return ""
    n = nombre.lower()
    n = re.sub(PATRON_CONTENIDO_EXTRA, "", n)
    n = re.sub(PATRON_MULETILLAS_SPOTIFY, "", n)
    n = re.sub(PATRON_DESDE_GUION, "", n)
    n = unicodedata.normalize(NORMALIZACION_UNICODE, n).encode(
        CODIFICACION_ASCII, "ignore"
    ).decode(CODIFICACION_TEXTO)
    return re.sub(PATRON_NO_ALFANUMERICO, "", n)


def obtener_popularidad(driver) -> dict:
    """Devuelve nombre_normalizado -> cantidad de playlists distintas."""
    query = f"""
    MATCH (c:{config.ETIQUETA_CANCION})<-[r:{config.RELACION_AGREGO_PLAYLIST}]-()
    RETURN c.{config.PROP_NOMBRE} AS nombre, count(DISTINCT r.{config.PROP_PLAYLIST}) AS num_playlists
    """
    popularidad = {}
    with driver.session() as session:
        res = session.run(query)
        for rec in res:
            if rec["nombre"]:
                clave = normalizar_titulo_extremo(rec["nombre"])
                if clave:
                    popularidad[clave] = popularidad.get(clave, 0) + rec["num_playlists"]
    return popularidad


def obtener_perfiles_audio(coleccion) -> dict:
    """Devuelve nombre_normalizado -> perfil de audio de MongoDB."""
    proyeccion = {
        config.CAMPO_NOMBRE_CANCION: 1,
        config.CAMPO_GENERO: 1,
        **{atributo: 1 for atributo in config.ATRIBUTOS_AUDIO},
    }
    res = coleccion.find({}, proyeccion)
    perfiles = {}
    for doc in res:
        nombre = doc.get(config.CAMPO_NOMBRE_CANCION)
        if not isinstance(nombre, str) or any(doc.get(a) is None for a in config.ATRIBUTOS_AUDIO):
            continue
        clave = normalizar_titulo_extremo(nombre)
        if clave and clave not in perfiles:
            perfiles[clave] = doc
    return perfiles


def calcular_estadisticas(perfiles: dict) -> dict:
    estadisticas = {}
    cantidad = len(perfiles)
    for atributo in config.ATRIBUTOS_AUDIO:
        valores = [perfil[atributo] for perfil in perfiles.values()]
        media = sum(valores) / cantidad
        varianza = sum((valor - media) ** 2 for valor in valores) / cantidad
        estadisticas[atributo] = (media, math.sqrt(varianza) or 1.0)
    return estadisticas


def vector_normalizado(perfil: dict, estadisticas: dict) -> list:
    return [
        (perfil[atributo] - estadisticas[atributo][0]) / estadisticas[atributo][1]
        for atributo in config.ATRIBUTOS_AUDIO
    ]


def distancia_euclidiana(vector_1: list, vector_2: list) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vector_1, vector_2)))


def agrupar_ocultas_por_genero(ocultas: list, perfiles: dict) -> dict:
    ocultas_por_genero = {}
    for clave_oculta in ocultas:
        genero = perfiles[clave_oculta].get(config.CAMPO_GENERO)
        ocultas_por_genero.setdefault(genero, []).append(clave_oculta)
    return ocultas_por_genero


def generar_recomendaciones(
    top_populares: int = TOP_POPULARES_POR_DEFECTO,
    max_playlists_oculta: int = MAX_PLAYLISTS_OCULTA_POR_DEFECTO,
    similares_por_popular: int = SIMILARES_POR_POPULAR_POR_DEFECTO,
    mismo_genero: bool = True,
) -> None:
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
            log.info(
                "-> %d canciones con popularidad + perfil de audio disponibles para recomendar.",
                len(popularidad_cruzada),
            )

            estadisticas = calcular_estadisticas(perfiles)
            semillas = sorted(popularidad_cruzada.items(), key=lambda kv: kv[1], reverse=True)[
                :top_populares
            ]
            ocultas = [
                clave
                for clave, n_playlists in popularidad_cruzada.items()
                if n_playlists <= max_playlists_oculta
            ]
            vectores_normalizados = {
                clave: vector_normalizado(perfil, estadisticas)
                for clave, perfil in perfiles.items()
            }
            ocultas_por_genero = agrupar_ocultas_por_genero(ocultas, perfiles)

            print("\n=== Recomendacion hibrida: populares + similares poco conocidas ===\n")

            for clave_popular, n_playlists in semillas:
                perfil_popular = perfiles[clave_popular]
                vector_popular = vectores_normalizados[clave_popular]
                genero_popular = perfil_popular.get(config.CAMPO_GENERO)

                claves_ocultas_candidatas = (
                    ocultas_por_genero.get(genero_popular, [])
                    if mismo_genero
                    else ocultas
                )

                def calcular_candidata(clave_oculta: str) -> tuple:
                    perfil_oculta = perfiles[clave_oculta]
                    vector_oculta = vectores_normalizados[clave_oculta]
                    distancia = distancia_euclidiana(vector_popular, vector_oculta)
                    return distancia, clave_oculta, perfil_oculta

                similares = heapq.nsmallest(
                    similares_por_popular,
                    (
                        calcular_candidata(clave_oculta)
                        for clave_oculta in claves_ocultas_candidatas
                        if clave_oculta != clave_popular
                    ),
                    key=lambda x: x[0],
                )

                print(
                    f"Popular: '{perfil_popular[config.CAMPO_NOMBRE_CANCION]}' "
                    f"(genero: {genero_popular}, en {n_playlists} playlists)"
                )
                if similares:
                    print("   Recomendaciones de descubrimiento:")
                    for distancia, clave_oculta, perfil in similares:
                        print(
                            f"      '{perfil[config.CAMPO_NOMBRE_CANCION]}' "
                            f"(distancia: {distancia:.3f}, "
                            f"en {popularidad_cruzada.get(clave_oculta, 0)} playlists)"
                        )
                else:
                    print("   (no se encontraron canciones similares de baja exposicion)")
                print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recomendacion hibrida: canciones populares + similares poco conocidas."
    )
    parser.add_argument("--top-populares", type=int, default=TOP_POPULARES_POR_DEFECTO)
    parser.add_argument("--max-playlists-oculta", type=int, default=MAX_PLAYLISTS_OCULTA_POR_DEFECTO)
    parser.add_argument("--similares-por-popular", type=int, default=SIMILARES_POR_POPULAR_POR_DEFECTO)
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
