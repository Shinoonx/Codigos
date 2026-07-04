from collections import deque

# Definir el grafo basado en la imagen
# Las aristas se representan como: nodo -> [vecinos]
grafo = {
    'S': ['A', 'C', 'G'],
    'A': ['B', 'C'],
    'B': ['D'],
    'C': ['D', 'G'],
    'D': ['G'],
    'G': []
}

def bfs_camino(grafo, inicio, destino):
    """
    Implementa BFS para encontrar el camino desde inicio hasta destino
    
    Args:
        grafo: Diccionario con la estructura del grafo
        inicio: Nodo de inicio
        destino: Nodo destino
    
    Returns:
        Lista con el camino encontrado, o None si no existe
    """
    
    # Cola para almacenar los nodos a procesar
    # Cada elemento es una tupla (nodo_actual, camino_hasta_ahora)
    cola = deque([(inicio, [inicio])])
    
    # Conjunto para rastrear nodos ya visitados
    visitados = {inicio}
    
    # Lista para registrar el orden de exploración
    orden_exploracion = []
    
    print(f"Iniciando BFS desde {inicio} hacia {destino}")
    print("-" * 50)
    
    while cola:
        nodo_actual, camino = cola.popleft()
        orden_exploracion.append(nodo_actual)
        
        print(f"Procesando nodo: {nodo_actual}")
        print(f"  Camino actual: {' → '.join(camino)}")
        
        # Si encontramos el destino, retornamos el camino
        if nodo_actual == destino:
            print(f"\n✓ ¡Destino encontrado!")
            return camino
        
        # Explorar vecinos
        vecinos = grafo.get(nodo_actual, [])
        print(f"  Vecinos de {nodo_actual}: {vecinos}")
        
        for vecino in vecinos:
            if vecino not in visitados:
                visitados.add(vecino)
                cola.append((vecino, camino + [vecino]))
                print(f"    → Agregando {vecino} a la cola")
        
        print()
    
    # Si llegamos aquí, no hay camino
    print(f"✗ No existe camino desde {inicio} hasta {destino}")
    return None

# Ejecutar BFS
if __name__ == "__main__":
    inicio = 'A'
    destino = 'G'
    
    camino = bfs_camino(grafo, inicio, destino)
    
    print("-" * 50)
    if camino:
        print(f"\nRESULTADO FINAL:")
        print(f"Camino de {inicio} a {destino}: {' → '.join(camino)}")
        print(f"Número de pasos: {len(camino) - 1}")
    else:
        print(f"\nNo se encontró camino")
