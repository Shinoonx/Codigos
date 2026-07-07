"""
Consultas de valor "a nivel empresarial" para BsdSpoty.
Cada una combina el perfil sonoro (MongoDB) con el comportamiento social
en playlists (Neo4j) para responder preguntas de negocio concretas.

Consulta 1: Joyas ocultas
    Canciones con muy buen perfil sonoro (energía + bailabilidad altas)
    pero casi nula presencia en playlists. Útil para decidir qué
    canciones promocionar o priorizar en un feed de "descubrimiento".

Consulta 2: ADN sonoro de las playlists más grandes
    Perfil de audio promedio de las playlists con más canciones/usuarios
    únicos. Útil para entender qué combinación sonora "funciona" y
    replicarla al curar nuevas playlists o al hacer marketing de producto.

Consulta 3: Canciones puente entre géneros
    Canciones que aparecen en playlists junto a muchos géneros distintos
    al propio. Son candidatas naturales para recomendaciones cross-género
    (ampliar el gusto musical de un usuario más allá de su género habitual).

Todas las consultas trabajan sobre la intersección de canciones presentes
en ambos motores (mismo criterio que 03_cruzar_datos.py), porque ahí es
donde tenemos both perfil sonoro y datos sociales.
"""
import argparse
import logging
from collections import defaultdict

import pymongo
from neo4j import GraphDatabase

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades compartidas (mismo criterio de cruce que 03_cruzar_datos.py)
# ---------------------------------------------------------------------------

def obtener_nombres_neo4j(driver) -> dict:
    query = "MATCH (c:Cancion) RETURN DISTINCT c.nombre AS nombre"
    with driver.session() as session:
        res = session.run(query)
        return {str(r["nombre"]).strip().lower(): r["nombre"] for r in res if r["nombre"]}


def obtener_perfiles_mongo(coleccion) -> dict:
    """nombre_normalizado -> documento completo de Mongo (perfil sonoro)."""
    res = coleccion.find({}, {"track_name": 1, "track_genre": 1, "energy": 1,
                               "danceability": 1, "tempo": 1, "valence": 1, "popularity": 1})
    perfiles = {}
    for doc in res:
        nombre = doc.get("track_name")
        if isinstance(nombre, str):
            perfiles[nombre.strip().lower()] = doc
    return perfiles


def calcular_interseccion(driver, coleccion):
    log.info("Cargando nombres desde Neo4j y MongoDB para calcular la intersección...")
    dict_neo = obtener_nombres_neo4j(driver)
    perfiles_mongo = obtener_perfiles_mongo(coleccion)
    coincidencias = set(dict_neo.keys()) & set(perfiles_mongo.keys())
    log.info("-> %d canciones presentes en ambos motores.", len(coincidencias))
    return coincidencias, dict_neo, perfiles_mongo


# ---------------------------------------------------------------------------
# Consulta 1: Joyas ocultas
# ---------------------------------------------------------------------------

def consulta_joyas_ocultas(driver, coincidencias, dict_neo, perfiles_mongo,
                            max_playlists: int = 1, top_n: int = 10):
    """Canciones con buen perfil sonoro pero poca presencia social."""
    nombres_originales = [dict_neo[n] for n in coincidencias]

    query = """
    UNWIND $nombres AS nombre
    MATCH (c:Cancion {nombre: nombre})
    OPTIONAL MATCH (c)<-[r:AGREGO_A_PLAYLIST]-()
    RETURN nombre, count(DISTINCT r.playlist) AS num_playlists
    """
    with driver.session() as session:
        res = session.run(query, nombres=nombres_originales)
        exposicion = {rec["nombre"]: rec["num_playlists"] for rec in res}

    candidatos = []
    for n in coincidencias:
        nombre_original = dict_neo[n]
        num_playlists = exposicion.get(nombre_original, 0)
        if num_playlists > max_playlists:
            continue

        perfil = perfiles_mongo[n]
        energia = perfil.get("energy")
        bailabilidad = perfil.get("danceability")
        if energia is None or bailabilidad is None:
            continue

        score_calidad = (energia + bailabilidad) / 2
        candidatos.append((score_calidad, num_playlists, nombre_original, perfil))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    print("\n=== 💎 Consulta 1: Joyas ocultas ===")
    print(f"(canciones en <= {max_playlists} playlist(s) con mejor score de energía+bailabilidad)\n")
    for score, num_playlists, nombre, perfil in candidatos[:top_n]:
        print(f"🎵 {nombre}")
        print(f"   Score calidad: {score:.2f} | Playlists: {num_playlists} | "
              f"Género: {perfil.get('track_genre', 'N/A')}")
    if not candidatos:
        print("No se encontraron candidatos con los umbrales actuales.")
    return candidatos[:top_n]


# ---------------------------------------------------------------------------
# Consulta 2: ADN sonoro de las playlists más grandes
# ---------------------------------------------------------------------------

def consulta_adn_playlists(driver, perfiles_mongo, top_n: int = 5, max_canciones_por_playlist: int = 500):
    query = """
    MATCH (u:Usuario)-[r:AGREGO_A_PLAYLIST]->(c:Cancion)
    WITH r.playlist AS playlist, collect(DISTINCT c.nombre) AS canciones, count(DISTINCT u) AS usuarios
    RETURN playlist, canciones, size(canciones) AS num_canciones, usuarios
    ORDER BY num_canciones DESC
    LIMIT $top_n
    """
    with driver.session() as session:
        res = session.run(query, top_n=top_n)
        playlists = [dict(rec) for rec in res]

    print("\n=== 🎧 Consulta 2: ADN sonoro de las playlists más grandes ===\n")
    resultados = []
    for p in playlists:
        nombres_norm = [str(n).strip().lower() for n in p["canciones"][:max_canciones_por_playlist]]
        perfiles = [perfiles_mongo[n] for n in nombres_norm if n in perfiles_mongo]

        if not perfiles:
            continue

        metricas = ["energy", "danceability", "tempo", "valence", "popularity"]
        promedios = {}
        for m in metricas:
            valores = [pf[m] for pf in perfiles if pf.get(m) is not None]
            promedios[m] = sum(valores) / len(valores) if valores else None

        generos = defaultdict(int)
        for pf in perfiles:
            generos[pf.get("track_genre", "Desconocido")] += 1
        genero_dominante = max(generos.items(), key=lambda kv: kv[1])[0] if generos else "N/A"

        print(f"📀 Playlist: '{p['playlist']}' ({p['num_canciones']} canciones, {p['usuarios']} usuarios)")
        print(f"   Género dominante: {genero_dominante}")
        print(f"   Energía: {promedios['energy']:.2f} | Bailabilidad: {promedios['danceability']:.2f} | "
              f"Tempo: {promedios['tempo']:.1f} | Valencia: {promedios['valence']:.2f} | "
              f"Popularidad: {promedios['popularity']:.1f}\n" if all(v is not None for v in promedios.values())
              else "   (faltan algunas métricas de audio)\n")

        resultados.append({"playlist": p["playlist"], "promedios": promedios, "genero_dominante": genero_dominante})

    return resultados


# ---------------------------------------------------------------------------
# Consulta 3: Canciones puente entre géneros
# ---------------------------------------------------------------------------

def consulta_puentes_genero(driver, coincidencias, dict_neo, perfiles_mongo, top_n: int = 10):
    nombres_originales = [dict_neo[n] for n in coincidencias]

    query = """
    UNWIND $nombres AS nombre
    MATCH (u:Usuario)-[r:AGREGO_A_PLAYLIST]->(c:Cancion {nombre: nombre})
    RETURN DISTINCT r.playlist AS playlist, nombre
    """
    with driver.session() as session:
        res = session.run(query, nombres=nombres_originales)
        filas = [dict(rec) for rec in res]

    playlist_a_canciones = defaultdict(set)
    cancion_a_playlists = defaultdict(set)
    for f in filas:
        playlist_a_canciones[f["playlist"]].add(f["nombre"])
        cancion_a_playlists[f["nombre"]].add(f["playlist"])

    # Género de cada canción (usando el perfil de Mongo)
    genero_por_nombre_original = {
        dict_neo[n]: perfiles_mongo[n].get("track_genre", "Desconocido") for n in coincidencias
    }

    # Géneros presentes en cada playlist
    generos_por_playlist = {
        playlist: {genero_por_nombre_original.get(c) for c in canciones}
        for playlist, canciones in playlist_a_canciones.items()
    }

    candidatos = []
    for nombre_original, playlists in cancion_a_playlists.items():
        genero_propio = genero_por_nombre_original.get(nombre_original)
        generos_conectados = set()
        for pl in playlists:
            generos_conectados |= generos_por_playlist.get(pl, set())
        generos_conectados.discard(genero_propio)
        generos_conectados.discard(None)

        if generos_conectados:
            candidatos.append((len(generos_conectados), nombre_original, genero_propio, generos_conectados))

    candidatos.sort(key=lambda x: x[0], reverse=True)

    print("\n=== 🌉 Consulta 3: Canciones puente entre géneros ===\n")
    for score, nombre, genero_propio, generos_conectados in candidatos[:top_n]:
        muestra_generos = ", ".join(list(generos_conectados)[:5])
        print(f"🎵 {nombre} (género: {genero_propio})")
        print(f"   Conecta con {score} género(s) distintos: {muestra_generos}\n")
    if not candidatos:
        print("No se encontraron canciones puente con los datos actuales.")

    return candidatos[:top_n]


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def main(query: str, top_n: int, max_playlists_joya: int):
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
                consulta_joyas_ocultas(driver, coincidencias, dict_neo, perfiles_mongo,
                                        max_playlists=max_playlists_joya, top_n=top_n)
            if query in ("2", "all"):
                consulta_adn_playlists(driver, perfiles_mongo_completos, top_n=top_n)
            if query in ("3", "all"):
                consulta_puentes_genero(driver, coincidencias, dict_neo, perfiles_mongo, top_n=top_n)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consultas de negocio sobre BsdSpoty.")
    parser.add_argument("--query", choices=["1", "2", "3", "all"], default="all",
                         help="Qué consulta correr (por defecto: todas)")
    parser.add_argument("--top", type=int, default=10, help="Cantidad de resultados a mostrar")
    parser.add_argument("--max-playlists-joya", type=int, default=1,
                         help="Umbral de presencia social para considerar 'joya oculta'")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.query, args.top, args.max_playlists_joya)
