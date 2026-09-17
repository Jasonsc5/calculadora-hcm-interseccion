"""Verificacion contra el ejemplo resuelto en Mathcad (practica calificada).

Los cuatro accesos deben reproducir S, v, c, X, d1, d2, d3, d y la demora
global de la interseccion. Ejecutar con:  python test_calculos.py
"""
from math import isclose
from calculos import Config, Acceso, calcular, demora_interseccion

CFG = Config(ciclo=100.0, periodo=0.25, aislada=True, redondear=True,
             so=1900.0, et=2.0)

# fLT tomado como dato (1/EL) y fRT = 1/ER, segun la lectura de la figura.
ACCESOS = {
    "Norte": Acceso(nombre="Norte", ancho=3.6, en_metros=True, pesados=15,
                    pendiente=-1.0, estacionamiento=False, carriles=1,
                    paradero=True, buses=27, cbd=True,
                    flt=1 / 2.0, frt=0.85, flpb=0.928, frpb=0.893,
                    n60=220 + 22 + 9, phf=0.97, verde=50, k=0.5, cola_inicial=4),
    "Sur": Acceso(nombre="Sur", ancho=3.6, en_metros=True, pesados=15,
                  pendiente=1.0, estacionamiento=False, carriles=1,
                  paradero=True, buses=32, cbd=True,
                  flt=1 / 1.74, frt=0.85, flpb=1.0, frpb=1.0,
                  n60=350 + 52 + 30, phf=0.97, verde=50, k=0.5, cola_inicial=0),
    "Oeste": Acceso(nombre="Oeste", ancho=3.6, en_metros=True, pesados=12,
                    pendiente=-0.5, estacionamiento=True, maniobras=33,
                    carriles=1, paradero=False, cbd=True,
                    flt=1 / 2.06, frt=0.85, flpb=1.0, frpb=1.0,
                    n60=300 + 20 + 40, phf=0.95, verde=40, k=0.5, cola_inicial=0),
    "Este": Acceso(nombre="Este", ancho=3.6, en_metros=True, pesados=12,
                   pendiente=0.5, estacionamiento=True, maniobras=10,
                   carriles=1, paradero=False, cbd=True,
                   flt=1 / 1.90, frt=0.85, flpb=1.0, frpb=1.0,
                   n60=380 + 23 + 13, phf=0.95, verde=40, k=0.5, cola_inicial=3),
}

ESPERADO = {
    "Norte": dict(S=469.48, v=259, c=235, X=1.102, d1=25, d2=88.757, d3=61.277, d=175.034),
    "Sur":   dict(S=630.242, v=445, c=315, X=1.413, d1=25, d2=203.560, d3=0.0, d=228.560),
    "Oeste": dict(S=464.196, v=379, c=186, X=2.038, d1=30, d2=485.223, d3=0.0, d=515.223),
    "Este":  dict(S=579.129, v=438, c=232, X=1.888, d1=30, d2=415.435, d3=46.552, d=491.987),
}


def main():
    resultados = []
    fallos = 0
    for nombre, acc in ACCESOS.items():
        r = calcular(acc, CFG)
        resultados.append(r)
        for clave, valor in ESPERADO[nombre].items():
            obtenido = r[clave]
            ok = isclose(obtenido, valor, abs_tol=0.05)
            fallos += 0 if ok else 1
            marca = "OK" if ok else "XX"
            print(f"{marca}  {nombre:6} {clave:3}  esperado={valor:>10}  obtenido={obtenido:>12.4f}")

    inter = demora_interseccion(resultados)
    ok = isclose(inter["dI"], 366.734, abs_tol=0.1)
    fallos += 0 if ok else 1
    print(f"{'OK' if ok else 'XX'}  Interseccion  dI esperado=366.734  "
          f"obtenido={inter['dI']:.4f}  (LOS {inter['los']})")

    print("\n" + ("TODOS LOS VALORES COINCIDEN" if fallos == 0
                  else f"{fallos} DIFERENCIAS ENCONTRADAS"))
    return fallos


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
