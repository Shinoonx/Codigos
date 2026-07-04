
# Estructura del árbol basado en la imagen
# Grafo como lista de adyacencia
arbol = {
    5: [3, 7],
    3: [2, 4],
    7: [8],
    2: [],
    4: [8],
    8: []
}

def dfs_explicado(arbol, inicio):
    """
    Implementa DFS (Búsqueda en Profundidad) con explicación detallada
    
    Args:
        arbol: Diccionario con la estructura del árbol
        inicio: Nodo de inicio
    """
    
    pila = [inicio]  # Pila LIFO (Last In, First Out)
    visitados = set()
    orden_visita = []
    
    print(f"Iniciando DFS desde nodo {inicio}")
    print("=" * 60)
    print(f"DFS utiliza una PILA (LIFO): el último elemento agregado")
    print(f"es el primero en ser procesado.")
    print("=" * 60)
    print()
    
    paso = 1
    while pila:
        nodo = pila.pop()  # Sacar del final de la pila (LIFO)
        
        if nodo not in visitados:
            visitados.add(nodo)
            orden_visita.append(nodo)
            
            print(f"Paso {paso}:")
            print(f"  Nodo procesado: {nodo}")
            print(f"  Visitados hasta ahora: {sorted(visitados)}")
            
            # Obtener vecinos
            vecinos = arbol.get(nodo, [])
            
            if vecinos:
                # Agregar vecinos en reversa para procesar en orden (izq a der)
                for vecino in reversed(vecinos):
                    pila.append(vecino)
                print(f"  Vecinos de {nodo}: {vecinos}")
                print(f"  Agregados a la pila (en reversa para order): {list(reversed(vecinos))}")
            else:
                print(f"  {nodo} es una hoja (sin vecinos)")
            
            print(f"  Pila actual: {pila}")
            print()
            paso += 1
    
    return orden_visita

def dfs_recursivo(arbol, nodo, visitados=None, orden=None, profundidad=0):
    """
    Implementación recursiva de DFS con visualización de la profundidad
    """
    if visitados is None:
        visitados = set()
        orden = []
    
    if nodo not in visitados:
        visitados.add(nodo)
        orden.append(nodo)
        
        # Mostrar la indentación según la profundidad
        indent = "  " * profundidad
        print(f"{indent}└─ Visitando nodo {nodo} (profundidad: {profundidad})")
        
        # Explorar recursivamente los vecinos
        vecinos = arbol.get(nodo, [])
        for vecino in vecinos:
            dfs_recursivo(arbol, vecino, visitados, orden, profundidad + 1)
        
        if not vecinos:
            print(f"{indent}   ↳ {nodo} es una hoja (backtrack)")
    
    return orden

# Ejecutar DFS
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SOLUCIÓN - PROBLEMA 3: DFS (Búsqueda en Profundidad)")
    print("=" * 60 + "\n")
    
    print("\n### VERSIÓN ITERATIVA (CON PILA) ###\n")
    orden_visita = dfs_explicado(arbol, 5)
    
    print("\n" + "=" * 60)
    print("RESULTADO - Orden de visita: " + " → ".join(map(str, orden_visita)))
    print("=" * 60 + "\n")
    
    print("\n### VERSIÓN RECURSIVA (CON PROFUNDIDAD VISUAL) ###\n")
    print("Árbol de recursión:")
    orden_recursiva = dfs_recursivo(arbol, 5)
    print(f"\nOrden de visita (recursiva): {' → '.join(map(str, orden_recursiva))}")
