import pandas as pd
from pymongo import MongoClient

def cargar_catalogo_mongodb(ruta_archivo, uri_conexion, nombre_db, nombre_coleccion):
    print("Iniciando el proceso de carga en MongoDB...")
    
    # 1. Conexión a la base de datos
    cliente = MongoClient(uri_conexion)
    db = cliente[nombre_db]
    coleccion = db[nombre_coleccion]
    
    # 2. Lectura y limpieza de datos con Pandas
    try:
        # Leemos el archivo considerando el carácter de escape
        df = pd.read_csv(ruta_archivo, escapechar='\\')
        
        # Eliminamos la columna 'Unnamed: 0' si existe, ya que es solo un índice del CSV
        if 'Unnamed: 0' in df.columns:
            df = df.drop(columns=['Unnamed: 0'])
            
        print(f"Archivo leído exitosamente. Total de canciones a cargar: {len(df)}")
        
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo en la ruta {ruta_archivo}")
        return

    # 3. Transformación a formato de documentos
    # Convertimos el DataFrame a una lista de diccionarios (equivalente a JSON)
    documentos = df.to_dict(orient='records')
    
    # 4. Inyección masiva
    if documentos:
        # Vaciamos la colección previa por si estamos haciendo pruebas
        coleccion.delete_many({}) 
        
        # insert_many es mucho más rápido que insertar uno por uno en un bucle
        resultado = coleccion.insert_many(documentos)
        print(f"¡Éxito! Se insertaron {len(resultado.inserted_ids)} documentos en la colección '{nombre_coleccion}'.")
    else:
        print("El archivo estaba vacío, no se insertaron datos.")

# Bloque principal de ejecución
if __name__ == "__main__":
    # Configuración de variables
    ARCHIVO_CSV = 'dataset.csv'
    # Por defecto, URI para una base local. 
    MONGO_URI = 'mongodb://localhost:27017/' 
    BASE_DE_DATOS = 'proyecto_musical'
    COLECCION = 'canciones'
    
    cargar_catalogo_mongodb(ARCHIVO_CSV, MONGO_URI, BASE_DE_DATOS, COLECCION)