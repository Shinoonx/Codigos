import csv
import random
from datetime import datetime, timedelta

def generar_datos(cantidad=1000000, archivo='datos_sensores.csv'):
    fecha_inicio = datetime(2025, 1, 1)
    
    with open(archivo, mode='w', newline='') as file:
        writer = csv.writer(file)
        
        for i in range(1, cantidad + 1):
            fecha_hora = fecha_inicio + timedelta(minutes=i)
            sensor_id = random.randint(1, 10) # Suponiendo 10 sensores distintos
            temperatura = round(random.uniform(-10.0, 45.0), 2)
            humedad = round(random.uniform(0.0, 100.0), 2)
            velocidad_viento = round(random.uniform(0.0, 120.0), 2)
            
            writer.writerow([i, fecha_hora.strftime('%Y-%m-%d %H:%M:%S'), sensor_id, temperatura, humedad, velocidad_viento])

    print(f"¡Listo! Se generaron {cantidad} registros en '{archivo}'.")

if __name__ == '__main__':
    generar_datos()