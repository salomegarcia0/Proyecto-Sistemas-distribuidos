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
        self.sectores_activos = {sector}
        self.candado = threading.Lock()

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

    def escuchar_nave(self): 
        while True:
            msg = self.conexion.recibir()
            if msg is None:
                break
            if msg["tipo"] == "ASSIGN":
                with self.candado:
                    self.sectores_activos = set(msg["sectores"])
                print(f"[{self.sector}] Cobertura actualizada: {sorted(self.sectores_activos)}")

    def ejecutar(self):
        semilla, inicio = self.conectar()
        universo = generar_meteoritos(semilla)
        mis_meteoritos = sorted(
            (segundo, meteor_id, s)
            for s in SECTORES
            for segundo, meteor_id in meteoritos_de_mi_sector(universo, s)
        )

        hilo = threading.Thread(target=self.enviar_heartbeats, daemon=True)
        hilo.start()

        hilo_escucha = threading.Thread(target=self.escuchar_nave, daemon=True)
        hilo_escucha.start()

        for segundo, meteor_id, sector in mis_meteoritos:
            hora = inicio + segundo
            espera = hora - time.time()
            if espera < 0:
                continue                     # ese meteorito ya paso
            time.sleep(espera)

            with self.candado:
                if self.sector not in self.sectores_activos:
                    continue 

            self.conexion.enviar("DETECTION", sector=sector, meteor_id=meteor_id)
            print(f"[{self.sector}] Detectado meteorito #{meteor_id} en #{sector}")

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
