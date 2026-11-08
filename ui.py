import queue
import tkinter as tk

from protocolo import POS_MATRIZ
from matriz import ALERTA_ROJA, matriz_a_texto

GRIS, VERDE, ROJO, AZUL = "#9e9e9e", "#4caf50", "#e53935", "#1e88e5"


class Pantalla:
    def __init__(self, nave):
        self.nave = nave
        self.conectados = set()

        self.ventana = tk.Tk()
        self.ventana.title("Aegis-Star - Nave")

        # cuadricula 3x3
        cuadricula = tk.Frame(self.ventana)
        cuadricula.grid(row=0, column=0, padx=10, pady=10)
        self.cuadros = {}
        for sector, (fila, col) in POS_MATRIZ.items():
            cuadro = tk.Label(cuadricula, text=sector, width=8, height=3,
                              bg=GRIS, fg="white", font=("Arial", 14, "bold"))
            cuadro.grid(row=fila, column=col, padx=3, pady=3)
            self.cuadros[sector] = cuadro
        tk.Label(cuadricula, text="NAVE", width=8, height=3, bg="black", fg="white",
                 font=("Arial", 14, "bold")).grid(row=1, column=1, padx=3, pady=3)

        # ultima decisión y matriz
        self.texto_decision = tk.Label(self.ventana, text="Esperando meteoritos...",
                                       font=("Arial", 14, "bold"))
        self.texto_decision.grid(row=1, column=0, pady=5)
        self.texto_matriz = tk.Label(self.ventana, text=matriz_a_texto([[0] * 3] * 3),
                                     font=("Courier", 14))
        self.texto_matriz.grid(row=2, column=0)

        # lista de eventos
        self.lista = tk.Listbox(self.ventana, width=50, height=18)
        self.lista.grid(row=0, column=1, rowspan=3, padx=10, pady=10)

    def agregar_a_lista(self, texto):
        self.lista.insert(tk.END, texto)
        self.lista.see(tk.END)

    def pintar_estado_base(self):
        """Verde si el sensor está conectado, gris si no."""
        for sector, cuadro in self.cuadros.items():
            cuadro.config(bg=VERDE if sector in self.conectados else GRIS)

    def procesar(self, evento):
        tipo = evento[0]
        if tipo == "CONECTADO":
            self.conectados.add(evento[1])
            self.agregar_a_lista(f"Sensor {evento[1]} conectado")
        elif tipo == "DESCONECTADO":
            self.conectados.discard(evento[1])
            self.agregar_a_lista(f"Sensor {evento[1]} DESCONECTADO")
        elif tipo == "DUPLICADO":
            self.agregar_a_lista(f"Duplicado descartado: #{evento[2]} de {evento[1]}")
        elif tipo == "DECISION":
            _, meteor_id, matriz, decision, sectores = evento
            self.texto_matriz.config(text=matriz_a_texto(matriz))
            self.pintar_estado_base()
            color = ROJO if decision == ALERTA_ROJA else AZUL
            for s in sectores:
                self.cuadros[s].config(bg=color)
            self.texto_decision.config(text=f"#{meteor_id}: {decision}", fg=color)
            self.agregar_a_lista(f"#{meteor_id} {sectores} -> {decision}")
            return
        self.pintar_estado_base()

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