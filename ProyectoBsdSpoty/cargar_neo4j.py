import pandas as pd
from neo4j import GraphDatabase

# --- CONFIGURACIÓN ---
URI = "bolt://localhost:7687"
USUARIO = "neo4j"
CONTRASENA = "hachi2603"
ARCHIVO = "spotify_dataset.csv"
LOTE_SIZE = 10000

def cargar_grafos(archivo_csv):
    print("Conectando a Neo4j (SpotyDB)...")
    driver = GraphDatabase.driver(URI, auth=(USUARIO, CONTRASENA))
    
    print(f"Leyendo el archivo {archivo_csv}...")
    df = pd.read_csv(archivo_csv, sep=',', quotechar='"', escapechar='\\', on_bad_lines='skip')
    
# 1. Limpiar nombres de columnas
    df.columns = df.columns.str.strip().str.replace('"', '')
    
    # 2. Filtrado estricto: Eliminamos filas si CUALQUIERA de estas columnas es nula
    # Esto elimina filas con playlist vacía, artista vacío o nombre de canción vacío
    df = df.dropna(subset=['user_id', 'trackname', 'artistname', 'playlistname'])
    
    # 3. Limpiar cualquier resto de espacios en blanco en los strings
    df['playlistname'] = df['playlistname'].str.strip()
    
    # 4. Limitar para la prueba (asegura que trabajamos con datos limpios)
    df = df.head(100000)
    
    datos = df.to_dict('records')
    total = len(datos)
    print(f"Total de registros limpios a inyectar: {total}")
    
    query = """
    UNWIND $filas AS fila
    MERGE (u:Usuario {id: fila.user_id})
    MERGE (c:Cancion {nombre: fila.trackname, artista: fila.artistname})
    MERGE (u)-[:AGREGO_A_PLAYLIST {playlist: fila.playlistname}]->(c)
    """
    
    print("Iniciando inyección por lotes...")
    with driver.session() as session:
        for i in range(0, total, LOTE_SIZE):
            lote = datos[i : i + LOTE_SIZE]
            session.run(query, filas=lote)
            print(f"Progreso: {min(i + LOTE_SIZE, total)} / {total} procesados...")
            
    driver.close()
    print("¡Grafo construido con éxito!")

if __name__ == "__main__":
    cargar_grafos(ARCHIVO)