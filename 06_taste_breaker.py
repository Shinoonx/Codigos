"""
Algoritmo Taste Breaker: recomienda canciones de generos nuevos que mantienen
un perfil sonoro cercano al usuario.
"""
import argparse
import heapq
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

MIN_CANCIONES_USUARIO = 10
MAX_CANCIONES_USUARIO = 50
MAX_INTENTOS_USUARIO = 15
MIN_CANCIONES_CRUZADAS_USUARIO = 3
TOP_GENEROS_USUARIO = 3
RECOMENDACIONES_POR_DEFECTO = 5
LIMITE_USUARIOS_ALEATORIOS = 1
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


def obtener_usuario_aleatorio(driver) -> str | None:
    query = f"""
    MATCH (u:{config.ETIQUETA_USUARIO})-[r:{config.RELACION_AGREGO_PLAYLIST}]->(c:{config.ETIQUETA_CANCION})
    WITH u, count(c) as total_canciones
    WHERE total_canciones >= $min_canciones AND total_canciones <= $max_canciones
    RETURN u.{config.PROP_ID_USUARIO} AS user_id
    ORDER BY rand()
    LIMIT $limite_usuarios
    """
    with driver.session() as session:
        res = session.run(
            query,
            min_canciones=MIN_CANCIONES_USUARIO,
            max_canciones=MAX_CANCIONES_USUARIO,
            limite_usuarios=LIMITE_USUARIOS_ALEATORIOS,
        ).single()
        return res["user_id"] if res else None


def obtener_canciones_usuario_normalizadas(driver, user_id: str) -> list:
    query = f"""
    MATCH (u:{config.ETIQUETA_USUARIO} {{{config.PROP_ID_USUARIO}: $user_id}})-[:{config.RELACION_AGREGO_PLAYLIST}]->(c:{config.ETIQUETA_CANCION})
    RETURN DISTINCT c.{config.PROP_NOMBRE} AS nombre
    """
    with driver.session() as session:
        return [
            normalizar_titulo_extremo(rec["nombre"])
            for rec in session.run(query, user_id=user_id)
            if rec["nombre"]
        ]


def obtener_diccionario_traduccion_mongo(coleccion) -> dict:
    """Crea un mapa clave_limpia -> nombre original de MongoDB."""
    res = coleccion.find({}, {config.CAMPO_NOMBRE_CANCION: 1})
    mapa = {}
    for doc in res:
        nombre = doc.get(config.CAMPO_NOMBRE_CANCION)
        if isinstance(nombre, str):
            clave = normalizar_titulo_extremo(nombre)
            if clave:
                mapa[clave] = nombre
    return mapa


def distancia_euclidiana(vector_1: list, vector_2: list) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vector_1, vector_2)))


def ejecutar_taste_breaker(
    user_id_obj: str | None = None,
    n_recomendaciones: int = RECOMENDACIONES_POR_DEFECTO,
) -> None:
    config.validar_config()

    with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as driver_neo:
        driver_neo.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]

            log.info("Generando mapa de traduccion de nombres en MongoDB...")
            mapa_mongo = obtener_diccionario_traduccion_mongo(coleccion)

            perfiles_usuario = []
            canciones_normalizadas_neo4j = []
            target_user = user_id_obj
            intentos = 0

            while not perfiles_usuario and intentos < MAX_INTENTOS_USUARIO:
                if not user_id_obj:
                    target_user = obtener_usuario_aleatorio(driver_neo)

                if not target_user:
                    log.error("No se encontro un usuario valido en Neo4j.")
                    return

                canciones_normalizadas_neo4j = obtener_canciones_usuario_normalizadas(driver_neo, target_user)
                nombres_originales_mongo = [
                    mapa_mongo[nombre]
                    for nombre in canciones_normalizadas_neo4j
                    if nombre in mapa_mongo
                ]

                if nombres_originales_mongo:
                    perfiles_usuario = list(
                        coleccion.find(
                            {config.CAMPO_NOMBRE_CANCION: {"$in": nombres_originales_mongo}},
                            {
                                config.CAMPO_NOMBRE_CANCION: 1,
                                config.CAMPO_GENERO: 1,
                                **{atributo: 1 for atributo in config.ATRIBUTOS_AUDIO},
                            },
                        )
                    )

                if len(perfiles_usuario) < MIN_CANCIONES_CRUZADAS_USUARIO:
                    if user_id_obj:
                        log.warning("El usuario no tiene suficientes canciones cruzadas en MongoDB.")
                        return
                    perfiles_usuario = []
                    intentos += 1

            if not perfiles_usuario:
                log.error("Se supero el limite de intentos buscando un usuario con datos cruzados.")
                return

            log.info("Usuario perfilado exitosamente: %s", target_user)
            log.info("-> Canciones originales en su playlist: %d", len(canciones_normalizadas_neo4j))
            log.info("-> Cruce en MongoDB: %d canciones para calcular ADN.", len(perfiles_usuario))

            generos = [doc.get(config.CAMPO_GENERO) for doc in perfiles_usuario if doc.get(config.CAMPO_GENERO)]
            top_generos = [genero for genero, _ in Counter(generos).most_common(TOP_GENEROS_USUARIO)]

            adn_usuario = {}
            for atributo in config.ATRIBUTOS_AUDIO:
                valores_validos = [doc[atributo] for doc in perfiles_usuario if doc.get(atributo) is not None]
                adn_usuario[atributo] = sum(valores_validos) / len(valores_validos) if valores_validos else 0

            print("\n=======================================================")
            print("PERFIL DEL USUARIO")
            print("=======================================================")
            print(f"Generos favoritos: {', '.join(top_generos)}")
            print("ADN acustico promedio:")
            for atributo in config.ATRIBUTOS_AUDIO:
                print(f"   - {atributo.capitalize()}: {adn_usuario[atributo]:.3f}")

            log.info("Buscando canciones fuera de su zona de confort...")
            query_rompe_burbujas = {
                config.CAMPO_GENERO: {"$nin": top_generos},
                config.CAMPO_ENERGIA: {"$ne": None},
                config.CAMPO_BAILABILIDAD: {"$ne": None},
            }
            proyeccion = {
                config.CAMPO_NOMBRE_CANCION: 1,
                config.CAMPO_GENERO: 1,
                **{atributo: 1 for atributo in config.ATRIBUTOS_AUDIO},
            }
            candidatos = coleccion.find(query_rompe_burbujas, proyeccion)

            vector_adn = [adn_usuario[atributo] for atributo in config.ATRIBUTOS_AUDIO]

            def calcular_recomendacion(doc: dict) -> tuple:
                vector_candidato = [doc.get(atributo, 0) for atributo in config.ATRIBUTOS_AUDIO]
                distancia = distancia_euclidiana(vector_adn, vector_candidato)
                return distancia, doc

            mejores_taste_breakers = heapq.nsmallest(
                n_recomendaciones,
                (calcular_recomendacion(doc) for doc in candidatos),
                key=lambda x: x[0],
            )

            print("\n=======================================================")
            print("TASTE BREAKERS")
            print("=======================================================")
            print("Canciones de generos nuevos que mantienen un perfil sonoro cercano:\n")

            for rank, (distancia, doc) in enumerate(mejores_taste_breakers, 1):
                print(f"{rank}. '{doc[config.CAMPO_NOMBRE_CANCION]}'")
                print(f"   Genero nuevo: {doc[config.CAMPO_GENERO]}")
                print(f"   Distancia al ADN del usuario: {distancia:.3f}")
                print(
                    f"   Perfil: Energy {doc.get(config.CAMPO_ENERGIA, 0):.2f} | "
                    f"Dance {doc.get(config.CAMPO_BAILABILIDAD, 0):.2f} | "
                    f"Tempo {doc.get(config.CAMPO_TEMPO, 0):.0f}\n"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Algoritmo Taste Breaker con normalizacion extrema.")
    parser.add_argument("--usuario", type=str, default=None)
    parser.add_argument(
        "--recomendaciones",
        type=int,
        default=RECOMENDACIONES_POR_DEFECTO,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ejecutar_taste_breaker(user_id_obj=args.usuario, n_recomendaciones=args.recomendaciones)
