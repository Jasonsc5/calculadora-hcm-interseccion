"""Intersecciones semaforizadas - HCM 2010.

Nivel de servicio a partir de la demora de control de cada acceso y de la
demora global de la interseccion. Unidades internas: pies, segundos, veh/h.

El desarrollo reproduce el ejemplo resuelto en Mathcad (practica calificada):
redondea v y c a enteros como en esa fuente. Los factores de giro (fLT, fRT)
y de peatones/bicicletas (fLpb, fRpb) se ingresan como DATO, ya que dependen
de la lectura de la figura (tipo de carril, flujo opuesto, movimientos). El
resto de factores se calcula a partir de la geometria y la demanda del acceso.

Cadena de calculo por acceso:
    S  = So * fw * fHV * fg * fp * fbb * fa * fLU * fLT * fRT * fLpb * fRpb
    v  = n60 / PHF
    c  = S * (g/C)
    X  = v / c
    d  = d1 + d2 + d3     (uniforme + incremental + cola inicial)
Agregacion de la interseccion:
    dI = sum(di * vi) / sum(vi)
"""
from dataclasses import dataclass, asdict
from math import sqrt, floor, isfinite

PIES_POR_METRO = 1 / 0.3048

# Niveles de servicio HCM 2010 (interseccion semaforizada).
# Limite superior de la demora de control (s/veh) para cada nivel.
LOS_LIMITES = ((10.0, "A"), (20.0, "B"), (35.0, "C"), (55.0, "D"), (80.0, "E"))

# Valores maximos admitidos por el HCM para Nm (maniobras) y Nb (buses).
TOPE_MANIOBRAS = 180.0
TOPE_BUSES = 250.0


@dataclass(frozen=True)
class Config:
    """Parametros comunes a toda la interseccion."""
    ciclo: float = 100.0        # C, longitud del ciclo (s)
    periodo: float = 0.25       # T, duracion del analisis (h)
    aislada: bool = True        # interseccion aislada -> I = 1.0
    redondear: bool = True      # redondear v y c a enteros (como el ejemplo)
    so: float = 1900.0          # flujo de saturacion base (pc/h/ln)
    et: float = 2.0             # equivalente de vehiculo pesado


@dataclass(frozen=True)
class Acceso:
    """Datos de un acceso (grupo de carril)."""
    nombre: str = "Acceso"
    ancho: float = 3.6          # ancho de carril (en metros o pies)
    en_metros: bool = True      # unidad del ancho ingresado
    pesados: float = 0.0        # % de vehiculos pesados (camiones + buses)
    pendiente: float = 0.0      # Pg (%), + cuesta arriba / - cuesta abajo
    estacionamiento: bool = False
    maniobras: float = 0.0      # Nm, maniobras de estacionamiento (veh/h)
    carriles: int = 1           # N, carriles del grupo
    paradero: bool = False
    buses: float = 0.0          # Nb, buses que bloquean (buses/h)
    cbd: bool = False           # zona central de negocios -> fa = 0.9
    flu: float = 1.0            # dato (1.00 para un solo carril)
    flt: float = 1.0            # dato (1/EL)
    frt: float = 1.0            # dato (1/ER)
    flpb: float = 1.0           # dato
    frpb: float = 1.0           # dato
    n60: float = 0.0            # aforo de 1 h (veh mixtos)
    phf: float = 0.95
    verde: float = 0.0          # g, verde efectivo (s)
    k: float = 0.5              # 0.5 permitido / 1.0 protegido
    cola_inicial: float = 0.0   # Qb (veh)


class DatosInvalidos(ValueError):
    pass


def _round_int(x):
    """Redondeo al entero mas cercano, mitades hacia afuera (como Mathcad)."""
    return float(floor(x + 0.5)) if x >= 0 else -float(floor(-x + 0.5))


def ancho_pies(acceso):
    """Ancho del carril en pies (el HCM usa pies para fw)."""
    return acceso.ancho * PIES_POR_METRO if acceso.en_metros else acceso.ancho


def factor_ancho(ancho_ft):
    """Exhibit fw: <10 -> 0.96 ; 10 a 12.9 -> 1.00 ; >12.9 -> 1.04 (pies)."""
    if ancho_ft < 10.0:
        return 0.96
    if ancho_ft <= 12.9:
        return 1.00
    return 1.04


def factor_estacionamiento(N, Nm):
    """fp = [N - 0.1 - 18*Nm/3600]/N >= 0.05. Nm topado en 180 veh/h."""
    Nm = min(Nm, TOPE_MANIOBRAS)
    return max(0.05, (N - 0.1 - 18.0 * Nm / 3600.0) / N)


def factor_buses(N, Nb):
    """fbb = [N - 14.4*Nb/3600]/N >= 0.05. Nb topado en 250 buses/h."""
    Nb = min(Nb, TOPE_BUSES)
    return max(0.05, (N - 14.4 * Nb / 3600.0) / N)


def factor_aguas_arriba(X, aislada):
    """I = 1.0 si la interseccion es aislada; si no, I = 1 - 0.91*X^2.68 >= 0.09."""
    if aislada:
        return 1.0
    return max(0.09, 1.0 - 0.91 * X ** 2.68)


def nivel_demora(d):
    """Nivel de servicio segun la demora de control (s/veh)."""
    for limite, nivel in LOS_LIMITES:
        if d <= limite:
            return nivel
    return "F"


def demora_uniforme(C, gC, X):
    """d1 = 0.5*C*(1 - g/C)^2 / (1 - min(1,X)*g/C)."""
    return 0.5 * C * (1 - gC) ** 2 / (1 - min(1.0, X) * gC)


def demora_incremental(X, c, T, k, I):
    """d2 = 900*T*[(X-1) + sqrt((X-1)^2 + 8*k*I*X/(c*T))]."""
    return 900.0 * T * ((X - 1) + sqrt((X - 1) ** 2 + 8.0 * k * I * X / (c * T)))


def demora_cola_inicial(Qb, v, c, T):
    """d3 con la formulacion de cola inicial del HCM 2010.

    Devuelve (d3, detalle) donde detalle trae tA, Qe y Qev.
    """
    if Qb <= 0 or v <= 0:
        return 0.0, dict(tA=0.0, Qe=0.0, Qev=0.0)
    if v >= c:
        tA = T
        Qev = T * (v - c)
    else:
        tA = Qb / (c - v)
        Qev = 0.0
    Qe = Qb + tA * (v - c)
    d3 = (3600.0 / (v * T)) * (
        tA * (Qb + Qe - Qev) / 2.0
        + (Qe ** 2 - Qev ** 2) / (2.0 * c)
        - Qb ** 2 / (2.0 * c)
    )
    return d3, dict(tA=tA, Qe=Qe, Qev=Qev)


def validar(a, cfg):
    errores = []
    valores = {**asdict(a), **{f"cfg_{k}": v for k, v in asdict(cfg).items()}}
    for clave, valor in valores.items():
        if isinstance(valor, (bool, str)):
            continue
        if not isinstance(valor, (int, float)) or not isfinite(valor):
            errores.append(f"{clave}: ingresa un numero finito.")
    if errores:
        raise DatosInvalidos(" ".join(errores))
    if a.carriles < 1 or a.carriles != int(a.carriles):
        errores.append("Los carriles del grupo (N) deben ser un entero >= 1.")
    if a.ancho <= 0:
        errores.append("El ancho de carril debe ser mayor que cero.")
    if not -6.0 <= a.pendiente <= 10.0:
        errores.append("La pendiente Pg debe estar entre -6 % y +10 %.")
    if not 0.25 <= a.phf <= 1.0:
        errores.append("El PHF debe estar entre 0.25 y 1.")
    if not 0 <= a.pesados <= 100:
        errores.append("El porcentaje de pesados debe estar entre 0 y 100.")
    if a.n60 < 0 or a.verde < 0 or a.maniobras < 0 or a.buses < 0:
        errores.append("Aforo, verde, maniobras y buses no pueden ser negativos.")
    if a.cola_inicial < 0:
        errores.append("La cola inicial (Qb) no puede ser negativa.")
    for nombre, f in (("fLU", a.flu), ("fLT", a.flt), ("fRT", a.frt),
                      ("fLpb", a.flpb), ("fRpb", a.frpb)):
        if not 0 < f <= 1.0:
            errores.append(f"{nombre} debe estar en el intervalo (0, 1].")
    if cfg.ciclo <= 0:
        errores.append("La longitud del ciclo (C) debe ser mayor que cero.")
    if a.verde > cfg.ciclo:
        errores.append("El verde efectivo (g) no puede superar el ciclo (C).")
    if cfg.periodo <= 0:
        errores.append("El periodo de analisis (T) debe ser mayor que cero.")
    if cfg.so <= 0 or cfg.et < 1:
        errores.append("Revisa el flujo base (So>0) y el equivalente ET (>=1).")
    if errores:
        raise DatosInvalidos(" ".join(errores))


def calcular(a, cfg):
    """Calculo completo de un acceso. Devuelve un dict con intermedios y LOS."""
    validar(a, cfg)
    w = ancho_pies(a)
    fw = factor_ancho(w)
    fhv = 100.0 / (100.0 + a.pesados * (cfg.et - 1.0))
    fg = 1.0 - a.pendiente / 200.0
    fp = factor_estacionamiento(a.carriles, a.maniobras) if a.estacionamiento else 1.0
    fbb = factor_buses(a.carriles, a.buses) if a.paradero else 1.0
    fa = 0.9 if a.cbd else 1.0
    S = (cfg.so * fw * fhv * fg * fp * fbb * fa
         * a.flu * a.flt * a.frt * a.flpb * a.frpb)

    v_exacto = a.n60 / a.phf
    v = _round_int(v_exacto) if cfg.redondear else v_exacto
    gC = a.verde / cfg.ciclo
    c_exacto = S * gC
    c = _round_int(c_exacto) if cfg.redondear else c_exacto
    if c <= 0:
        raise DatosInvalidos("La capacidad resulto <= 0. Revisa g, C y los factores.")

    X = v / c
    d1 = demora_uniforme(cfg.ciclo, gC, X)
    I = factor_aguas_arriba(X, cfg.aislada)
    d2 = demora_incremental(X, c, cfg.periodo, a.k, I)
    d3, cola = demora_cola_inicial(a.cola_inicial, v, c, cfg.periodo)
    d = d1 + d2 + d3

    return dict(
        nombre=a.nombre, ancho_ft=w, fw=fw, fhv=fhv, fg=fg, fp=fp, fbb=fbb,
        fa=fa, flu=a.flu, flt=a.flt, frt=a.frt, flpb=a.flpb, frpb=a.frpb,
        S=S, v_exacto=v_exacto, v=v, gC=gC, c_exacto=c_exacto, c=c, X=X,
        d1=d1, I=I, d2=d2, d3=d3, d=d, los=nivel_demora(d),
        satura=(X > 1.0), tA=cola["tA"], Qe=cola["Qe"], Qev=cola["Qev"],
    )


def demora_interseccion(resultados):
    """dI = sum(di*vi)/sum(vi). resultados: lista de dicts de calcular()."""
    den = sum(r["v"] for r in resultados)
    if den <= 0:
        raise DatosInvalidos("La suma de flujos es cero; no se puede promediar.")
    num = sum(r["d"] * r["v"] for r in resultados)
    dI = num / den
    return dict(dI=dI, los=nivel_demora(dI), v_total=den)
