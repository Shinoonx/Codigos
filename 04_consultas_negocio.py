"""
Consultas de negocio para BsdSpoty.

Cada consulta combina el perfil sonoro guardado en MongoDB con el comportamiento
social guardado en Neo4j.
"""
import argparse
import logging
from collections import defaultdict

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

TOP_RESULTADOS_POR_DEFECTO = 10
MAX_PLAYLISTS_JOYA_POR_DEFECTO = 1
MAX_CANCIONES_POR_PLAYLIST = 500
GENEROS_EJEMPLO = 5
METRICAS_NEGOCIO = [
    config.CAMPO_ENERGIA,
    config.CAMPO_BAILABILIDAD,
    config.CAMPO_TEMPO,
    config.CAMPO_VALENCIA,
    config.CAMPO_POPULARIDAD,
]


def obtener_nombres_neo4j(driver) -> dict:
    query = (
        f"MATCH (c:{config.ETIQUETA_CANCION}) "
        f"RETURN DISTINCT c.{config.PROP_NOMBRE} AS nombre"
    )
    with driver.session() as session:
        res = session.run(query)
        return {str(r["nombre"]).strip().lower(): r["nombre"] for r in res if r["nombre"]}


def obtener_perfiles_mongo(coleccion) -> dict:
    """Devuelve nombre_normalizado -> documento completo de MongoDB."""
    proyeccion = {
        config.CAMPO_NOMBRE_CANCION: 1,
        config.CAMPO_GENERO: 1,
        **{metrica: 1 for metrica in METRICAS_NEGOCIO},
    }
    res = coleccion.find({}, proyeccion)
    perfiles = {}
    for doc in res:
        nombre = doc.get(config.CAMPO_NOMBRE_CANCION)
        if isinstance(nombre, str):
            perfiles[nombre.strip().lower()] = doc
    return perfiles


def calcular_interseccion(driver, coleccion):
    log.info("Cargando nombres desde Neo4j y MongoDB para calcular la interseccion...")
    dict_neo = obtener_nombres_neo4j(driver)
    perfiles_mongo = obtener_perfiles_mongo(coleccion)
    coincidencias = set(dict_neo.keys()) & set(perfiles_mongo.keys())
    log.info("-> %d canciones presentes en ambos motores.", len(coincidencias))
    return coincidencias, dict_neo, perfiles_mongo


def consulta_joyas_ocultas(
    driver,
    coincidencias,
    dict_neo,
    perfiles_mongo,
    max_playlists: int = MAX_PLAYLISTS_JOYA_POR_DEFECTO,
    top_n: int = TOP_RESULTADOS_POR_DEFECTO,
):
    """Canciones con buen perfil sonoro pero poca presencia social."""
    nombres_originales = [dict_neo[n] for n in coincidencias]

    query = f"""
    UNWIND $nombres AS nombre
    MATCH (c:{config.ETIQUETA_CANCION} {{{config.PROP_NOMBRE}: nombre}})
    OPTIONAL MATCH (c)<-[r:{config.RELACION_AGREGO_PLAYLIST}]-()
    RETURN nombre, count(DISTINCT r.{config.PROP_PLAYLIST}) AS num_playlists
    """
    with driver.session() as session:
        res = session.run(query, nombres=nombres_originales)
        exposicion = {rec["nombre"]: rec["num_playlists"] for rec in res}

    candidatos = []
    for nombre_normalizado in coincidencias:
        nombre_original = dict_neo[nombre_normalizado]
        num_playlists = exposicion.get(nombre_original, 0)
        if num_playlists > max_playlists:
            continue

        perfil = perfiles_mongo[nombre_normalizado]
        energia = perfil.get(config.CAMPO_ENERGIA)
        bailabilidad = perfil.get(config.CAMPO_BAILABILIDAD)
        if energia is None or bailabilidad is None:
            continue

        score_calidad = (energia + bailabilidad) / 2
        candidatos.append((score_calidad, num_playlists, nombre_original, perfil))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    print("\n=== Consulta 1: Joyas ocultas ===")
    print(f"(canciones en <= {max_playlists} playlist(s) con mejor score de energia+bailabilidad)\n")
    for score, num_playlists, nombre, perfil in candidatos[:top_n]:
        print(f"Cancion: {nombre}")
        print(
            f"   Score calidad: {score:.2f} | Playlists: {num_playlists} | "
            f"Genero: {perfil.get(config.CAMPO_GENERO, 'N/A')}"
        )
    if not candidatos:
        print("No se encontraron candidatos con los umbrales actuales.")
    return candidatos[:top_n]


def consulta_adn_playlists(
    driver,
    perfiles_mongo,
    top_n: int = TOP_RESULTADOS_POR_DEFECTO,
    max_canciones_por_playlist: int = MAX_CANCIONES_POR_PLAYLIST,
):
    query = f"""
    MATCH (u:{config.ETIQUETA_USUARIO})-[r:{config.RELACION_AGREGO_PLAYLIST}]->(c:{config.ETIQUETA_CANCION})
    WITH r.{config.PROP_PLAYLIST} AS playlist, collect(DISTINCT c.{config.PROP_NOMBRE}) AS canciones, count(DISTINCT u) AS usuarios
    RETURN playlist, canciones, size(canciones) AS num_canciones, usuarios
    ORDER BY num_canciones DESC
    LIMIT $top_n
    """
    with driver.session() as session:
        res = session.run(query, top_n=top_n)
        playlists = [dict(rec) for rec in res]

    print("\n=== Consulta 2: ADN sonoro de las playlists mas grandes ===\n")
    resultados = []
    for playlist in playlists:
        nombres_norm = [
            str(nombre).strip().lower()
            for nombre in playlist["canciones"][:max_canciones_por_playlist]
        ]
        perfiles = [perfiles_mongo[nombre] for nombre in nombres_norm if nombre in perfiles_mongo]

        if not perfiles:
            continue

        promedios = {}
        for metrica in METRICAS_NEGOCIO:
            valores = [perfil[metrica] for perfil in perfiles if perfil.get(metrica) is not None]
            promedios[metrica] = sum(valores) / len(valores) if valores else None

        generos = defaultdict(int)
        for perfil in perfiles:
            generos[perfil.get(config.CAMPO_GENERO, "Desconocido")] += 1
        genero_dominante = max(generos.items(), key=lambda kv: kv[1])[0] if generos else "N/A"

        print(
            f"Playlist: '{playlist['playlist']}' "
            f"({playlist['num_canciones']} canciones, {playlist['usuarios']} usuarios)"
        )
        print(f"   Genero dominante: {genero_dominante}")
        if all(valor is not None for valor in promedios.values()):
            print(
                f"   Energia: {promedios[config.CAMPO_ENERGIA]:.2f} | "
                f"Bailabilidad: {promedios[config.CAMPO_BAILABILIDAD]:.2f} | "
                f"Tempo: {promedios[config.CAMPO_TEMPO]:.1f} | "
                f"Valencia: {promedios[config.CAMPO_VALENCIA]:.2f} | "
                f"Popularidad: {promedios[config.CAMPO_POPULARIDAD]:.1f}\n"
            )
        else:
            print("   (faltan algunas metricas de audio)\n")

        resultados.append(
            {
                "playlist": playlist["playlist"],
                "promedios": promedios,
                "genero_dominante": genero_dominante,
            }
        )

    return resultados


def consulta_puentes_genero(
    driver,
    coincidencias,
    dict_neo,
    perfiles_mongo,
    top_n: int = TOP_RESULTADOS_POR_DEFECTO,
):
    nombres_originales = [dict_neo[n] for n in coincidencias]

    query = f"""
    UNWIND $nombres AS nombre
    MATCH (u:{config.ETIQUETA_USUARIO})-[r:{config.RELACION_AGREGO_PLAYLIST}]->(c:{config.ETIQUETA_CANCION} {{{config.PROP_NOMBRE}: nombre}})
    RETURN DISTINCT r.{config.PROP_PLAYLIST} AS playlist, nombre
    """
    with driver.session() as session:
        res = session.run(query, nombres=nombres_originales)
        filas = [dict(rec) for rec in res]

    playlist_a_canciones = defaultdict(set)
    cancion_a_playlists = defaultdict(set)
    for fila in filas:
        playlist_a_canciones[fila["playlist"]].add(fila["nombre"])
        cancion_a_playlists[fila["nombre"]].add(fila["playlist"])

    genero_por_nombre_original = {
        dict_neo[n]: perfiles_mongo[n].get(config.CAMPO_GENERO, "Desconocido") for n in coincidencias
    }
    generos_por_playlist = {
        playlist: {genero_por_nombre_original.get(cancion) for cancion in canciones}
        for playlist, canciones in playlist_a_canciones.items()
    }

    candidatos = []
    for nombre_original, playlists in cancion_a_playlists.items():
        genero_propio = genero_por_nombre_original.get(nombre_original)
        generos_conectados = set()
        for playlist in playlists:
            generos_conectados |= generos_por_playlist.get(playlist, set())
        generos_conectados.discard(genero_propio)
        generos_conectados.discard(None)

        if generos_conectados:
            candidatos.append((len(generos_conectados), nombre_original, genero_propio, generos_conectados))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    print("\n=== Consulta 3: Canciones puente entre generos ===\n")
    for score, nombre, genero_propio, generos_conectados in candidatos[:top_n]:
        muestra_generos = ", ".join(list(generos_conectados)[:GENEROS_EJEMPLO])
        print(f"Cancion: {nombre} (genero: {genero_propio})")
        print(f"   Conecta con {score} genero(s) distintos: {muestra_generos}\n")
    if not candidatos:
        print("No se encontraron canciones puente con los datos actuales.")

    return candidatos[:top_n]


def main(
    query: str,
    top_n: int,
    max_playlists_joya: int,
    max_canciones_playlist: int,
) -> None:
    config.validar_config()

    with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)) as driver:
        driver.verify_connectivity()
        with pymongo.MongoClient(config.MONGO_URI) as cliente_mongo:
            coleccion = cliente_mongo[config.MONGO_DB][config.MONGO_COLLECTION]

            if query in ("1", "3", "all"):
                coincidencias, dict_neo, perfiles_mongo = calcular_interseccion(driver, coleccion)

            if query in ("2", "all"):
                perfiles_mongo_completos = obtener_perfiles_mongo(coleccion)

            if query in ("1", "all"):
                consulta_joyas_ocultas(
                    driver,
                    coincidencias,
                    dict_neo,
                    perfiles_mongo,
                    max_playlists=max_playlists_joya,
                    top_n=top_n,
                )
            if query in ("2", "all"):
                consulta_adn_playlists(
                    driver,
                    perfiles_mongo_completos,
                    top_n=top_n,
                    max_canciones_por_playlist=max_canciones_playlist,
                )
            if query in ("3", "all"):
                consulta_puentes_genero(driver, coincidencias, dict_neo, perfiles_mongo, top_n=top_n)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consultas de negocio sobre BsdSpoty.")
    parser.add_argument(
        "--query",
        choices=["1", "2", "3", "all"],
        default="all",
        help="Consulta a ejecutar",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=TOP_RESULTADOS_POR_DEFECTO,
        help="Cantidad de resultados a mostrar",
    )
    parser.add_argument(
        "--max-playlists-joya",
        type=int,
        default=MAX_PLAYLISTS_JOYA_POR_DEFECTO,
        help="Umbral de presencia social para considerar una joya oculta",
    )
    parser.add_argument(
        "--max-canciones-playlist",
        type=int,
        default=MAX_CANCIONES_POR_PLAYLIST,
        help="Maximo de canciones por playlist para calcular promedios",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.query, args.top, args.max_playlists_joya, args.max_canciones_playlist)
