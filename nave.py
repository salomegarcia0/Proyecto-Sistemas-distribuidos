import queue
import random
import socket
import threading
import time

from protocolo import HOST, PUERTO, SECTORES, TIMEOUT_HEARTBEAT, Conexion
from matriz import crear_matriz, clasificar, matriz_a_texto

ESPERA_EVALUACION = 2   # segundos que espera para juntar todas las detecciones de un meteorito


class Nave:
    def __init__(self):
        self.semilla = random.randint(1, 9999)
        self.inicio = time.time()           # hora comun para todos los sensores

        self.cola_detecciones = queue.Queue()  #hilos de sensores -> evaluador
        self.cola_pantalla = queue.Queue()   #hilos de nave -> interfaz gráfica

        self.ultimo_heartbeat = {}    # sector -> hora del ultimo heartbeat
        self.conexiones = {}          # sector -> Conexion activa
        self.cobertura = {}     # sector -> set de sectores que cubre
        self.candado = threading.Lock()  # protege ultimo_heartbeat

    def avisar(self, *evento):
        """Manda un evento a la interfaz gráfica."""
        self.cola_pantalla.put(evento)

    def _buscar_vecino_vivo(self, sector_caido):
        """Busca el sensor conectado más cercano en SECTORES."""
        idx = SECTORES.index(sector_caido)
        for paso in range(1, len(SECTORES)):
            for direccion in (1, -1):
                candidato = SECTORES[(idx + paso * direccion) % len(SECTORES)]
                if candidato in self.conexiones:
                    return candidato
        return None

    def reasignar_cobertura(self, sector_caido):
        """Pasa los sectores del sensor caído a sus vecinos vivos."""
        envios = []
        with self.candado:
            huerfanos = self.cobertura.pop(sector_caido, {sector_caido})
            for huerfano in huerfanos:
                vecino = self._buscar_vecino_vivo(huerfano)
                if vecino:
                    self.cobertura[vecino].add(huerfano)
                    envios.append((self.conexiones[vecino], sorted(self.cobertura[vecino])))
                    print(f"Cobertura: {vecino} ahora cubre también a {huerfano}")

        for conn, lista in envios:
            try:
                conn.enviar("ASSIGN", sectores=lista)
            except OSError:
                pass

    def restaurar_cobertura(self, sector_nuevo, conexion):
        """Devuelve su sector original al sensor que se acaba de conectar."""
        envios = []
        with self.candado:
            for otro, sectores in self.cobertura.items():
                if sector_nuevo in sectores:
                    sectores.remove(sector_nuevo)
                    envios.append((self.conexiones[otro], sorted(sectores)))
            self.cobertura[sector_nuevo] = {sector_nuevo}
            envios.append((conexion, [sector_nuevo]))

        for conn, lista in envios:
            try:
                conn.enviar("ASSIGN", sectores=lista)
            except OSError:
                pass
            
    # conexiones

    def hilo_aceptar(self):
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((HOST, PUERTO))
        servidor.listen()
        print(f"Nave escuchando en {HOST}:{PUERTO}  (semilla {self.semilla})")

        while True:
            sock, direccion = servidor.accept()
            threading.Thread(target=self.hilo_sensor, args=(sock,), daemon=True).start()

    def hilo_sensor(self, sock):
        conexion = Conexion(sock)
        registro = conexion.recibir() # el primer mensaje siempre va a ser register
        sector = registro["sector"]
        conexion.enviar("CONFIG", semilla=self.semilla, inicio=self.inicio)
        with self.candado:
            self.ultimo_heartbeat[sector] = time.time()
        print(f"Sensor {sector} conectado")
        self.avisar("CONECTADO", sector)
        self.conexiones[sector] = conexion
        self.restaurar_cobertura(sector, conexion)
        while True: #va a escuchar mensajes hasta que se desconecte
            mensaje = conexion.recibir()
            if mensaje is None:
                break
            if mensaje["tipo"] == "HEARTBEAT":
                with self.candado:
                    self.ultimo_heartbeat[sector] = time.time()
            elif mensaje["tipo"] == "DETECTION":
                self.cola_detecciones.put(mensaje)

        conexion.cerrar()
        se_desconecto = False
        with self.candado:
            if self.conexiones.get(sector) is conexion:
                del self.conexiones[sector]
                self.ultimo_heartbeat.pop(sector, None)
                se_desconecto = True
        if se_desconecto:
            print(f"Sensor {sector} DESCONECTADO")
            self.avisar("DESCONECTADO", sector)
            self.reasignar_cobertura(sector)

    # heartbeats
    def hilo_monitor(self):
        """Si un sensor sigue conectado pero no manda heartbeat, se da por perdido."""
        while True:
            time.sleep(1)
            ahora = time.time()
            with self.candado:
                perdidos = [s for s, t in self.ultimo_heartbeat.items()
                            if ahora - t > TIMEOUT_HEARTBEAT]
                for s in perdidos:
                    del self.ultimo_heartbeat[s]
                    self.conexiones.pop(s, None)
            for s in perdidos:
                print(f"Sensor {s} sin heartbeat por {TIMEOUT_HEARTBEAT} s -> DESCONECTADO")
                self.avisar("DESCONECTADO", s)
                self.reasignar_cobertura(s)

    #decisiones
    def hilo_evaluador(self):
        pendientes = {}   # meteor_id -> {"llegada": hora, "sectores": set()}
        recibidos = set() # (meteor_id, sector) ya vistos, esto es para detectar duplicados

        while True:
            # saca la siguiente detección de la cola (si es que hay)
            try:
                det = self.cola_detecciones.get(timeout=0.1)
            except queue.Empty:
                det = None

            if det:
                clave = (det["meteor_id"], det["sector"])
                if clave in recibidos:
                    print(f"  Duplicado descartado: #{det['meteor_id']} desde {det['sector']}")
                    self.avisar("DUPLICADO", det["sector"], det["meteor_id"])
                else:
                    recibidos.add(clave)
                    if det["meteor_id"] not in pendientes:
                        pendientes[det["meteor_id"]] = {"llegada": time.time(), "sectores": set()}
                    pendientes[det["meteor_id"]]["sectores"].add(det["sector"])
                    print(f"  {det['sector']} detecta meteorito #{det['meteor_id']}")

            # luego, evalua los meteoritos que ya esperaron lo suficiente
            ahora = time.time()
            for meteor_id in list(pendientes):
                if ahora - pendientes[meteor_id]["llegada"] >= ESPERA_EVALUACION:
                    sectores = pendientes.pop(meteor_id)["sectores"]
                    matriz = crear_matriz(sectores)
                    decision, aislados = clasificar(matriz)
                    print(f"\n=== Meteorito #{meteor_id}: {decision}")
                    print(matriz_a_texto(matriz) + "\n")
                    self.avisar("DECISION", meteor_id, matriz, decision, sorted(sectores))

    def iniciar(self):
        for funcion in (self.hilo_aceptar, self.hilo_monitor, self.hilo_evaluador):
            threading.Thread(target=funcion, daemon=True).start()


if __name__ == "__main__":
    from ui import Pantalla
    nave = Nave()
    nave.iniciar()
    Pantalla(nave).ejecutar()     # la ventana ocupa el hilo principal