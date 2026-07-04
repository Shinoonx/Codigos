import heapq

# Definir el grafo con pesos (costos)
# Formato: nodo -> [(vecino, costo), ...]
grafo = {
    'S': [('A', 1), ('C', 1), ('G', 12)],
    'A': [('B', 3), ('C', 1)],
    'B': [('D', 3)],
    'C': [('D', 1), ('G', 2)],
    'D': [('G', 3)],
    'G': []
}

def ucs_camino(grafo, inicio, destino):
    """
    Implementa UCS (Búsqueda de Costo Uniforme) para encontrar el camino
    de menor costo desde inicio hasta destino
    
    Args:
        grafo: Diccionario con la estructura del grafo ponderado
        inicio: Nodo de inicio
        destino: Nodo destino
    
    Returns:
        Tupla (camino, costo_total) o (None, float('inf')) si no existe
    """
    
    # Cola de prioridad: (costo_acumulado, nodo, camino)
    cola_prioridad = [(0, inicio, [inicio])]
    
    # Diccionario para rastrear el menor costo a cada nodo
    costo_minimo = {inicio: 0}
    
    # Conjunto de nodos ya procesados
    visitados = set()
    
    print(f"Iniciando UCS desde {inicio} hacia {destino}")
    print("-" * 60)
    
    paso = 1
    while cola_prioridad:
        costo_actual, nodo_actual, camino = heapq.heappop(cola_prioridad)
        
        print(f"Paso {paso}:")
        print(f"  Procesando nodo: {nodo_actual} (Costo: {costo_actual})")
        print(f"  Camino actual: {' → '.join(camino)} (Costo total: {costo_actual})")
        
        # Si ya fue visitado, saltamos
        if nodo_actual in visitados:
            print(f"  → Ya fue visitado, omitiendo...\n")
            paso += 1
            continue
        
        visitados.add(nodo_actual)
        
        # Si encontramos el destino, retornamos
        if nodo_actual == destino:
            print(f"\n✓ ¡Destino encontrado!")
            return camino, costo_actual
        
        # Explorar vecinos
        vecinos = grafo.get(nodo_actual, [])
        print(f"  Vecinos de {nodo_actual}:")
        
        for vecino, costo_arista in vecinos:
            nuevo_costo = costo_actual + costo_arista
            
            # Si no visitado o si encontramos un camino más barato
            if vecino not in visitados:
                if vecino not in costo_minimo or nuevo_costo < costo_minimo[vecino]:
                    costo_minimo[vecino] = nuevo_costo
                    heapq.heappush(cola_prioridad, (nuevo_costo, vecino, camino + [vecino]))
                    print(f"    → {vecino} (costo arista: {costo_arista}, costo total: {nuevo_costo})")
        
        print()
        paso += 1
    
    print(f"✗ No existe camino desde {inicio} hasta {destino}")
    return None, float('inf')

# Ejecutar UCS
if __name__ == "__main__":
    inicio = 'A'
    destino = 'G'
    
    camino, costo = ucs_camino(grafo, inicio, destino)
    
    print("-" * 60)
    if camino:
        print(f"\nRESULTADO FINAL:")
        print(f"Camino de {inicio} a {destino}: {' → '.join(camino)}")
        print(f"Costo total: {costo}")
    else:
        print(f"\nNo se encontró camino")
