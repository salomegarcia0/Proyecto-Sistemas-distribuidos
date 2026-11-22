import random
import socket
import sys
import threading
import time

from protocolo import HOST, PUERTO, SECTORES, INTERVALO_HEARTBEAT, Conexion
from universo import generar_meteoritos, meteoritos_de_mi_sector

PROB_DUPLICADO = 0.1   # 10% de las veces manda la detección dos veces (simula un reenvío)


class Sensor:
    def __init__(self, sector, es_alien=False):
        self.sector = sector
        self.es_alien = es_alien
        self.conexion = None
        self.sectores_activos = {sector}
        self.candado = threading.Lock()
        self.activo = True

    def conectar(self):
        sock = socket.create_connection((HOST, PUERTO))
        self.conexion = Conexion(sock)

        self.conexion.enviar("REGISTER", sector=self.sector)
        respuesta = self.conexion.recibir()
        if respuesta["tipo"] == "CUARENTENA": 
            raise ConnectionError("Sensor en cuarentena")    
        print(f"[{self.sector}] Conectado. Semilla recibida: {respuesta['semilla']}")
        return respuesta["semilla"], respuesta["inicio"]

    def enviar_heartbeats(self):
        """Corre en su propio hilo: avisa que está vivo cada segundo."""
        while self.activo:
            self.conexion.enviar("HEARTBEAT", sector=self.sector)
            time.sleep(INTERVALO_HEARTBEAT)

    def escuchar_nave(self):
        while self.activo:
            msg = self.conexion.recibir()
            if msg is None:
                self.activo = False
                break
            if msg["tipo"] == "ASSIGN":
                with self.candado:
                    self.sectores_activos = set(msg["sectores"])
                print(f"[{self.sector}] Cobertura actualizada: {sorted(self.sectores_activos)}")
            elif msg["tipo"] == "CUARENTENA":
                print(f"[{self.sector}] PUESTO EN CUARENTENA por la Nave.")
                self.activo = False
                break

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

        # si es alien, manda un meteorito falso a los 3 segundos
        if self.es_alien:
            time.sleep(3)
            print(f"[{self.sector}] (ALIEN) Enviando detección falsa #99999")
            self.conexion.enviar("DETECTION", origen=self.sector, sector=self.sector, meteor_id=99999)

        for segundo, meteor_id, sector in mis_meteoritos:
            if not self.activo:
                break
            hora = inicio + segundo
            espera = hora - time.time()
            if espera < 0:
                continue                     # ese meteorito ya paso
            time.sleep(espera)

            if not self.activo:
                break

            with self.candado:
                if sector not in self.sectores_activos:
                    continue

            self.conexion.enviar("DETECTION", origen=self.sector, sector=sector, meteor_id=meteor_id)
            print(f"[{self.sector}] Detectado meteorito #{meteor_id} en {sector}")

            if random.random() < PROB_DUPLICADO:
                self.conexion.enviar("DETECTION", origen=self.sector, sector=sector, meteor_id=meteor_id)
                print(f"[{self.sector}] (reenvío duplicado de #{meteor_id})")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in SECTORES:
        print("Uso: python sensor.py <SECTOR> [--alien]")
        sys.exit(1)
    es_alien = "--alien" in sys.argv
    try:
        Sensor(sys.argv[1], es_alien=es_alien).ejecutar()
    except (ConnectionError, OSError):
        print("Se perdió la conexión con la Nave.")
    except KeyboardInterrupt:
        pass
