from dataclasses import asdict
import html
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from calculos import (Config, Acceso, DatosInvalidos, calcular,
                      demora_interseccion, nivel_demora, LOS_LIMITES)

st.set_page_config(page_title="Vía · Nivel de servicio en intersecciones",
                   page_icon="🚦", layout="wide")
st.markdown('''<style>
.block-container{max-width:1440px;padding-top:4.5rem;padding-bottom:2rem}
h1{font-size:2.2rem!important;letter-spacing:-.065rem} h3{font-size:1.2rem!important}
[data-testid="stVerticalBlockBorderWrapper"]>div{background:white;border-radius:14px}
div[data-testid="stMetric"]{background:#edf3fb;padding:14px;border-radius:10px}
div[data-testid="stMetricValue"]{font-size:1.7rem}
button[data-baseweb="tab"]{font-size:1rem;padding:12px 20px}
.eyebrow{font-size:13px;letter-spacing:.14em;font-weight:700;color:#1763e8;margin-bottom:8px}
.result{display:flex;align-items:center;gap:18px;padding:20px;border:1px solid #dce4ef;border-radius:12px;background:#fff;margin:8px 0 14px}
.grade{font-size:3rem;font-weight:750;border-radius:12px;width:78px;min-width:78px;text-align:center;padding:2px 0}
.result-title{font-size:1.12rem;font-weight:700}.result-note{color:#52657a;font-size:14px;margin-top:4px}
.step{font-size:14px;font-weight:700;color:#1763e8;text-transform:uppercase;letter-spacing:.04em;margin-top:8px}
.foot{font-size:13px;color:#52657a;border-top:1px solid #dce4ef;padding-top:16px;margin-top:24px}
.big{display:flex;align-items:center;gap:22px;padding:22px 26px;border-radius:14px;background:linear-gradient(90deg,#f4f8 fe,#eef3fb);border:1px solid #dce4ef;margin:6px 0 4px}
.big .grade{font-size:3.6rem;width:96px;min-width:96px}
.big-num{font-size:2.2rem;font-weight:750;line-height:1}
@media(max-width:640px){.block-container{padding:4.5rem 1rem 1rem}h1{font-size:1.7rem!important}.result{padding:12px}}
</style>''', unsafe_allow_html=True)

COLORS = {"A":"#176443","B":"#287846","C":"#1d5dab","D":"#956000","E":"#a34a10","F":"#b42335"}
NOTES = {
    "A":"Operación libre; demora de control muy baja.",
    "B":"Buena operación; demoras bajas y colas cortas.",
    "C":"Demoras moderadas; empiezan a aparecer ciclos con cola.",
    "D":"Demoras notables; congestión perceptible en cada ciclo.",
    "E":"Demoras altas; operación próxima a la capacidad.",
    "F":"Demoras muy altas; la demanda supera la capacidad del acceso.",
}
DEF_NAMES = ["Norte","Sur","Este","Oeste","Acceso 5","Acceso 6","Acceso 7","Acceso 8"]

# Ejemplo resuelto (practica calificada). fLT = 1/EL con EL interpolado de la figura.
EJEMPLO = [
    dict(nombre="Norte", ancho=3.6, pesados=15.0, pendiente=-1.0, cbd=True, carriles=1,
         estacionamiento=False, maniobras=0.0, paradero=True, buses=27.0,
         n60=251.0, phf=0.97, verde=50.0, protegido=False, cola=4.0,
         flt=1/2.00, frt=0.85, flpb=0.928, frpb=0.893, flu=1.0),
    dict(nombre="Sur", ancho=3.6, pesados=15.0, pendiente=1.0, cbd=True, carriles=1,
         estacionamiento=False, maniobras=0.0, paradero=True, buses=32.0,
         n60=432.0, phf=0.97, verde=50.0, protegido=False, cola=0.0,
         flt=1/1.74, frt=0.85, flpb=1.0, frpb=1.0, flu=1.0),
    dict(nombre="Este", ancho=3.6, pesados=12.0, pendiente=0.5, cbd=True, carriles=1,
         estacionamiento=True, maniobras=10.0, paradero=False, buses=0.0,
         n60=416.0, phf=0.95, verde=40.0, protegido=False, cola=3.0,
         flt=1/1.90, frt=0.85, flpb=1.0, frpb=1.0, flu=1.0),
    dict(nombre="Oeste", ancho=3.6, pesados=12.0, pendiente=-0.5, cbd=True, carriles=1,
         estacionamiento=True, maniobras=33.0, paradero=False, buses=0.0,
         n60=360.0, phf=0.95, verde=40.0, protegido=False, cola=0.0,
         flt=1/2.06, frt=0.85, flpb=1.0, frpb=1.0, flu=1.0),
]


def cargar_ejemplo():
    st.session_state.update(dict(g_metros=True, g_ciclo=100.0, g_periodo=0.25,
                                 g_so=1900.0, g_et=2.0, g_aislada=True,
                                 g_redondear=True, n_acc=4))
    for idx, a in enumerate(EJEMPLO):
        for k, v in a.items():
            st.session_state[f"{idx}_{k}"] = v


def cambiar_unidad():
    factor = 0.3048 if st.session_state["g_metros"] else 1/0.3048
    for idx in range(st.session_state.get("n_acc", 4)):
        key = f"{idx}_ancho"
        if key in st.session_state:
            st.session_state[key] *= factor


def num(label, idx, name, default, **kw):
    key = f"{idx}_{name}"
    if key not in st.session_state:
        st.session_state[key] = default
    return st.number_input(label, key=key, **kw)


def entrada_acceso(idx, metric):
    unit = "m" if metric else "ft"
    dname = DEF_NAMES[idx] if idx < len(DEF_NAMES) else f"Acceso {idx+1}"
    if f"{idx}_nombre" not in st.session_state:
        st.session_state[f"{idx}_nombre"] = dname
    nombre = st.text_input("Nombre del acceso", key=f"{idx}_nombre")

    st.markdown('<div class="step">01 · Geometría y área</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        ancho = num(f"Ancho de carril ({unit})", idx, "ancho", 3.6 if metric else 11.81,
                    min_value=0.0, max_value=30.0, step=0.1 if metric else 0.5, format="%.2f")
        carriles = num("Carriles del grupo · N", idx, "carriles", 1,
                       min_value=1, max_value=8, step=1)
    with b:
        pend = num("Pendiente Pg (%)", idx, "pendiente", 0.0, min_value=-6.0,
                   max_value=10.0, step=0.5, format="%.2f",
                   help="Signo + en cuesta arriba, − en cuesta abajo. Rango −6 a +10 %.")
        cbd = st.toggle("Zona central (CBD) → fa = 0.9", key=f"{idx}_cbd")

    st.markdown('<div class="step">02 · Demanda y semáforo</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        n60 = num("Aforo n₆₀ (veh mixtos/h)", idx, "n60", 0.0, min_value=0.0,
                  max_value=100000.0, step=10.0, format="%.0f",
                  help="Suma de todos los movimientos del acceso en una hora.")
        phf = num("Factor de hora punta · PHF", idx, "phf", 0.95, min_value=0.25,
                  max_value=1.0, step=0.01, format="%.2f")
        pesados = num("Vehículos pesados (%)", idx, "pesados", 0.0, min_value=0.0,
                      max_value=100.0, step=1.0, format="%.1f",
                      help="Camiones + buses. ET = 2.0 (configurable arriba).")
    with b:
        verde = num("Verde efectivo g (s)", idx, "verde", 0.0, min_value=0.0,
                    max_value=300.0, step=1.0, format="%.0f",
                    help="Se asume verde efectivo = verde físico.")
        prot = st.toggle("Giro protegido (k = 1.0)", key=f"{idx}_protegido",
                         help="Desactivado = giro permitido, k = 0.5.")
        cola = num("Cola inicial Qb (veh)", idx, "cola", 0.0, min_value=0.0,
                   max_value=1000.0, step=1.0, format="%.0f")

    st.markdown('<div class="step">03 · Factores de giro y peatones · dato</div>',
                unsafe_allow_html=True)
    st.caption("Se ingresan directamente (dependen de la figura). fLT = 1/EL y fRT = 1/ER; "
               "usa la pestaña «Tablas de referencia» para elegir EL y ER.")
    a, b, c, d = st.columns(4)
    with a:
        flt = num("fLT (giro izq.)", idx, "flt", 1.0, min_value=0.01, max_value=1.0,
                  step=0.01, format="%.3f")
    with b:
        frt = num("fRT (giro der.)", idx, "frt", 1.0, min_value=0.01, max_value=1.0,
                  step=0.01, format="%.3f")
    with c:
        flpb = num("fLpb (peat. izq.)", idx, "flpb", 1.0, min_value=0.01, max_value=1.0,
                   step=0.001, format="%.3f")
    with d:
        frpb = num("fRpb (peat. der.)", idx, "frpb", 1.0, min_value=0.01, max_value=1.0,
                   step=0.001, format="%.3f")

    with st.expander("04 · Estacionamiento, buses y utilización de carril"):
        a, b = st.columns(2)
        with a:
            est = st.toggle("Estacionamiento adyacente", key=f"{idx}_estacionamiento")
            man = num("Maniobras Nm (veh/h)", idx, "maniobras", 0.0, min_value=0.0,
                      max_value=1000.0, step=1.0, format="%.0f",
                      help="Máximo 180 veh/h. Solo aplica si hay estacionamiento.")
        with b:
            par = st.toggle("Paradero de buses", key=f"{idx}_paradero")
            bus = num("Buses que bloquean Nb (buses/h)", idx, "buses", 0.0, min_value=0.0,
                      max_value=1000.0, step=1.0, format="%.0f",
                      help="Máximo 250 buses/h. Solo aplica si hay paradero.")
        flu = num("fLU · utilización de carril", idx, "flu", 1.0, min_value=0.01,
                  max_value=1.0, step=0.01, format="%.2f",
                  help="1.00 para análisis de un solo carril.")

    return Acceso(nombre=nombre, ancho=ancho, en_metros=metric, pesados=pesados,
                  pendiente=pend, estacionamiento=est, maniobras=man, carriles=int(carriles),
                  paradero=par, buses=bus, cbd=cbd, flu=flu, flt=flt, frt=frt,
                  flpb=flpb, frpb=frpb, n60=n60, phf=phf, verde=verde,
                  k=1.0 if prot else 0.5, cola_inicial=cola)


def tarjeta(r):
    g = r["los"]; color = COLORS[g]
    st.markdown(f'''<div class="result"><div class="grade" style="color:{color};background:{color}12">{g}</div>
<div><div class="result-title">{html.escape(r["nombre"])} · Nivel de servicio {g}</div>
<div class="result-note">{NOTES[g]}</div></div></div>''', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    a.metric("Demora de control · s/veh", f"{r['d']:.1f}")
    b.metric("Grado de saturación · X", f"{r['X']:.3f}")
    c.metric("Capacidad c · veh/h", f"{r['c']:.0f}")
    if r["satura"]:
        st.error(f"Acceso saturado: X = {r['X']:.3f} > 1. La demanda v = {r['v']:.0f} "
                 f"supera la capacidad c = {r['c']:.0f} veh/h.")
    st.caption(f"S = {r['S']:.2f} veh/h/ln · v = {r['v']:.0f} veh/h · g/C = {r['gC']:.2f} · "
               f"fHV = {r['fhv']:.3f} · d1 = {r['d1']:.1f} · d2 = {r['d2']:.1f} · d3 = {r['d3']:.1f}")


def tarjeta_interseccion(inter):
    g = inter["los"]; color = COLORS[g]
    st.markdown(f'''<div class="big"><div class="grade" style="color:{color};background:{color}18">{g}</div>
<div><div class="result-title">Intersección · Nivel de servicio {g}</div>
<div class="big-num" style="color:{color}">{inter['dI']:.1f} <span style="font-size:1rem;color:#52657a">s/veh</span></div>
<div class="result-note">Demora de control ponderada por flujo · d<sub>I</sub> = Σ(dᵢ·vᵢ)/Σvᵢ</div></div></div>''',
                unsafe_allow_html=True)


def grafico(names, results, inter):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=[r["d1"] for r in results], name="d₁ uniforme",
                         marker_color="#9cc0f2"))
    fig.add_trace(go.Bar(x=names, y=[r["d2"] for r in results], name="d₂ incremental",
                         marker_color="#1763e8"))
    fig.add_trace(go.Bar(x=names, y=[r["d3"] for r in results], name="d₃ cola inicial",
                         marker_color="#0b2f66"))
    for n, r in zip(names, results):
        fig.add_annotation(x=n, y=r["d"], text=f"<b>{r['los']}</b>", showarrow=False,
                           yshift=12, font=dict(color=COLORS[r["los"]], size=14))
    if inter:
        fig.add_hline(y=inter["dI"], line_dash="dot", line_color="#b42335",
                      annotation_text=f"dₐ intersección = {inter['dI']:.0f} s/veh",
                      annotation_position="top left")
    fig.update_layout(barmode="stack", height=300, margin=dict(l=5, r=15, t=25, b=5),
                      paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(family="Arial", size=13, color="#52657a"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                      xaxis_title="", yaxis_title="Demora de control (s/veh)",
                      yaxis=dict(gridcolor="#eef2f6"), xaxis=dict(gridcolor="#eef2f6"))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def procedimiento(cfg, e, r):
    st.subheader(f"{r['nombre']}")
    with st.container(border=True):
        st.markdown("**1. Flujo de saturación ajustado**")
        st.write(f"Ancho {e.ancho:.2f} {'m' if e.en_metros else 'ft'} "
                 f"({r['ancho_ft']:.2f} ft) → fw = {r['fw']:.2f}. "
                 f"fHV = 100/(100 + {e.pesados:g}·({cfg.et:g}−1)) = {r['fhv']:.3f}. "
                 f"fg = 1 − ({e.pendiente:g}/200) = {r['fg']:.3f}. "
                 f"fp = {r['fp']:.3f}, fbb = {r['fbb']:.3f}, fa = {r['fa']:.2f}.")
        st.latex(r"S=S_0\,f_w\,f_{HV}\,f_g\,f_p\,f_{bb}\,f_a\,f_{LU}\,f_{LT}\,f_{RT}\,f_{Lpb}\,f_{Rpb}")
        st.latex(
            fr"S={cfg.so:g}\times{r['fw']:.3f}\times{r['fhv']:.3f}\times{r['fg']:.3f}"
            fr"\times{r['fp']:.3f}\times{r['fbb']:.3f}\times{r['fa']:.2f}\times{r['flu']:.2f}"
            fr"\times{r['flt']:.3f}\times{r['frt']:.3f}\times{r['flpb']:.3f}\times{r['frpb']:.3f}"
            fr"={r['S']:.3f}\;\mathrm{{veh/h/ln}}")
    with st.container(border=True):
        st.markdown("**2. Tasa de flujo, capacidad y grado de saturación**")
        st.latex(fr"v=\frac{{n_{{60}}}}{{PHF}}=\frac{{{e.n60:g}}}{{{e.phf:g}}}"
                 fr"={r['v_exacto']:.3f}\;\rightarrow\;{r['v']:.0f}\;\mathrm{{veh/h}}")
        st.latex(fr"c=S\left(\frac{{g}}{{C}}\right)={r['S']:.3f}\times\frac{{{e.verde:g}}}{{{cfg.ciclo:g}}}"
                 fr"={r['c_exacto']:.3f}\;\rightarrow\;{r['c']:.0f}\;\mathrm{{veh/h}}")
        st.latex(fr"X=\frac{{v}}{{c}}=\frac{{{r['v']:.0f}}}{{{r['c']:.0f}}}={r['X']:.3f}")
    with st.container(border=True):
        st.markdown("**3. Demoras y nivel de servicio**")
        st.latex(fr"d_1=\frac{{0.5\,C\,(1-g/C)^2}}{{1-\min(1,X)\,g/C}}={r['d1']:.3f}\;\mathrm{{s/veh}}")
        st.latex(fr"d_2=900\,T\left[(X-1)+\sqrt{{(X-1)^2+\frac{{8kIX}}{{cT}}}}\,\right]"
                 fr"={r['d2']:.3f}\;\mathrm{{s/veh}}")
        st.caption(f"k = {e.k:g} ({'giro protegido' if e.k==1.0 else 'giro permitido'}), "
                   f"I = {r['I']:.2f} ({'intersección aislada' if cfg.aislada else 'no aislada'}), "
                   f"T = {cfg.periodo:g} h.")
        if r["d3"] > 0:
            st.latex(fr"d_3={r['d3']:.3f}\;\mathrm{{s/veh}}\quad(Q_b={e.cola_inicial:g}\;\mathrm{{veh}})")
        else:
            st.caption(f"d₃ = 0 (sin cola inicial, Qb = {e.cola_inicial:g}).")
        st.latex(fr"d=d_1+d_2+d_3={r['d1']:.2f}+{r['d2']:.2f}+{r['d3']:.2f}={r['d']:.3f}\;\mathrm{{s/veh}}")
        st.success(f"Demora de control d = {r['d']:.2f} s/veh → nivel de servicio {r['los']}.")


# ------------------------------------------------------------------ Encabezado
# La app abre mostrando el ejemplo del curso (siembra unica de session_state).
if "seeded" not in st.session_state:
    cargar_ejemplo()
    st.session_state["seeded"] = True

st.markdown('<div class="eyebrow">VÍA / ANÁLISIS DE TRÁNSITO</div>', unsafe_allow_html=True)
st.title("Nivel de servicio en intersecciones semaforizadas")
st.caption("Metodología HCM 2010 · demora de control por acceso y de la intersección")

top = st.columns([2, 1], vertical_alignment="bottom")
with top[0]:
    st.selectbox("Metodología", ["HCM 2010"], key="metodo",
                 help="Demora de control (d = d1 + d2 + d3) y LOS por demora.")
with top[1]:
    st.button("Cargar ejemplo del curso", on_click=cargar_ejemplo, width="stretch",
              help="Restaura los cuatro accesos de la práctica calificada.")

tab_calc, tab_proc, tab_tab = st.tabs(["Calculadora", "Procedimiento", "Tablas de referencia"])

# --------------------------------------------------------- Configuración común
entries, results, errors, names = [], [], [], []
with tab_calc:
    with st.container(border=True):
        st.subheader("Parámetros de la intersección")
        c = st.columns(4)
        with c[0]:
            metric = st.toggle("Ancho en metros", key="g_metros", on_change=cambiar_unidad)
            aislada = st.toggle("Intersección aislada (I = 1.0)", key="g_aislada")
        with c[1]:
            ciclo = st.number_input("Ciclo C (s)", min_value=1.0, max_value=300.0,
                                    step=1.0, format="%.0f", key="g_ciclo")
            periodo = st.number_input("Periodo T (h)", min_value=0.05, max_value=1.0,
                                      step=0.05, format="%.2f", key="g_periodo")
        with c[2]:
            so = st.number_input("So base (pc/h/ln)", min_value=1.0, max_value=3000.0,
                                 step=50.0, format="%.0f", key="g_so")
            et = st.number_input("ET · equiv. pesados", min_value=1.0, max_value=5.0,
                                 step=0.1, format="%.1f", key="g_et")
        with c[3]:
            n_acc = st.number_input("Número de accesos", min_value=1, max_value=8,
                                    step=1, key="n_acc")
            redondear = st.toggle("Redondear v y c a enteros", key="g_redondear",
                                  help="Como en el desarrollo original de Mathcad.")
    cfg = Config(ciclo=ciclo, periodo=periodo, aislada=aislada, redondear=redondear,
                 so=so, et=et)

    n_acc = int(n_acc)
    names = [st.session_state.get(f"{i}_nombre", DEF_NAMES[i] if i < len(DEF_NAMES)
             else f"Acceso {i+1}") for i in range(n_acc)]

    left, right = st.columns([1.05, 1], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("Datos por acceso")
            for idx, t in enumerate(st.tabs(names)):
                with t:
                    entries.append(entrada_acceso(idx, metric))
            st.caption("Los resultados se actualizan al confirmar cada campo con Enter o al salir de él.")

    for e in entries:
        try:
            results.append(calcular(e, cfg)); errors.append(None)
        except DatosInvalidos as ex:
            results.append(None); errors.append(str(ex))

    validos = [r for r in results if r]
    inter = demora_interseccion(validos) if validos else None
    names = [r["nombre"] if r else n for n, r in zip(names, results)]

    with right:
        st.subheader("Resultados")
        if inter:
            tarjeta_interseccion(inter)
        for r, err in zip(results, errors):
            if err:
                st.error(err); st.caption("Corrige los datos indicados para este acceso.")
            else:
                tarjeta(r)
        if len(validos) >= 1:
            with st.container(border=True):
                st.markdown("**Demora por acceso · componentes d₁ / d₂ / d₃**")
                grafico([r["nombre"] for r in validos], validos, inter)
                st.caption("La letra sobre cada barra es el LOS del acceso; la línea roja marca "
                           "la demora de control de la intersección.")
            filas = [{"Acceso": r["nombre"], "LOS": r["los"], "S (veh/h/ln)": round(r["S"], 2),
                      "v (veh/h)": round(r["v"]), "c (veh/h)": round(r["c"]),
                      "X": round(r["X"], 3), "d1": round(r["d1"], 2), "d2": round(r["d2"], 2),
                      "d3": round(r["d3"], 2), "d (s/veh)": round(r["d"], 2)} for r in validos]
            df = pd.DataFrame(filas)
            st.dataframe(df, hide_index=True, width="stretch")
            st.download_button("Descargar resultados CSV",
                               df.to_csv(index=False).encode("utf-8-sig"),
                               "resultados_interseccion.csv", "text/csv", width="stretch")

# ------------------------------------------------------------- Procedimiento
with tab_proc:
    st.subheader("Memoria de cálculo")
    st.caption("El desarrollo coincide con los valores actuales de la calculadora. "
               "Los cálculos conservan todos los decimales; solo v y c se redondean.")
    for e, r, err in zip(entries, results, errors):
        if err:
            st.error(f"{e.nombre}: {err}")
        else:
            procedimiento(cfg, e, r)
    if inter:
        with st.container(border=True):
            st.markdown("**Demora de la intersección**")
            terminos = " + ".join(f"{r['d']:.2f}\\cdot{r['v']:.0f}" for r in validos)
            denom = " + ".join(f"{r['v']:.0f}" for r in validos)
            st.latex(r"d_I=\frac{\sum d_i\,v_i}{\sum v_i}")
            st.latex(fr"d_I=\frac{{{terminos}}}{{{denom}}}={inter['dI']:.3f}\;\mathrm{{s/veh}}")
            st.success(f"Demora de la intersección d_I = {inter['dI']:.2f} s/veh → "
                       f"nivel de servicio global {inter['los']}.")
    payload = {"config": asdict(cfg),
               "accesos": [dict(nombre=e.nombre, entrada=asdict(e), resultado=r, error=err)
                           for e, r, err in zip(entries, results, errors)],
               "interseccion": inter}
    st.download_button("Descargar datos y cálculo JSON",
                       json.dumps(payload, ensure_ascii=False, indent=2),
                       "calculo_interseccion.json", "application/json")

# --------------------------------------------------------- Tablas de referencia
with tab_tab:
    st.subheader("Factores y criterios HCM 2010")
    a, b = st.columns(2)
    with a:
        st.markdown("**Ancho de carril · fw**")
        st.table(pd.DataFrame({"Ancho medio (ft)": ["< 10.0", "10.0 – 12.9", "> 12.9"],
                               "fw": [0.96, 1.00, 1.04]}))
        st.caption("Se ingresa en metros o pies; se convierte a pies para elegir el intervalo.")
        st.markdown("**Vehículos pesados · fHV**")
        st.latex(r"f_{HV}=\frac{100}{100+P_{HV}(E_T-1)}\quad(E_T=2.0)")
        st.caption("PHV incluye camiones y buses.")
        st.markdown("**Pendiente · fg**")
        st.latex(r"f_g=1-\frac{P_g}{200}\quad(-6\le P_g\le +10)")
        st.markdown("**Tipo de área · fa**")
        st.table(pd.DataFrame({"Zona": ["CBD (centro)", "Otras áreas"], "fa": [0.90, 1.00]}))
    with b:
        st.markdown("**Estacionamiento · fp** y **buses · fbb**")
        st.latex(r"f_p=\frac{N-0.1-\frac{18N_m}{3600}}{N}\ge0.05\quad(N_m\le180)")
        st.latex(r"f_{bb}=\frac{N-\frac{14.4N_b}{3600}}{N}\ge0.05\quad(N_b\le250)")
        st.markdown("**Giro a la izquierda · fLT = 1/EL**")
        st.table(pd.DataFrame({
            "Condición": ["Protegido · 1 carril", "Protegido · 2+ carriles",
                          "Un sentido / T · 1 carril", "Un sentido / T · 2+ carriles"],
            "EL": [1.05, 1.09, 1.18, 1.33], "fLT": [0.95, 0.92, 0.85, 0.75]}))
        st.caption("Con flujo opuesto (permitido), EL se interpola por el flujo opuesto "
                   "(1→1.4 … 1200→4.5 en carriles compartidos).")
        st.markdown("**Giro a la derecha · fRT = 1/ER**")
        st.table(pd.DataFrame({"Condición": ["1 carril", "2+ carriles"],
                               "ER": [1.18, 1.33], "fRT": [0.85, 0.75]}))
    st.markdown("**Niveles de servicio · demora de control (HCM 2010)**")
    lim = [f"≤ {int(LOS_LIMITES[0][0])}"] + \
          [f"> {int(LOS_LIMITES[i-1][0])} a {int(LOS_LIMITES[i][0])}" for i in range(1, len(LOS_LIMITES))] + \
          ["> 80 (o X > 1)"]
    st.table(pd.DataFrame({"Nivel": list("ABCDEF"), "Demora de control (s/veh)": lim}))
    with st.expander("Alcance y notas"):
        st.write("Aplica a accesos de intersecciones semaforizadas por el método de demora de "
                 "control del HCM 2010. Los factores de giro (fLT, fRT) y de peatones/bicicletas "
                 "(fLpb, fRpb) se ingresan como dato porque dependen de la geometría y del flujo "
                 "opuesto leídos de la figura. El factor de utilización de carril fLU = 1.00 "
                 "corresponde al análisis de un solo carril. Verde efectivo = verde físico.")
        st.write("El factor de intersecciones aguas arriba usa I = 1.0 para intersección aislada; "
                 "si se desactiva, I = 1 − 0.91·X^2.68 ≥ 0.09. En d₂, k = 0.5 en giros permitidos "
                 "y k = 1.0 en giros protegidos.")

st.markdown('<div class="foot">S = flujo de saturación · v = tasa de flujo · c = capacidad · '
            'X = grado de saturación · d = demora de control · d<sub>I</sub> = demora de la intersección<br>'
            'Herramienta académica; los resultados dependen de que el acceso cumpla las condiciones del método.</div>',
            unsafe_allow_html=True)
