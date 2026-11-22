import itertools
import queue
import random
import socket
import threading
import time

from protocolo import HOST, PUERTO, SECTORES, TIMEOUT_HEARTBEAT, Conexion
from matriz import crear_matriz, clasificar, matriz_a_texto
from universo import generar_meteoritos, meteoritos_de_mi_sector  # <--- NUEVO

ESPERA_EVALUACION = 2   # segundos que espera para juntar todas las detecciones de un meteorito


class Nave:
    def __init__(self):
        self.semilla = random.randint(1, 9999)
        self.inicio = time.time()           # hora comun para todos los sensores

        #verdad del universo para detectar sensores alien
        universo = generar_meteoritos(self.semilla)
        self.universo_real = {
            (meteor_id, s)
            for s in SECTORES
            for _, meteor_id in meteoritos_de_mi_sector(universo, s)
        }

        self.cola_detecciones = queue.Queue()     # hilos de sensores -> evaluador
        self.cola_prioridad = queue.PriorityQueue()  #(prioridad, orden, datos)
        self.desempate = itertools.count()           #evita comparar dicts/listas si empatan
        self.cola_pantalla = queue.Queue()        # hilos de nave -> interfaz gráfica

        self.ultimo_heartbeat = {}    # sector -> hora del ultimo heartbeat
        self.conexiones = {}          # sector -> Conexion activa
        self.cobertura = {}           # sector -> set de sectores que vigila
        self.cuarentena = set()
        self.candado = threading.Lock()

    def avisar(self, *evento):
        """Manda un evento a la interfaz gráfica."""
        self.cola_pantalla.put(evento)

    def _buscar_vecino_vivo(self, sector_caido):
        """Busca el sensor conectado más cercano en SECTORES (llamar dentro del candado)."""
        idx = SECTORES.index(sector_caido)
        for paso in range(1, len(SECTORES)):
            for direccion in (1, -1):
                candidato = SECTORES[(idx + paso * direccion) % len(SECTORES)]
                if candidato in self.conexiones and candidato not in self.cuarentena:
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
        registro = conexion.recibir()
        sector = registro["sector"]

        # <--- NUEVO: rechaza sensores en cuarentena
        with self.candado:
            if sector in self.cuarentena:
                print(f"Rechazada reconexión de {sector} (en cuarentena)")
                conexion.enviar("CUARENTENA")
                conexion.cerrar()
                return
            self.ultimo_heartbeat[sector] = time.time()
            self.conexiones[sector] = conexion

        conexion.enviar("CONFIG", semilla=self.semilla, inicio=self.inicio)
        self.restaurar_cobertura(sector, conexion)
        print(f"Sensor {sector} conectado")
        self.avisar("CONECTADO", sector)

        while True:
            mensaje = conexion.recibir()
            if mensaje is None:
                break
            if mensaje["tipo"] == "HEARTBEAT":
                with self.candado:
                    self.ultimo_heartbeat[sector] = time.time()
            elif mensaje["tipo"] == "DETECTION":
                mensaje.setdefault("origen", sector)
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

    # decisiones
    def hilo_evaluador(self):
        pendientes = {}   # meteor_id -> {"llegada": hora, "sectores": set()}
        recibidos = set() # (meteor_id, sector) ya vistos, esto es para detectar duplicados

        while True:
            try:
                det = self.cola_detecciones.get(timeout=0.1)
            except queue.Empty:
                det = None

            if det:
                origen = det["origen"]
                sector = det["sector"]
                meteor_id = det["meteor_id"]

                #validación contra sensores alien
                with self.candado:
                    en_cuarentena = origen in self.cuarentena
                    autorizado = sector in self.cobertura.get(origen, set())
                if en_cuarentena:
                    continue
                if (meteor_id, sector) not in self.universo_real or not autorizado:
                    print(f"¡ALERTA ALIEN! {origen} reportó dato falso (#{meteor_id} en {sector}) -> CUARENTENA")
                    with self.candado:
                        self.cuarentena.add(origen)
                        conn = self.conexiones.pop(origen, None)
                        self.ultimo_heartbeat.pop(origen, None)
                    if conn:
                        try:
                            conn.enviar("CUARENTENA")
                        except OSError:
                            pass
                        conn.cerrar()
                    self.avisar("CUARENTENA", origen)
                    self.reasignar_cobertura(origen)
                    continue

                clave = (meteor_id, sector)
                if clave in recibidos:
                    print(f"  Duplicado descartado: #{meteor_id} desde {sector}")
                    self.avisar("DUPLICADO", sector, meteor_id)
                else:
                    recibidos.add(clave)
                    if meteor_id not in pendientes:
                        pendientes[meteor_id] = {"llegada": time.time(), "sectores": set()}
                    pendientes[meteor_id]["sectores"].add(sector)
                    print(f"  {origen} detecta meteorito #{meteor_id} en {sector}")

            ahora = time.time()
            for meteor_id in list(pendientes):
                if ahora - pendientes[meteor_id]["llegada"] >= ESPERA_EVALUACION:
                    sectores = pendientes.pop(meteor_id)["sectores"]
                    matriz = crear_matriz(sectores)
                    decision, aislados = clasificar(matriz)

                    #en vez de imprimir directo, se manda a la cola de prioridad
                    prioridad = 1 if decision == "ALERTA ROJA" else 2
                    self.cola_prioridad.put((
                        prioridad,
                        next(self.desempate),
                        (meteor_id, matriz, decision, sorted(sectores))
                    ))

    #despacha primero las ALERTA ROJA (P1) y luego TRANSITO SEGURO (P2)
    def hilo_despachador(self):
        while True:
            prioridad, _, (meteor_id, matriz, decision, sectores) = self.cola_prioridad.get()
            accion = " -> ¡ESCUDOS ACTIVADOS / MANIOBRA EVASIVA!" if prioridad == 1 else ""
            print(f"\n=== [P{prioridad}] Meteorito #{meteor_id}: {decision}{accion}")
            print(matriz_a_texto(matriz) + "\n")
            self.avisar("DECISION", meteor_id, matriz, decision, sectores)
            self.cola_prioridad.task_done()

    def iniciar(self):
        for funcion in (self.hilo_aceptar, self.hilo_monitor, self.hilo_evaluador, self.hilo_despachador):
            threading.Thread(target=funcion, daemon=True).start()


if __name__ == "__main__":
    from ui import Pantalla
    nave = Nave()
    nave.iniciar()
    Pantalla(nave).ejecutar()     # la ventana ocupa el hilo principal