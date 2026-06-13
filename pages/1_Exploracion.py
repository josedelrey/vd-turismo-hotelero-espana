from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "processed" / "turismo_hotelero_provincias.csv"


VARIABLES_HISTORICAS = {
    "Establecimientos": "establecimientos",
    "Plazas hoteleras": "plazas",
    "Ocupación por plazas (%)": "ocupacion_plazas",
    "Ocupación por habitaciones (%)": "ocupacion_habitaciones",
    "Personal empleado": "personal_empleado",
}

VARIABLES_RECIENTES = {
    "Viajeros": "viajeros",
    "Pernoctaciones": "pernoctaciones",
    "Estancia media": "estancia_media",
    "Pernoctaciones por plaza": "pernoctaciones_por_plaza",
    "Viajeros por plaza": "viajeros_por_plaza",
}

RATIO_VARIABLES = [
    "ocupacion_plazas",
    "ocupacion_habitaciones",
    "estancia_media",
    "pernoctaciones_por_plaza",
    "viajeros_por_plaza",
]

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


st.set_page_config(
    page_title="Exploración",
    page_icon="📈",
    layout="wide",
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate_for_total(df, variable):
    if variable in RATIO_VARIABLES:
        return df.groupby("date", as_index=False)[variable].mean()

    return df.groupby("date", as_index=False)[variable].sum()


def aggregate_by_ccaa(df, variable):
    if variable in RATIO_VARIABLES:
        return df.groupby(["date", "ccaa"], as_index=False)[variable].mean()

    return df.groupby(["date", "ccaa"], as_index=False)[variable].sum()


def temporal_title(label_variable, variable):
    if variable in RATIO_VARIABLES:
        return f"Evolución media provincial de {label_variable}"

    return f"Evolución nacional de {label_variable}"


def ccaa_title(label_variable, variable):
    if variable in RATIO_VARIABLES:
        return f"Evolución media provincial de {label_variable} por comunidad autónoma"

    return f"Evolución total de {label_variable} por comunidad autónoma"


def format_period(month, year):
    return f"{MONTH_NAMES.get(month, str(month))} de {year}"


df = load_data()

st.title("Exploración temporal y comparativa")

st.markdown(
    """
Esta página permite analizar la evolución de la actividad hotelera en España y comparar territorios.
La exploración se divide en dos modos: una serie histórica de **oferta hotelera** y un análisis reciente
de **demanda turística**.
"""
)

st.sidebar.header("Filtros generales")

modo = st.sidebar.radio(
    "Tipo de análisis",
    ["Oferta hotelera histórica", "Demanda turística reciente"],
)

if modo == "Oferta hotelera histórica":
    variables = VARIABLES_HISTORICAS
    default_var = "Ocupación por plazas (%)"
else:
    variables = VARIABLES_RECIENTES
    default_var = "Pernoctaciones"

label_variable = st.sidebar.selectbox(
    "Variable para las gráficas 1, 2 y 3",
    list(variables.keys()),
    index=list(variables.keys()).index(default_var),
)

variable = variables[label_variable]
available = df[df[variable].notna()].copy()

if available.empty:
    st.error("No hay datos disponibles para la variable seleccionada.")
    st.stop()

years = sorted(available["year"].unique())
default_year = 2025 if 2025 in years else years[-1]

year = st.sidebar.selectbox(
    "Año para el ranking provincial y el gráfico 4",
    years,
    index=years.index(default_year),
)

months = sorted(available[available["year"] == year]["month"].unique())

if not months:
    st.error("No hay meses disponibles para el año seleccionado.")
    st.stop()

default_month = 8 if 8 in months else months[-1]

month_labels = {m: MONTH_NAMES.get(m, str(m)) for m in months}
month_label_to_value = {v: k for k, v in month_labels.items()}

selected_month_label = st.sidebar.selectbox(
    "Mes para el ranking provincial y el gráfico 4",
    list(month_label_to_value.keys()),
    index=list(month_label_to_value.values()).index(default_month),
)

month = month_label_to_value[selected_month_label]

st.sidebar.divider()
st.sidebar.header("Filtro específico del gráfico 2")

ccaa_values = sorted(available["ccaa"].dropna().unique())

default_ccaa = [
    ccaa
    for ccaa in [
        "Andalucía",
        "Cataluña",
        "Comunitat Valenciana",
        "Madrid, Comunidad de",
        "Balears, Illes",
    ]
    if ccaa in ccaa_values
]

if not default_ccaa:
    default_ccaa = ccaa_values[:5]

selected_ccaa = st.sidebar.multiselect(
    "Comunidades autónomas mostradas en el gráfico 2",
    ccaa_values,
    default=default_ccaa,
)

st.sidebar.caption(
    "Este selector solo modifica la gráfica 2: Evolución por comunidad autónoma. "
    "No afecta a la evolución nacional, al ranking provincial ni al gráfico de dispersión."
)

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Modo**")
    st.markdown(f"### {modo}")

with col2:
    st.markdown("**Variable**")
    st.markdown(f"### {label_variable}")

with col3:
    st.markdown("**Periodo ranking**")
    st.markdown(f"### {format_period(month, year)}")

st.divider()

if variable in RATIO_VARIABLES:
    st.info(
        """
Para tasas y ratios, como ocupación, estancia media o valores por plaza, las series agregadas se calculan
como medias provinciales. Para variables de conteo, como plazas, establecimientos, viajeros o pernoctaciones,
se utilizan sumas territoriales.
"""
    )

st.header("1. Evolución temporal nacional")

national = aggregate_for_total(available, variable)

fig_national = px.line(
    national,
    x="date",
    y=variable,
    title=temporal_title(label_variable, variable),
    labels={
        "date": "Fecha",
        variable: label_variable,
    },
)

fig_national.update_layout(
    xaxis_title="Fecha",
    yaxis_title=label_variable,
    hovermode="x unified",
)

st.plotly_chart(fig_national, width="stretch")

st.header("2. Evolución por comunidad autónoma")

st.info(
    """
El selector de comunidades autónomas de la barra lateral afecta únicamente a esta gráfica.
Permite elegir qué comunidades se comparan en la evolución temporal.
"""
)

if selected_ccaa:
    ccaa_df = available[available["ccaa"].isin(selected_ccaa)].copy()
else:
    ccaa_df = available.copy()

ccaa_time = aggregate_by_ccaa(ccaa_df, variable)

fig_ccaa = px.line(
    ccaa_time,
    x="date",
    y=variable,
    color="ccaa",
    title=ccaa_title(label_variable, variable),
    labels={
        "date": "Fecha",
        variable: label_variable,
        "ccaa": "Comunidad autónoma",
    },
)

fig_ccaa.update_layout(
    xaxis_title="Fecha",
    yaxis_title=label_variable,
    hovermode="x unified",
    legend_title_text="Comunidad autónoma",
)

st.plotly_chart(fig_ccaa, width="stretch")

st.header("3. Ranking provincial")

st.markdown(
    """
Este ranking utiliza todas las provincias disponibles para el año y mes seleccionados.
No se ve afectado por el selector de comunidades autónomas del gráfico 2.
"""
)

ranking = available[
    (available["year"] == year)
    & (available["month"] == month)
    & available[variable].notna()
].copy()

ranking = ranking.sort_values(variable, ascending=False).head(15)

if ranking.empty:
    st.warning("No hay datos para construir el ranking con los filtros seleccionados.")
else:
    fig_ranking = px.bar(
        ranking,
        x=variable,
        y="provincia",
        color="ccaa",
        orientation="h",
        title=f"Top 15 provincias por {label_variable} en {format_period(month, year)}",
        labels={
            variable: label_variable,
            "provincia": "Provincia",
            "ccaa": "Comunidad autónoma",
        },
    )

    fig_ranking.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_title=label_variable,
        yaxis_title="Provincia",
        legend_title_text="Comunidad autónoma",
    )

    st.plotly_chart(fig_ranking, width="stretch")

st.header("4. Relación entre capacidad y demanda")

st.markdown(
    """
Este gráfico cruza la **capacidad hotelera** de cada provincia, medida mediante plazas disponibles,
con la **demanda turística**, medida mediante pernoctaciones. El tamaño de cada punto representa
el número de viajeros.

El gráfico utiliza todas las provincias con datos disponibles para el año y mes seleccionados.
No se ve afectado por el selector de comunidades autónomas del gráfico 2.
"""
)

scatter_df = df[
    (df["year"] == year)
    & (df["month"] == month)
    & df["plazas"].notna()
    & df["pernoctaciones"].notna()
    & df["viajeros"].notna()
].copy()

if len(scatter_df) > 0:
    fig_scatter = px.scatter(
        scatter_df,
        x="plazas",
        y="pernoctaciones",
        color="ccaa",
        size="viajeros",
        hover_name="provincia",
        title=f"Plazas hoteleras frente a pernoctaciones en {format_period(month, year)}",
        labels={
            "plazas": "Plazas hoteleras",
            "pernoctaciones": "Pernoctaciones",
            "viajeros": "Viajeros",
            "ccaa": "Comunidad autónoma",
        },
    )

    fig_scatter.update_layout(
        xaxis_title="Plazas hoteleras",
        yaxis_title="Pernoctaciones",
        legend_title_text="Comunidad autónoma",
    )

    st.plotly_chart(fig_scatter, width="stretch")
else:
    st.warning(
        "No hay datos suficientes de plazas, viajeros y pernoctaciones para construir el gráfico de dispersión en este periodo."
    )

st.divider()

st.subheader("Datos del ranking provincial")

if ranking.empty:
    st.info("No hay datos que mostrar para los filtros seleccionados.")
else:
    table = ranking[
        [
            "prov_code",
            "provincia",
            "ccaa",
            "year",
            "month",
            variable,
        ]
    ].copy()

    table["month"] = table["month"].map(MONTH_NAMES)

    table = table.rename(
        columns={
            "prov_code": "Código provincial",
            "provincia": "Provincia",
            "ccaa": "Comunidad autónoma",
            "year": "Año",
            "month": "Mes",
            variable: label_variable,
        }
    )

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
    )