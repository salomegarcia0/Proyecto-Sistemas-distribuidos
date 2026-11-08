
# comprueba que la regla de la matriz decide bien.

from matriz import crear_matriz, clasificar, ALERTA_ROJA, TRANSITO_SEGURO, SIN_AMENAZAS

casos = [
    # (sectores con 1, decision esperada, descripcion)
    ([],                    SIN_AMENAZAS,    "Estado 1 del PDF: todo en 0"),
    (["N"],                 ALERTA_ROJA,     "Estado 2 del PDF: objeto desde N"),
    (["NE", "E"],           TRANSITO_SEGURO, "Estado 3 del PDF: columna este"),
    (["O"],                 ALERTA_ROJA,     "Estado 4 del PDF: objeto desde O"),
    (["NO"],                ALERTA_ROJA,     "Estado 5 del PDF: objeto desde NO"),
    (["O", "NO"],           TRANSITO_SEGURO, "Borde: O y NO son vecinos (el anillo se cierra)"),
    (["NE", "O"],           ALERTA_ROJA,     "Borde: NE y O NO son vecinos"),
    (["SE", "S", "SO"],     TRANSITO_SEGURO, "Tres seguidos"),
    (["N", "E"],            ALERTA_ROJA,     "Dos aislados = dos amenazas"),
]

fallas = 0
for sectores, esperado, descripcion in casos:
    decision, _ = clasificar(crear_matriz(sectores))
    ok = decision == esperado
    fallas += not ok
    print(f"[{'OK' if ok else 'FALLA'}] {descripcion}: {sectores} -> {decision}")

print(f"\n{len(casos) - fallas}/{len(casos)} pruebas correctas")
