"""
universo.py - genera los meteoritos usando unsa semilla compartida

el random.Random(semilla) saca siempre la misma secuenia, 
entonces la nave le tira la misma semilla a los 8 nodos. Así todos generan el mismo universo
de meteoritos sin mandarse mensaje entre ellos por la red

Dos tipos de meteorito:
  * DIRECTO    -> pasa por 1 solo sector (va hacia la nave, hay colisión)
  * TANGENCIAL -> pasa por 2 o 3 sectores seguidos (pasa de lado, no hay colisión)
"""
import random

from protocolo import SECTORES


def generar_meteoritos(semilla, cantidad=300):
    """Lista de meteoritos. cada uno es un diccionario con esta forma:
    {"id": 5, "tipo": "TANGENCIAL", "pasos": [("N", 12.4), ("NE", 12.9)]}
    donde cada paso es (sector, segundo exactoen que lo cruza)"""
    rng = random.Random(semilla)
    meteoritos = []
    tiempo = 3.0                           

    for i in range(cantidad):
        tiempo += rng.uniform(1.5, 4.0)            # spam de meteoritos
        velocidad = rng.uniform(0.3, 0.7)          # q tan rapido pasan de un nodo a otro

        if rng.random() < 0.45:
            tipo = "DIRECTO"
            sectores = [rng.choice(SECTORES)]
        else:
            tipo = "TANGENCIAL"
            largo = rng.randint(2, 3)                       # cruza 2 o 3 sectores
            inicio = rng.randrange(8)                       # sector por donde entra
            sentido = rng.choice([1, -1])                   # a la derecha o a la izquierda
            sectores = [SECTORES[(inicio + sentido * k) % 8] for k in range(largo)]

        pasos = [(s, tiempo + k * velocidad) for k, s in enumerate(sectores)]
        meteoritos.append({"id": i, "tipo": tipo, "pasos": pasos})

    return meteoritos


def meteoritos_de_mi_sector(meteoritos, mi_sector):
    """Filtro, lista ordena de (segundo, id) de cada meteorito que cruza mi sector
       cada nodo corre esta funcion para quedarse SOLO con su propios metoeritos ordenados por tiempo
    """
    mios = []
    for m in meteoritos:
        for sector, segundo in m["pasos"]:
            if sector == mi_sector:
                mios.append((segundo, m["id"]))
    return sorted(mios)
