import pymongo
from neo4j import GraphDatabase

# --- CONFIGURACIÓN ---
URI_NEO = "bolt://localhost:7687"
USUARIO_NEO = "neo4j"
PASS_NEO = "hachi2603"

URI_MONGO = "mongodb://localhost:27017/"
DB_MONGO = "proyecto_musical" 
COL_MONGO = "canciones" 

def cruce_definitivo():
    print("1. Conectando a los motores de bases de datos...")
    driver_neo = GraphDatabase.driver(URI_NEO, auth=(USUARIO_NEO, PASS_NEO))
    cliente_mongo = pymongo.MongoClient(URI_MONGO)
    coleccion_mongo = cliente_mongo[DB_MONGO][COL_MONGO]

    print("2. Extrayendo nombres desde Neo4j...")
    query_neo = "MATCH (c:Cancion) RETURN DISTINCT c.nombre AS nombre"
    with driver_neo.session() as session:
        res_neo = session.run(query_neo)
        # Guardamos la versión limpia (llave) y la original (valor)
        dict_neo = {
            str(record["nombre"]).strip().lower(): record["nombre"] 
            for record in res_neo if record["nombre"]
        }
    print(f" -> Se extrajeron {len(dict_neo)} canciones únicas del grafo.")

    print("3. Extrayendo nombres desde MongoDB...")
    # Solo traemos la columna del nombre para que sea instantáneo
    res_mongo = coleccion_mongo.find({}, {"track_name": 1})
    dict_mongo = {}
    for doc in res_mongo:
        nombre = doc.get("track_name")
        if isinstance(nombre, str):
            dict_mongo[nombre.strip().lower()] = nombre
            
    print(f" -> Se leyeron {len(dict_mongo)} canciones únicas de Mongo.")

    print("4. Realizando el cruce en memoria (Intersección)...")
    # Encontramos los nombres que existen en AMBOS diccionarios
    coincidencias = set(dict_neo.keys()).intersection(set(dict_mongo.keys()))
    
    print(f" -> ¡Se encontraron {len(coincidencias)} coincidencias exactas ignorando formato!")

    if not coincidencias:
        print(" -> No hay coincidencias. Los datasets definitivamente no comparten canciones.")
    else:
        print("\n=======================================================")
        print("🎉 ¡CRUCE DE INFORMACIÓN EXITOSO! (MongoDB + Neo4j) 🎉")
        print("=======================================================\n")
        
        # Mostramos 5 ejemplos del cruce exitoso
        for nombre_normalizado in list(coincidencias)[:5]:
            nombre_original_mongo = dict_mongo[nombre_normalizado]
            nombre_original_neo = dict_neo[nombre_normalizado]
            
            # 1. Traer perfil de la canción desde MongoDB
            cancion_mongo = coleccion_mongo.find_one({"track_name": nombre_original_mongo})
            genero = cancion_mongo.get("track_genre", "Desconocido")
            energia = cancion_mongo.get("energy", "N/A")
            bailabilidad = cancion_mongo.get("danceability", "N/A")
            
            # 2. Traer relaciones (playlists) desde Neo4j
            query_quien = """
            MATCH (u:Usuario)-[r:AGREGO_A_PLAYLIST]->(c:Cancion {nombre: $nombre})
            RETURN r.playlist AS playlist LIMIT 3
            """
            with driver_neo.session() as session:
                res_playlists = session.run(query_quien, nombre=nombre_original_neo)
                playlists = [rec["playlist"] for rec in res_playlists]
                
            print(f"🎵 Pista: '{nombre_original_mongo}'")
            print(f"   📊 Perfil Técnico (MongoDB):")
            print(f"      - Género: {genero} | Energía: {energia} | Bailabilidad: {bailabilidad}")
            print(f"   👥 Interacciones (Neo4j):")
            print(f"      - Guardada en las playlists: {', '.join(playlists)}\n")
            
    driver_neo.close()

if __name__ == "__main__":
    cruce_definitivo()