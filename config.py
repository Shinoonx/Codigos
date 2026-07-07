"""Configuracion compartida para los scripts de BsdSpoty."""
from __future__ import annotations

import os
from pathlib import Path


def _cargar_dotenv(ruta: str = ".env") -> None:
    ruta_env = Path(ruta)
    if not ruta_env.exists():
        return

    for linea_original in ruta_env.read_text(encoding="utf-8").splitlines():
        linea = linea_original.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue

        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave:
            os.environ.setdefault(clave, valor)


def _obtener_entero(nombre: str, valor_por_defecto: int) -> int:
    valor_crudo = os.getenv(nombre, str(valor_por_defecto)).strip()
    try:
        return int(valor_crudo)
    except ValueError as exc:
        raise ValueError(f"{nombre} debe ser un entero valido, recibido: {valor_crudo!r}") from exc


def _obtener_lista(nombre: str, valor_por_defecto: list[str]) -> list[str]:
    valor_crudo = os.getenv(nombre)
    if valor_crudo is None:
        return valor_por_defecto
    return [item.strip() for item in valor_crudo.split(",") if item.strip()]


_cargar_dotenv()

# Conexion a bases de datos.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "bsdspoty")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "canciones")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "hachi2603")

# Tamano de lote compartido por cargas grandes.
LOTE_SIZE = _obtener_entero("LOTE_SIZE", 1000)

# Campos compartidos del catalogo MongoDB.
CAMPO_NOMBRE_CANCION = os.getenv("CAMPO_NOMBRE_CANCION", "track_name")
CAMPO_GENERO = os.getenv("CAMPO_GENERO", "track_genre")
CAMPO_POPULARIDAD = os.getenv("CAMPO_POPULARIDAD", "popularity")
CAMPO_ENERGIA = os.getenv("CAMPO_ENERGIA", "energy")
CAMPO_BAILABILIDAD = os.getenv("CAMPO_BAILABILIDAD", "danceability")
CAMPO_TEMPO = os.getenv("CAMPO_TEMPO", "tempo")
CAMPO_VALENCIA = os.getenv("CAMPO_VALENCIA", "valence")

# Modelo compartido de Neo4j.
ETIQUETA_USUARIO = os.getenv("ETIQUETA_USUARIO", "Usuario")
ETIQUETA_CANCION = os.getenv("ETIQUETA_CANCION", "Cancion")
RELACION_AGREGO_PLAYLIST = os.getenv("RELACION_AGREGO_PLAYLIST", "AGREGO_A_PLAYLIST")
PROP_ID_USUARIO = os.getenv("PROP_ID_USUARIO", "id")
PROP_NOMBRE = os.getenv("PROP_NOMBRE", "nombre")
PROP_ARTISTA = os.getenv("PROP_ARTISTA", "artista")
PROP_PLAYLIST = os.getenv("PROP_PLAYLIST", "playlist")

# Atributos usados por mas de un algoritmo de recomendacion.
ATRIBUTOS_AUDIO = _obtener_lista(
    "ATRIBUTOS_AUDIO",
    [CAMPO_ENERGIA, CAMPO_BAILABILIDAD, CAMPO_TEMPO, CAMPO_VALENCIA],
)


def validar_config() -> None:
    faltantes = [
        nombre
        for nombre in (
            "MONGO_URI",
            "MONGO_DB",
            "MONGO_COLLECTION",
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
        )
        if not globals()[nombre]
    ]

    if LOTE_SIZE <= 0:
        faltantes.append("LOTE_SIZE debe ser mayor que 0")
    if not ATRIBUTOS_AUDIO:
        faltantes.append("ATRIBUTOS_AUDIO debe tener al menos un campo")

    if faltantes:
        raise ValueError("Configuracion incompleta: " + ", ".join(faltantes))
