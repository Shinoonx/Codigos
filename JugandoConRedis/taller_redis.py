import redis
import time

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def cargar_productos(lista_productos):
    for nombre, precio in lista_productos:
        nuevo_id = r.incr("id_producto")
        r.hset(f"producto:{nuevo_id}", mapping={"nombre": nombre, "precio": precio})
    print(f"Productos cargados. Último ID: {r.get('id_producto')}")


def gestionar_premium(correos_nuevos, eliminar=None):
    r.delete("usuarios_premium")
    
   
    if correos_nuevos:
        r.sadd("usuarios_premium", *correos_nuevos)
        print(f"\n Usuarios agregados :")
        print(f" {r.smembers('usuarios_premium')}")
    
   
    if eliminar:
        print(f"\n Eliminando usuario: {eliminar}")
        r.srem("usuarios_premium", *eliminar)
        
        usuarios_restantes = r.smembers("usuarios_premium")
        print(f"  Usuarios restantes después de la eliminación:")
        print(f"  {usuarios_restantes}")
    
  
    print(f" Usuarios {r.smembers('usuarios_premium')}")

def simular_tareas():
    r.lpush("prioridad:alta", "Fix bug crítico", "Subir servidor", "Backup DB")
    r.lpush("prioridad:baja", "Cambiar color botón", "Actualizar readme", "Limpiar log")
    
    print("Ejecutando tareas críticas:", r.lrange("prioridad:alta", 0, -1))

def crear_token():
    r.set("token_acceso", "ABC-123", ex=60) 
    print(f"Tiempo restante del token: {r.ttl('token_acceso')}s")

if __name__ == "__main__":

    premium = ["shinoon@mail.cl", "Anshyn@mail.com", "Pandemolde@redis.io"]

    cargar_productos([("RTX 4060", 300000), ("RAM 16GB", 45000), ("Monitor 144hz", 150000), ("Mouse Vxe", 50000)])
    gestionar_premium(premium, eliminar=["shinoon@mail.cl"])
    simular_tareas()
    crear_token()