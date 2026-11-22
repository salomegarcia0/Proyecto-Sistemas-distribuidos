import queue
import time
import tkinter as tk

from protocolo import HOST, PUERTO, POS_MATRIZ, SECTORES
from matriz import ALERTA_ROJA, TRANSITO_SEGURO, clasificar

# ---------------------------------------------------------------- estilo
FONDO, PANEL, BORDE = "#0b1020", "#121a33", "#223056"
TEXTO, SUAVE = "#e8ecff", "#8f9bc7"
VERDE, ROJO, AZUL, AMBAR = "#2ea36b", "#e53950", "#2f7de1", "#f0b429"
GRIS, CAIDO_BG, CAIDO_FG = "#3a4468", "#4a2430", "#ff9aa8"
ALIEN_BG, ALIEN_FG = "#5a1f7a", "#e8b4ff"
ROJO_OSCURO = "#7a1626"
CIAN = "#38e1ff"
C_PUBLICO, C_PRIVADO = "#7fb2ff", "#c9a7ff"       # color de la etiqueta de cada canal

FUENTE, MONO = "Segoe UI", "Consolas"             # si no existen, Tk usa una por defecto

# Estados posibles de un sensor
ESPERANDO, EN_LINEA, CAIDO, CUARENTENA = "esperando", "en línea", "caído", "en cuarentena"
# Canales de mensajes
PUBLICO, PRIVADO = "PÚBLICO", "PRIVADO"

MAX_HISTORIAL = 800


class Pantalla:
    def __init__(self, nave):
        self.nave = nave
        self.estados = {s: ESPERANDO for s in SECTORES}
        self.resaltado = {}                 # sector -> color (amenaza de la última decisión)
        self.contadores = {"alertas": 0, "transitos": 0, "duplicados": 0}
        self.historial = []                 # (hora, canal, texto, color_tag)
        self._flash_id = None
        self._resaltado_id = None

        self.ventana = tk.Tk()
        self.ventana.title("Aegis-Star · Centro de Mando")
        self.ventana.geometry("1000x640")
        self.ventana.minsize(920, 600)
        self.ventana.configure(bg=FONDO)
        self.ventana.columnconfigure(1, weight=1)
        self.ventana.rowconfigure(1, weight=1)

        self._construir_cabecera()
        izquierda = tk.Frame(self.ventana, bg=FONDO)
        izquierda.grid(row=1, column=0, sticky="ns", padx=(12, 6), pady=6)
        self._construir_sectores(izquierda)
        self._construir_decision(izquierda)
        self._construir_registro()
        self._construir_barra()

        self._pintar_sectores()
        self._actualizar_conexion()

    # ------------------------------------------------------ construcción
    def _tarjeta(self, padre, titulo):
        """Panel con borde y un título en mayúsculas pequeñas."""
        marco = tk.Frame(padre, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        tk.Label(marco, text=titulo, font=(FUENTE, 9, "bold"), fg=SUAVE, bg=PANEL
                 ).pack(anchor="w", padx=12, pady=(8, 2))
        return marco

    def _construir_cabecera(self):
        cab = tk.Frame(self.ventana, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        cab.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 6))
        tk.Label(cab, text="AEGIS-STAR", font=(FUENTE, 16, "bold"), fg=CIAN, bg=PANEL
                 ).pack(side="left", padx=(14, 6), pady=10)
        tk.Label(cab, text="Centro de Mando", font=(FUENTE, 11), fg=SUAVE, bg=PANEL
                 ).pack(side="left")
        # Lo último que se empaqueta a la derecha queda más a la izquierda.
        self.lbl_conexion = tk.Label(cab, font=(FUENTE, 12, "bold"), bg=PANEL)
        self.lbl_conexion.pack(side="right", padx=14)
        tk.Label(cab, text=f"Escuchando en {HOST}:{PUERTO}  ·  semilla {getattr(self.nave, 'semilla', '?')}",
                 font=(FUENTE, 9), fg=SUAVE, bg=PANEL).pack(side="right", padx=10)

    def _construir_sectores(self, padre):
        tarjeta = self._tarjeta(padre, "SECTORES (un sensor por sector)")
        tarjeta.pack(fill="x")
        rejilla = tk.Frame(tarjeta, bg=PANEL)
        rejilla.pack(padx=12, pady=(2, 6))
        self.cuadros = {}
        for sector, (fila, col) in POS_MATRIZ.items():
            cuadro = tk.Label(rejilla, width=11, height=3, font=(FUENTE, 10, "bold"))
            cuadro.grid(row=fila, column=col, padx=3, pady=3)
            self.cuadros[sector] = cuadro
        tk.Label(rejilla, text="NAVE", width=11, height=3, bg="#000000", fg=CIAN,
                 font=(FUENTE, 10, "bold"), highlightbackground=CIAN, highlightthickness=1
                 ).grid(row=1, column=1, padx=3, pady=3)

        # Leyenda de colores
        leyenda = tk.Frame(tarjeta, bg=PANEL)
        leyenda.pack(anchor="w", padx=12, pady=(0, 8))
        items = [(VERDE, "En línea"), (GRIS, "Esperando"), (CAIDO_FG, "Caído"), (ALIEN_FG, "Atacado Alien"),
                 (ROJO, "Amenaza directa"), (AZUL, "Tránsito lateral")]
        for i, (color, texto) in enumerate(items):
            tk.Label(leyenda, text="■", fg=color, bg=PANEL, font=(FUENTE, 10)
                     ).grid(row=i // 3, column=(i % 3) * 2, sticky="e")
            tk.Label(leyenda, text=texto, fg=SUAVE, bg=PANEL, font=(FUENTE, 8)
                     ).grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=(0, 8))

    def _construir_decision(self, padre):
        tarjeta = self._tarjeta(padre, "ÚLTIMA DECISIÓN")
        tarjeta.pack(fill="both", expand=True, pady=(8, 0))

        self.banner = tk.Frame(tarjeta, bg=GRIS)
        self.banner.pack(fill="x", padx=12, pady=(2, 8))
        self.lbl_decision = tk.Label(self.banner, text="Esperando meteoritos…", bg=GRIS, fg="white",
                                     font=(FUENTE, 15, "bold"), wraplength=330)
        self.lbl_decision.pack(pady=(8, 0))
        self.lbl_detalle = tk.Label(self.banner, text="Aún no se ha evaluado ningún meteorito",
                                    bg=GRIS, fg="#dfe4ff", font=(FUENTE, 9), wraplength=330)
        self.lbl_detalle.pack(pady=(0, 8))

        zona = tk.Frame(tarjeta, bg=PANEL)
        zona.pack(fill="x", padx=12, pady=(0, 10))
        # Mini matriz 3x3 (la misma que usó la Nave para decidir)
        mini = tk.Frame(zona, bg=PANEL)
        mini.pack(side="left")
        self.celdas = {}
        for sector, (fila, col) in POS_MATRIZ.items():
            celda = tk.Label(mini, text="0", width=3, height=1, bg=BORDE, fg=SUAVE,
                             font=(MONO, 12, "bold"))
            celda.grid(row=fila, column=col, padx=2, pady=2)
            self.celdas[sector] = celda
        tk.Label(mini, text="✦", width=3, bg=PANEL, fg=CIAN, font=(MONO, 12, "bold")
                 ).grid(row=1, column=1, padx=2, pady=2)

        # Contadores
        cuentas = tk.Frame(zona, bg=PANEL)
        cuentas.pack(side="right", padx=(10, 0))
        self.lbl_cuentas = {}
        for clave, titulo, color in (("alertas", "Alertas rojas", ROJO),
                                     ("transitos", "Tránsitos seguros", AZUL),
                                     ("duplicados", "Duplicados descartados", AMBAR)):
            fila = tk.Frame(cuentas, bg=PANEL)
            fila.pack(anchor="e", pady=1)
            tk.Label(fila, text=titulo, fg=SUAVE, bg=PANEL, font=(FUENTE, 9)).pack(side="left", padx=(0, 6))
            lbl = tk.Label(fila, text="0", fg=color, bg=PANEL, font=(FUENTE, 13, "bold"), width=3)
            lbl.pack(side="left")
            self.lbl_cuentas[clave] = lbl

    def _construir_registro(self):
        tarjeta = self._tarjeta(self.ventana, "REGISTRO DE MENSAJES")
        tarjeta.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)

        # Filtros
        filtros = tk.Frame(tarjeta, bg=PANEL)
        filtros.pack(fill="x", padx=12)
        self.ver_publicos = tk.BooleanVar(value=True)
        self.ver_privados = tk.BooleanVar(value=True)
        for var, texto, color in ((self.ver_publicos, "Mostrar PÚBLICOS", C_PUBLICO),
                                  (self.ver_privados, "Mostrar PRIVADOS", C_PRIVADO)):
            tk.Checkbutton(filtros, text=texto, variable=var, command=self._repintar_registro,
                           fg=color, bg=PANEL, selectcolor=FONDO, activebackground=PANEL,
                           activeforeground=color, font=(FUENTE, 9, "bold"), bd=0,
                           highlightthickness=0).pack(side="left", padx=(0, 14))

        # Explicación de los canales
        tk.Label(tarjeta, text="PÚBLICO = decisión de la Nave (afecta a toda la tripulación)",
                 fg=C_PUBLICO, bg=PANEL, font=(FUENTE, 8)).pack(anchor="w", padx=12, pady=(4, 0))
        tk.Label(tarjeta, text="PRIVADO = canal de un solo sensor (conexión, caída, duplicados)",
                 fg=C_PRIVADO, bg=PANEL, font=(FUENTE, 8)).pack(anchor="w", padx=12, pady=(0, 6))

        # Texto con scroll (solo lectura)
        cuerpo = tk.Frame(tarjeta, bg=PANEL)
        cuerpo.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        barra = tk.Scrollbar(cuerpo)
        barra.pack(side="right", fill="y")
        self.registro = tk.Text(cuerpo, bg="#0e1530", fg=TEXTO, font=(MONO, 10), wrap="word",
                                state="disabled", relief="flat", padx=8, pady=6,
                                yscrollcommand=barra.set, cursor="arrow", width=58)
        self.registro.pack(side="left", fill="both", expand=True)
        barra.config(command=self.registro.yview)
        for nombre, color in (("suave", SUAVE), ("rojo", ROJO), ("azul", "#6fa8ff"),
                              ("verde", "#4fd18f"), ("ambar", AMBAR),("morado", ALIEN_FG)):
            self.registro.tag_config(nombre, foreground=color)
        self.registro.tag_config("publico", foreground=C_PUBLICO, font=(MONO, 10, "bold"))
        self.registro.tag_config("privado", foreground=C_PRIVADO, font=(MONO, 10, "bold"))

    def _construir_barra(self):
        barra = tk.Frame(self.ventana, bg=PANEL, highlightbackground=BORDE, highlightthickness=1)
        barra.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 12))
        self.lbl_feedback = tk.Label(barra, anchor="w", font=(FUENTE, 10), bg=PANEL, fg=SUAVE,
                                     text="Listo. Esperando a que se conecten los 8 sensores…")
        self.lbl_feedback.pack(fill="x", padx=12, pady=6)

    # ------------------------------------------------------ actualización
    def _feedback(self, texto, color=TEXTO):
        self.lbl_feedback.config(text=texto, fg=color)

    def _en_linea(self):
        return sum(1 for e in self.estados.values() if e == EN_LINEA)

    def _actualizar_conexion(self):
        n, total = self._en_linea(), len(SECTORES)
        hay_caidos = any(e in (CAIDO, CUARENTENA) for e in self.estados.values())
        if n == total:
            texto, color = f"●  {n}/{total} sensores en línea", VERDE
        elif n == 0:
            texto, color = "●  Sin sensores conectados", ROJO
        elif hay_caidos:
            texto, color = f"●  {n}/{total} en línea · cobertura reducida", AMBAR
        else:
            texto, color = f"●  {n}/{total} conectados · esperando al resto", AMBAR
        self.lbl_conexion.config(text=texto, fg=color)

    def _pintar_sectores(self):
        """El estado se comunica con color Y texto (no solo con color)."""
        for sector, cuadro in self.cuadros.items():
            estado = self.estados[sector]
            if sector in self.resaltado:
                bg = self.resaltado[sector]
                cuadro.config(bg=bg, fg="white",
                              text=f"{sector}\n{'AMENAZA' if bg == ROJO else 'TRÁNSITO'}")
            elif estado == EN_LINEA:
                cuadro.config(bg=VERDE, fg="white", text=f"{sector}\n●  En línea")
            elif estado == CAIDO:
                cuadro.config(bg=CAIDO_BG, fg=CAIDO_FG, text=f"{sector}\n×  Caído")
            elif estado == CUARENTENA:
                cuadro.config(bg=ALIEN_BG, fg=ALIEN_FG, text=f"{sector}\n×  Atacado Alien")
            else:
                cuadro.config(bg=GRIS, fg="#c9d0ee", text=f"{sector}\n○  Esperando")

    def _contadores(self):
        for clave, lbl in self.lbl_cuentas.items():
            lbl.config(text=str(self.contadores[clave]))

    # ------------------------------------------------------ registro
    def _visible(self, canal):
        return self.ver_publicos.get() if canal == PUBLICO else self.ver_privados.get()

    def _escribir(self, entrada):
        hora, canal, texto, color = entrada
        self.registro.config(state="normal")
        self.registro.insert(tk.END, f"{hora}  ", "suave")
        self.registro.insert(tk.END, f"[{canal}] ", "publico" if canal == PUBLICO else "privado")
        self.registro.insert(tk.END, texto + "\n", color)
        self.registro.see(tk.END)
        self.registro.config(state="disabled")

    def _repintar_registro(self):
        self.registro.config(state="normal")
        self.registro.delete("1.0", tk.END)
        self.registro.config(state="disabled")
        for entrada in self.historial:
            if self._visible(entrada[1]):
                self._escribir(entrada)

    def registrar(self, canal, texto, color):
        entrada = (time.strftime("%H:%M:%S"), canal, texto, color)
        self.historial.append(entrada)
        if len(self.historial) > MAX_HISTORIAL:
            del self.historial[:200]
            self._repintar_registro()
        elif self._visible(canal):
            self._escribir(entrada)

    # ------------------------------------------------------ banner / alertas
    def _color_banner(self, color):
        for w in (self.banner, self.lbl_decision, self.lbl_detalle):
            w.config(bg=color)

    def _parpadear(self, restantes, claro=True):
        """La ALERTA ROJA parpadea unos segundos para llamar la atención."""
        if restantes == 0:
            self._color_banner(ROJO)
            return
        self._color_banner(ROJO if claro else ROJO_OSCURO)
        self._flash_id = self.ventana.after(300, self._parpadear, restantes - 1, not claro)

    def _limpiar_resaltado(self):
        self.resaltado = {}
        self._pintar_sectores()

    # ------------------------------------------------------ eventos
    def procesar(self, evento):
        tipo = evento[0]

        if tipo == "CONECTADO":
            sector = evento[1]
            self.estados[sector] = EN_LINEA
            self.registrar(PRIVADO, f"Sensor {sector}: conectado al Centro de Mando", "verde")
            self._feedback(f"Sensor {sector} conectado ({self._en_linea()}/{len(SECTORES)} en línea).", "#4fd18f")

        elif tipo == "DESCONECTADO":
            sector = evento[1]
            if self.estados[sector] == CAIDO:
                return                      # la Nave puede avisar dos veces: se ignora la repetida
            self.estados[sector] = CAIDO
            self.registrar(PRIVADO, f"Sensor {sector}: DESCONECTADO "
                                    f"(cobertura reducida a {self._en_linea()}/{len(SECTORES)})", "rojo")
            self._feedback(f"Sensor {sector} caído: el sector {sector} quedó sin vigilancia.", AMBAR)
            #self.ventana.bell()
        
        elif tipo == "CUARENTENA":
            sector = evento[1]
            self.estados[sector] = CUARENTENA
            self.registrar(PUBLICO, f"ALERTA ALIEN Sensor {sector} atacado -> en CUARENTENA", "morado")
            self._feedback(f"Sensor {sector} atacado por aliens! Aislado en cuarentena.", ALIEN_FG)

        elif tipo == "DUPLICADO":
            _, sector, meteor_id = evento
            self.contadores["duplicados"] += 1
            self.registrar(PRIVADO, f"Sensor {sector}: duplicado descartado (meteorito #{meteor_id})", "ambar")
            self._feedback(f"Se descartó un mensaje repetido del sensor {sector}.", AMBAR)
            self._contadores()

        elif tipo == "DECISION":
            self._decision(*evento[1:])

        self._pintar_sectores()
        self._actualizar_conexion()

    def _decision(self, meteor_id, matriz, decision, sectores):
        _, aislados = clasificar(matriz)

        # Mini matriz con los colores de la decisión
        for sector, celda in self.celdas.items():
            fila, col = POS_MATRIZ[sector]
            valor = matriz[fila][col]
            if valor:
                celda.config(text="1", bg=ROJO if sector in aislados else AZUL, fg="white")
            else:
                celda.config(text="0", bg=BORDE, fg=SUAVE)

        # Sectores resaltados unos segundos
        self.resaltado = {s: (ROJO if s in aislados else AZUL) for s in sectores}
        if self._resaltado_id:
            self.ventana.after_cancel(self._resaltado_id)
        self._resaltado_id = self.ventana.after(6000, self._limpiar_resaltado)

        if self._flash_id:
            self.ventana.after_cancel(self._flash_id)
            self._flash_id = None

        if decision == ALERTA_ROJA:
            origen = " y ".join(aislados)
            self.contadores["alertas"] += 1
            self.lbl_decision.config(text="ALERTA ROJA")
            self.lbl_detalle.config(text=f"Meteorito #{meteor_id} · colisión inminente desde {origen}")
            self._parpadear(10)
            self.registrar(PUBLICO, f"ALERTA ROJA: meteorito #{meteor_id} viene directo desde {origen}", "rojo")
            self._feedback(f"¡ALERTA ROJA! Colisión inminente desde {origen} (meteorito #{meteor_id}).", ROJO)
            #self.ventana.bell()
        elif decision == TRANSITO_SEGURO:
            por = ", ".join(sectores)
            self.contadores["transitos"] += 1
            self._color_banner(AZUL)
            self.lbl_decision.config(text="TRÁNSITO SEGURO")
            self.lbl_detalle.config(text=f"Meteorito #{meteor_id} · pasó de lado por {por}")
            self.registrar(PUBLICO, f"Tránsito seguro: meteorito #{meteor_id} pasó de lado por {por}", "azul")
            self._feedback(f"Meteorito #{meteor_id}: tránsito seguro, sin riesgo para la nave.", "#6fa8ff")
        else:
            self._color_banner(GRIS)
            self.lbl_decision.config(text="SIN AMENAZAS")
            self.lbl_detalle.config(text=f"Meteorito #{meteor_id} · sin riesgo")
            self.registrar(PUBLICO, f"Sin amenazas (meteorito #{meteor_id})", "suave")
        self._contadores()

    # ------------------------------------------------------ ciclo principal
    def revisar_cola(self):
        """Se ejecuta cada 100 ms: procesa los eventos que dejó la Nave."""
        try:
            while True:
                self.procesar(self.nave.cola_pantalla.get_nowait())
        except queue.Empty:
            pass
        self.ventana.after(100, self.revisar_cola)

    def ejecutar(self):
        self.revisar_cola()
        self.ventana.mainloop()