
import os
import subprocess
import sys
import time

from protocolo import SECTORES

os.chdir(os.path.dirname(os.path.abspath(__file__)))  #busca para trabajar directamente en la carpeta del proyecto


def abrir_sensor(sector):
    return subprocess.Popen([sys.executable, "sensor.py", sector],
                            stdout=subprocess.DEVNULL)


nave = subprocess.Popen([sys.executable, "nave.py"])
time.sleep(1) # darle tiempo a la Nave de abrir el puerto
sensores = {s: abrir_sensor(s) for s in SECTORES}
print("Listo. Comandos: matar <SECTOR> | revivir <SECTOR> | salir")

try:
    while True:
        partes = input("> ").upper().split()
        if partes == ["SALIR"]:
            break
        if len(partes) == 2 and partes[1] in SECTORES:
            orden, sector = partes
            if orden == "MATAR":
                sensores[sector].kill()
                print(f"Sensor {sector} cerrado")
            elif orden == "REVIVIR":
                sensores[sector] = abrir_sensor(sector)
                print(f"Sensor {sector} abierto de nuevo")
        else:
            print("Comando no reconocido")
except (KeyboardInterrupt, EOFError):
    pass
finally:
    for proceso in sensores.values():
        proceso.kill()
    nave.kill()