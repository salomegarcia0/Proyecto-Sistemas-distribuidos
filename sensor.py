import random
import socket
import sys
import threading
import time

from protocolo import HOST, PUERTO, SECTORES, INTERVALO_HEARTBEAT, Conexion
from universo import generar_meteoritos, meteoritos_de_mi_sector

PROB_DUPLICADO = 0.1   # 10% de las veces manda la detección dos veces (simula un reenvío)


class Sensor:
    def __init__(self, sector):
        self.sector = sector
        self.conexion = None

    def conectar(self):
        sock = socket.create_connection((HOST, PUERTO))
        self.conexion = Conexion(sock)

        self.conexion.enviar("REGISTER", sector=self.sector)
        respuesta = self.conexion.recibir()
        print(f"[{self.sector}] Conectado. Semilla recibida: {respuesta['semilla']}")
        return respuesta["semilla"], respuesta["inicio"]

    def enviar_heartbeats(self):
        """Corre en su propio hilo: avisa que está vivo cada segundo."""
        while True:
            self.conexion.enviar("HEARTBEAT", sector=self.sector)
            time.sleep(INTERVALO_HEARTBEAT)

    def ejecutar(self):
        semilla, inicio = self.conectar()
        mis_meteoritos = meteoritos_de_mi_sector(generar_meteoritos(semilla), self.sector)

        hilo = threading.Thread(target=self.enviar_heartbeats, daemon=True)
        hilo.start()

        for segundo, meteor_id in mis_meteoritos:
            hora = inicio + segundo
            espera = hora - time.time()
            if espera < 0:
                continue                     # ese meteorito ya paso
            time.sleep(espera)

            self.conexion.enviar("DETECTION", sector=self.sector, meteor_id=meteor_id)
            print(f"[{self.sector}] Detectado meteorito #{meteor_id}")

            if random.random() < PROB_DUPLICADO:
                self.conexion.enviar("DETECTION", sector=self.sector, meteor_id=meteor_id)
                print(f"[{self.sector}] (reenvío duplicado de #{meteor_id})")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SECTORES:
        print("Uso: python sensor.py <SECTOR> (NO, N, NE, E, SE, S, SO, O)")
        sys.exit(1)
    try:
        Sensor(sys.argv[1]).ejecutar()
    except (ConnectionError, OSError):
        print("Se perdió la conexión con la Nave.")
    except KeyboardInterrupt:
        pass
