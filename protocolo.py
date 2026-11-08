"""
protocolo.py aca esta lo q comparten la nave y los sensores.
  
Proyecto-Sistemas-distribuidos
  1. La dirección del servidor (HOST y PUERTO).
  2. La lista de los 8 sectores y su posición en la matriz 3x3.
  3. La clase conexion, que sabe enviar y recibir mensajes por el socket.

Formato de los mensajes: cada mensaje es un diccionario convertido a JSON
y enviado como UNA línea de texto terminada en "\n". Ejemplo:
    {"tipo": "DETECTION", "sector": "NE", "meteor_id": 17}
"""
import json
import threading

HOST = "127.0.0.1"   # la Nave corre en esta misma computadora
PUERTO = 5000

# Los 8 sectores en orden ALREDEDOR de la nave (como las agujas del reloj).
# En esta lista, cada sector es vecino del anterior y del siguiente,
# y el último (O) es vecino del primero (NO): es un anillo.
SECTORES = ["NO", "N", "NE", "E", "SE", "S", "SO", "O"]

# (fila, columna) de cada sector en la matriz 3x3. El centro es la nave.
POS_MATRIZ = {
    "NO": (0, 0), "N": (0, 1), "NE": (0, 2),
    "O":  (1, 0),              "E":  (1, 2),
    "SO": (2, 0), "S": (2, 1), "SE": (2, 2),
}

INTERVALO_HEARTBEAT = 1   # el sensor avisa "sigo vivo" cada 1 segundo, esto para saber si la nave sigue contando con el 
TIMEOUT_HEARTBEAT = 3     # si pasan 3 s sin aviso, la Nave lo da por perdido y se marca como gris en la interfaz


class Conexion:
    """Envuelve un socket para mandar y recibir mensajes JSON por líneas."""

    def __init__(self, sock):
        self.sock = sock
        self.archivo = sock.makefile("r", encoding="utf-8")  # para leer línea a línea
        self.candado = threading.Lock()  # evita que dos hilos escriban a la vez

    def enviar(self, tipo, **datos):
        mensaje = {"tipo": tipo, **datos}
        linea = json.dumps(mensaje) + "\n"
        with self.candado:
            self.sock.sendall(linea.encode("utf-8"))

    def recibir(self):
        """Devuelve el siguiente mensaje como diccionario, o None si se cerró."""
        try:
            linea = self.archivo.readline()
        except OSError:
            return None
        if not linea:          # línea vacía = el otro lado cerró la conexión
            return None
        return json.loads(linea)

    def cerrar(self):
        self.sock.close()
