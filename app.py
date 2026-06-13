from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "turismo_hotelero_provincias.csv"


st.set_page_config(
    page_title="Presión turística hotelera en España",
    page_icon="📊",
    layout="wide",
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


df = load_data()

st.title("Presión turística hotelera en España")
st.subheader("Análisis territorial por provincias a partir de datos mensuales del INE")

st.markdown(
    """
Esta aplicación permite explorar la distribución territorial, temporal y estacional de la actividad hotelera en España.
El análisis combina variables de **oferta hotelera**, como establecimientos, plazas, ocupación y personal empleado,
con variables de **demanda turística reciente**, como viajeros, pernoctaciones y estancia media.

La web está organizada en tres páginas principales:

- **Exploración**: análisis temporal, rankings provinciales y comparación entre comunidades autónomas.
- **Mapa**: mapa coroplético interactivo por provincia, con selección de año, mes, variable y escala de color.
- **Estacionalidad**: análisis mensual mediante heatmap, perfil medio anual y ranking de concentración estacional.
"""
)

st.divider()

min_year = int(df["year"].min())
max_year = int(df["year"].max())
n_provinces = df["provincia"].nunique()
n_ccaa = df["ccaa"].nunique()
n_rows = len(df)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Rango temporal", f"{min_year}–{max_year}")
col2.metric("Provincias", n_provinces)
col3.metric("Comunidades autónomas", n_ccaa)
col4.metric("Registros", f"{n_rows:,}".replace(",", "."))

st.divider()

st.header("Descripción del conjunto de datos")

st.markdown(
    """
El conjunto de datos utilizado contiene observaciones mensuales por provincia.
Cada registro representa una combinación de **provincia, año y mes**, junto con distintas variables hoteleras.

Las variables disponibles pueden dividirse en dos grupos:

- **Oferta hotelera histórica**: establecimientos, plazas hoteleras, ocupación y personal empleado.
- **Demanda turística reciente**: viajeros, pernoctaciones, estancia media y ratios de presión turística.
"""
)

st.info(
    """
Las variables de oferta hotelera tienen cobertura histórica amplia desde 1999.
Las variables de demanda turística, como viajeros y pernoctaciones, están completas para 2025
y disponibles parcialmente para 2026. Por este motivo, el análisis de presión turística reciente se centra
principalmente en 2025, evitando comparar años incompletos con años completos.
"""
)

st.divider()

st.header("Cobertura de variables")

display_names = {
    "prov_code": "Código provincial",
    "provincia": "Provincia",
    "ccaa": "Comunidad autónoma",
    "year": "Año",
    "month": "Mes",
    "date": "Fecha",
    "ocupacion_habitaciones": "Ocupación por habitaciones (%)",
    "ocupacion_plazas": "Ocupación por plazas (%)",
    "personal_empleado": "Personal empleado",
    "establecimientos": "Establecimientos",
    "plazas": "Plazas hoteleras",
    "pernoctaciones": "Pernoctaciones",
    "viajeros": "Viajeros",
    "estancia_media": "Estancia media",
    "pernoctaciones_por_plaza": "Pernoctaciones por plaza",
    "viajeros_por_plaza": "Viajeros por plaza",
}

coverage = (
    df.notna()
    .sum()
    .reset_index()
    .rename(columns={"index": "variable", 0: "valores_disponibles"})
)

coverage["Variable"] = coverage["variable"].map(display_names).fillna(coverage["variable"])
coverage["Valores disponibles"] = coverage["valores_disponibles"]
coverage["Cobertura (%)"] = (100 * coverage["valores_disponibles"] / len(df)).round(2)

coverage = coverage[
    [
        "Variable",
        "Valores disponibles",
        "Cobertura (%)",
    ]
].sort_values("Cobertura (%)", ascending=False)

st.dataframe(
    coverage,
    width="stretch",
    hide_index=True,
)

st.divider()

st.header("Lectura inicial")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
### Cobertura histórica

Las variables con mayor cobertura son las relacionadas con la estructura de la oferta hotelera.
Estas permiten estudiar la evolución territorial del sector durante más de dos décadas.
"""
    )

with col2:
    st.markdown(
        """
### Presión turística reciente

Las variables de viajeros y pernoctaciones permiten analizar la intensidad turística reciente.
En la aplicación se usan especialmente para comparar provincias durante 2025.
"""
    )

with col3:
    st.markdown(
        """
### Estacionalidad

La frecuencia mensual de los datos permite estudiar patrones de temporada alta y baja,
así como comparar territorios con actividad concentrada o más estable durante el año.
"""
    )

st.divider()

st.caption(
    "Fuente de datos: Instituto Nacional de Estadística, Encuesta de Ocupación Hotelera. "
    "Geometrías provinciales obtenidas a partir de un GeoJSON de provincias españolas."
)