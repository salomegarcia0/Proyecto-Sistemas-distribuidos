"""
matriz de amenazas 3x3 y la regla de decisión.

Si hay: 
  * Un 1 AISLADO           -> ALERTA ROJA, el meteorito viene directo a la nave
  * Dos o más 1 SEGUIDOS   -> TRÁNSITO SEGURO, pasa de lado
  * Todo en 0              -> SIN AMENAZAS, todo fino

Si un 1 está "aislado" se mira  sus dos vecinos en el anillo
NO-N-NE-E-SE-S-SO-O. Si ninguno de los dos está en 1, está aislado.
"""
from protocolo import SECTORES, POS_MATRIZ

ALERTA_ROJA = "ALERTA ROJA"
TRANSITO_SEGURO = "TRANSITO SEGURO"
SIN_AMENAZAS = "SIN AMENAZAS"


def crear_matriz(sectores_detectados):
    """Matriz 3x3 con 1 en los sectores que detectaron y 0 en el resto."""
    matriz = [[0, 0, 0],
              [0, 0, 0],
              [0, 0, 0]]
    for sector in sectores_detectados:
        fila, columna = POS_MATRIZ[sector]
        matriz[fila][columna] = 1
    return matriz


def vecinos(sector):
    """Los dos sectores pegados a este en el anillo."""
    i = SECTORES.index(sector)
    anterior = SECTORES[i - 1]                    
    siguiente = SECTORES[(i + 1) % len(SECTORES)]  
    return anterior, siguiente


def clasificar(matriz):
    """Aplica la regla. Devuelve (decision, lista_de_sectores_aislados)."""
    activos = [s for s, (f, c) in POS_MATRIZ.items() if matriz[f][c] == 1]

    if not activos:
        return SIN_AMENAZAS, []

    aislados = []
    for sector in activos:
        v1, v2 = vecinos(sector)
        if v1 not in activos and v2 not in activos:
            aislados.append(sector)

    if aislados:
        return ALERTA_ROJA, aislados
    return TRANSITO_SEGURO, []


def matriz_a_texto(matriz):
    return "\n".join(str(fila) for fila in matriz)
