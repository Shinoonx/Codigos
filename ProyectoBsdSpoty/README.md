# Proyecto BsdSpoty - Recomendación Híbrida

Este repositorio contiene el código fuente para la integración de MongoDB y Neo4j, desarrollado para la evaluación "Coup de grâce".

## ⚠️ Importante: Datos Masivos
Los archivos `.csv` superan el límite de tamaño de GitHub. Descárgalos desde nuestro Google Drive y colócalos en la raíz de este proyecto antes de ejecutar cualquier script:
* [Pega aquí el enlace a la carpeta de Google Drive]

## 📋 Lista de Tareas y Estado del Proyecto

- [x] **Selección de Bases de Datos (10%):** MongoDB (Documental) y Neo4j (Grafos) elegidas y configuradas. *(Nota: Falta redactar la justificación técnica para el informe).*
- [x] **Diseño y Carga de Datos (20%):** 
  - Catálogo de 114,000 canciones inyectado en MongoDB (`dataset.csv`).
  - 100,000 interacciones de playlists validadas e inyectadas en Neo4j (`spotify_dataset.csv`).
- [x] **Limpieza de Datos:** Scripts de carga (`cargar_neo4j.py`) blindados contra valores `NaN` y errores de formato.
- [x] **Extracción y Cruce de Información (30%):** Script `extraer_datos.py` finalizado. Conecta con ambos motores simultáneamente y cruza con éxito miles de registros en memoria ignorando diferencias de formato.
- [ ] **Análisis y Presentación de Resultados (30%):** 
  - Generar gráficos y visualizaciones con los datos cruzados.
  - Redactar el informe final detallado con conclusiones y recomendaciones.
- [ ] **Presentación Oral (10%):** 
  - Armar diapositivas de apoyo.
  - Preparar la exposición de 10-15 minutos (**excluyente: debe ser en inglés**).

## 🚀 Instrucciones de Ejecución

1. **Activar el entorno virtual:**
   ```bash
   source venv/bin/activate


   pip install pandas pymongo neo4j

   python extraer_datos.py