import json
import threading

HOST = "127.0.0.1" 
PUERTO = 5000

SECTORES = ["NO", "N", "NE", "E", "SE", "S", "SO", "O"]

# (fila, columna) de cada sector en la matriz 3x3. El centro es la nave.
POS_MATRIZ = { "NO": (0, 0), "N": (0, 1), "NE": (0, 2), "O":  (1, 0), "E":  (1, 2), "SO": (2, 0), "S": (2, 1), "SE": (2, 2)}

INTERVALO_HEARTBEAT = 1   # el sensor avisa "sigo vivo" cada 1 segundo, esto para saber si la nave sigue contando con el 
TIMEOUT_HEARTBEAT = 3     # si pasan 3s sin aviso, la Nave lo da por perdido y se marca como gris en la interfaz


class Conexion:
    """Envuelve un socket para mandar y recibir mensajes JSON por lineas."""

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
        if not linea:      
            return None
        return json.loads(linea)

    def cerrar(self):
        self.sock.close()
