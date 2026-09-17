# Nivel de servicio en intersecciones semaforizadas · HCM 2010

Aplicación en Streamlit que calcula el **nivel de servicio (LOS)** de una
intersección semaforizada por el método de la **demora de control** del
Highway Capacity Manual 2010, acceso por acceso y para la intersección completa.

Es la aplicación hermana de la calculadora de *Nivel de servicio en autopistas*:
misma estructura (`calculos.py` con la lógica pura + `app.py` con la interfaz) y
mismo estilo visual.

## Qué calcula

Para cada acceso (grupo de carril):

1. **Flujo de saturación ajustado**
   `S = So · fw · fHV · fg · fp · fbb · fa · fLU · fLT · fRT · fLpb · fRpb`
2. **Tasa de flujo de demanda** `v = n60 / PHF`
3. **Capacidad** `c = S · (g/C)`
4. **Grado de saturación** `X = v / c`
5. **Demoras** `d = d1 + d2 + d3` (uniforme + incremental + cola inicial)
6. **Nivel de servicio** del acceso según `d`

Y para la intersección: `dI = Σ(di · vi) / Σ(vi)`, con su LOS global.

Los factores **fw, fHV, fg, fp, fbb, fa** se calculan a partir de la geometría y
la demanda. Los factores que dependen de la lectura de la figura —**fLT, fRT,
fLpb, fRpb** y **fLU**— se ingresan como dato. La lógica está escrita para **un
acceso genérico**, de modo que sirve para 1 hasta 8 accesos.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Interfaz Streamlit (calculadora, memoria de cálculo y tablas). |
| `calculos.py` | Lógica pura del HCM 2010 (sin Streamlit). |
| `test_calculos.py` | Verifica los números contra el ejemplo resuelto en Mathcad. |
| `requirements.txt` | Dependencias. |
| `.streamlit/config.toml` | Tema visual. |
| `INICIAR_WINDOWS.bat` | Arranque en un clic en Windows. |

## Ejecutar en Windows (local)

Doble clic en **`INICIAR_WINDOWS.bat`**. La primera vez crea el entorno,
instala dependencias y abre la app en el navegador.

De forma manual:

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Verificar los cálculos

```bat
python test_calculos.py
```

Debe imprimir `TODOS LOS VALORES COINCIDEN`: reproduce S, v, c, X, d1, d2, d3, d
de los cuatro accesos y `dI = 366.734 s/veh` (LOS F) del ejemplo del curso.

## Publicar en GitHub + Streamlit Community Cloud

1. Crea un repositorio en GitHub (por ejemplo `calculadora-hcm-interseccion`).
2. Sube estos archivos al repo (ver comandos abajo).
3. Entra a https://share.streamlit.io → **New app** → elige el repositorio,
   la rama (`main`) y como *Main file path* pon **`app.py`**. → **Deploy**.

Comandos git (desde esta carpeta):

```bat
git init
git add .
git commit -m "Calculadora HCM 2010 - intersecciones semaforizadas"
git branch -M main
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

## Alcance

Herramienta académica. Aplica el método de demora de control del HCM 2010 para
accesos semaforizados. El verde efectivo se toma igual al verde físico; el factor
de intersecciones aguas arriba usa `I = 1.0` para intersección aislada (si se
desactiva, `I = 1 − 0.91·X^2.68 ≥ 0.09`); en `d2`, `k = 0.5` en giros permitidos
y `k = 1.0` en giros protegidos.
