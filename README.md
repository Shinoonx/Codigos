# BsdSpoty - Recomendacion Hibrida con MongoDB y Neo4j

Este proyecto carga datos musicales en dos motores de base de datos y luego
ejecuta analisis cruzados para generar consultas de negocio y recomendaciones.

- MongoDB guarda el catalogo tecnico de canciones desde `dataset.csv`.
- Neo4j guarda interacciones usuario/playlist/cancion desde `spotify_dataset.csv`.
- Los scripts combinan ambos motores para encontrar coincidencias, patrones y
  recomendaciones.

Este README esta pensado para orientar tanto a una persona como a un agente que
trabaje en el repositorio.

## Archivos principales

- `01_cargar_mongodb.py`: carga `dataset.csv` en MongoDB.
- `02_cargar_neo4j.py`: carga `spotify_dataset.csv` en Neo4j.
- `03_cruzar_datos.py`: calcula cuantas canciones aparecen en ambos motores.
- `03_cruzar_datosa.py`: version con ejemplos detallados del cruce.
- `04_consultas_negocio.py`: ejecuta consultas de valor para analisis.
- `05_recomendacion_hibrida.py`: recomienda canciones ocultas similares a
  canciones populares.
- `06_taste_breaker.py`: recomienda canciones de generos nuevos con perfil
  sonoro parecido al usuario.

Archivos de apoyo:

- `config.py`: conexion y esquema compartido entre scripts.
- `.env.example`: plantilla para cambios locales.
- `requirements.txt`: dependencias de Python.
- `docker-compose.yml`: servicios locales de MongoDB y Neo4j.

## Datos requeridos

Los CSV no se suben a Git porque son pesados. Antes de ejecutar las cargas,
coloca estos archivos en la raiz del proyecto:

- `dataset.csv`
- `spotify_dataset.csv`

Estructura esperada:

```text
TallerBasesFinale/
  dataset.csv
  spotify_dataset.csv
  01_cargar_mongodb.py
  02_cargar_neo4j.py
  ...
```

## Preparacion

Desde PowerShell en la raiz del proyecto:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si el entorno virtual falta o esta roto:

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuracion

`config.py` contiene solo valores compartidos: conexion a MongoDB/Neo4j,
tamano de lote y nombres de campos/labels usados por varios scripts. Para
cambios locales de entorno, copia `.env.example` a `.env` y modifica lo que
necesites.

Ejemplo de valores globales:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=bsdspoty
MONGO_COLLECTION=canciones
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=hachi2603
LOTE_SIZE=1000
```

Los parametros de prueba rapida se pasan por CLI cuando existen:

- `python 01_cargar_mongodb.py dataset.csv --limite 1000`
- `python 02_cargar_neo4j.py spotify_dataset.csv --limite 1000`
- `python 04_consultas_negocio.py --top 5 --max-canciones-playlist 100`

Los valores internos que pertenecen a un solo flujo estan como constantes al
inicio del script correspondiente.

## Levantar bases de datos

```powershell
docker compose up -d
```

Neo4j Browser queda disponible en:

```text
http://localhost:7474
```

Credenciales por defecto:

```text
usuario: neo4j
contrasena: hachi2603
```

## Orden recomendado de ejecucion

1. Cargar catalogo en MongoDB:

`python 01_cargar_mongodb.py dataset.csv`

Para limpiar la coleccion antes de cargar:

`python 01_cargar_mongodb.py dataset.csv --vaciar`

Para una carga corta de prueba:

`python 01_cargar_mongodb.py dataset.csv --limite 1000`

2. Cargar interacciones en Neo4j:

`python 02_cargar_neo4j.py spotify_dataset.csv`

Para cargar todo:

`python 02_cargar_neo4j.py spotify_dataset.csv --limite 0`

Para una carga corta de prueba:

`python 02_cargar_neo4j.py spotify_dataset.csv --limite 1000`

3. Verificar el cruce entre motores:

`python 03_cruzar_datos.py`

Con ejemplos:

`python 03_cruzar_datosa.py --ejemplos 5`

4. Ejecutar consultas de negocio:

`python 04_consultas_negocio.py --query all --top 10`

Para acelerar la consulta de ADN de playlists:

`python 04_consultas_negocio.py --query 2 --top 5 --max-canciones-playlist 100`

5. Ejecutar recomendacion hibrida:

`python 05_recomendacion_hibrida.py`

6. Ejecutar Taste Breaker:

`python 06_taste_breaker.py`

Con un usuario especifico:

`python 06_taste_breaker.py --usuario USER_ID --recomendaciones 5`

## Validacion rapida

Estos comandos verifican que los scripts arrancan sin ejecutar cargas completas:

```powershell
python -m compileall 01_cargar_mongodb.py 02_cargar_neo4j.py 03_cruzar_datos.py 03_cruzar_datosa.py 04_consultas_negocio.py 05_recomendacion_hibrida.py 06_taste_breaker.py config.py
python -c "import config; config.validar_config(); print(config.MONGO_URI, config.NEO4J_URI)"
python 01_cargar_mongodb.py --help
python 02_cargar_neo4j.py --help
python 03_cruzar_datos.py --help
python 03_cruzar_datosa.py --help
python 04_consultas_negocio.py --help
python 05_recomendacion_hibrida.py --help
python 06_taste_breaker.py --help
```

## Notas para agentes

- No asumas que los CSV existen en Git; revisa si estan localmente.
- No ejecutes cargas completas si el usuario no pidio escrituras en la base.
- Usa `03_cruzar_datos.py` como verificacion principal de cruce.
- Mantiene `config.py` versionado: contiene conexion y esquema compartido.
- Mantiene `.env` fuera de Git: es solo para ajustes locales.
