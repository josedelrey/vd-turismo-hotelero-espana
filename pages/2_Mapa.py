from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "processed" / "turismo_hotelero_provincias.csv"
GEO_PATH = BASE_DIR / "data" / "processed" / "provincias.geojson"


VARIABLES_MAPA = {
    "Viajeros": "viajeros",
    "Pernoctaciones": "pernoctaciones",
    "Estancia media": "estancia_media",
    "Pernoctaciones por plaza": "pernoctaciones_por_plaza",
    "Viajeros por plaza": "viajeros_por_plaza",
    "Establecimientos": "establecimientos",
    "Plazas hoteleras": "plazas",
    "Ocupación por plazas (%)": "ocupacion_plazas",
    "Ocupación por habitaciones (%)": "ocupacion_habitaciones",
    "Personal empleado": "personal_empleado",
}

RATIO_VARIABLES = [
    "ocupacion_plazas",
    "ocupacion_habitaciones",
    "estancia_media",
    "pernoctaciones_por_plaza",
    "viajeros_por_plaza",
]

EXCLUDED_MISSING_GEOMETRIES = {
    "Territorio no asociado a ninguna provincia",
}

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
    page_title="Mapa",
    page_icon="🗺️",
    layout="wide",
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df["prov_code"] = df["prov_code"].astype(str).str.zfill(2)

    geo = gpd.read_file(GEO_PATH)
    geo = geo.to_crs(epsg=4326)

    return df, geo


def find_geo_code_column(geo):
    preferred_columns = [
        "prov_code",
        "provincia_code",
        "codigo_provincia",
        "cod_provincia",
        "cpro",
    ]

    normalized_columns = {col.lower(): col for col in geo.columns}

    for col in preferred_columns:
        if col in normalized_columns:
            return normalized_columns[col]

    for col in geo.columns:
        lower = col.lower()
        if "prov" in lower and ("code" in lower or "cod" in lower):
            return col

    return None


def prepare_geo(geo):
    code_col = find_geo_code_column(geo)

    if code_col is None:
        st.error("No se ha encontrado una columna de código provincial en el GeoJSON.")
        st.write("Columnas disponibles en el GeoJSON:")
        st.write(list(geo.columns))
        st.stop()

    geo = geo.copy()
    geo["prov_code"] = (
        geo[code_col]
        .astype(str)
        .str.extract(r"(\d{1,2})")[0]
        .str.zfill(2)
    )

    return geo


def aggregate_map_data(df, year, month_value, variable):
    base = df[(df["year"] == year) & df[variable].notna()].copy()

    if month_value is not None:
        base = base[base["month"] == month_value].copy()

    if variable in RATIO_VARIABLES:
        agg = (
            base.groupby(["prov_code", "provincia", "ccaa"], as_index=False)[variable]
            .mean()
        )
    else:
        agg = (
            base.groupby(["prov_code", "provincia", "ccaa"], as_index=False)[variable]
            .sum()
        )

    return agg


def format_period(month_value, year):
    if month_value is None:
        return f"Todo el año {year}"

    return f"{MONTH_NAMES.get(month_value, str(month_value))} de {year}"


def format_number(value, variable):
    if pd.isna(value):
        return ""

    if variable in RATIO_VARIABLES:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"{value:,.0f}".replace(",", ".")


def is_log_transform_allowed(variable):
    return variable not in RATIO_VARIABLES


def add_color_column(df, variable, scale_mode):
    df = df.copy()

    if scale_mode == "Logarítmica" and is_log_transform_allowed(variable):
        df["color_value"] = np.log10(df[variable].clip(lower=0) + 1)
    else:
        df["color_value"] = df[variable]

    return df


def colorbar_title(label_variable, scale_mode, variable):
    if scale_mode == "Logarítmica" and is_log_transform_allowed(variable):
        return f"{label_variable}<br>log10(valor + 1)"

    return label_variable


def build_choropleth(merged, variable, label_variable, color_scale, period_label, scale_mode):
    merged = merged.copy()
    merged["geo_id"] = merged.index.astype(str)
    merged["Valor real"] = merged[variable]
    merged["Valor mostrado"] = merged[variable].apply(lambda x: format_number(x, variable))
    merged = add_color_column(merged, variable, scale_mode)

    common_args = {
        "data_frame": merged,
        "geojson": merged.__geo_interface__,
        "locations": "geo_id",
        "featureidkey": "properties.geo_id",
        "color": "color_value",
        "hover_name": "Provincia",
        "hover_data": {
            "Comunidad autónoma": True,
            "Valor mostrado": True,
            "geo_id": False,
            "color_value": False,
            "Valor real": False,
        },
        "color_continuous_scale": color_scale.lower(),
        "center": {"lat": 40.2, "lon": -3.7},
        "zoom": 4.6,
        "opacity": 0.75,
        "title": f"{label_variable} por provincia - {period_label}",
    }

    if hasattr(px, "choropleth_map"):
        fig = px.choropleth_map(
            **common_args,
            map_style="carto-positron",
        )
    else:
        fig = px.choropleth_mapbox(
            **common_args,
            mapbox_style="carto-positron",
        )

    fig.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        coloraxis_colorbar={
            "title": colorbar_title(label_variable, scale_mode, variable),
        },
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Comunidad autónoma=%{customdata[0]}<br>"
            f"{label_variable}=%{{customdata[1]}}"
            "<extra></extra>"
        )
    )

    return fig


def get_missing_geometries(merged, variable):
    missing = merged[merged[variable].isna()].copy()

    if missing.empty:
        return []

    if "Provincia" not in missing.columns:
        return []

    names = (
        missing["Provincia"]
        .dropna()
        .astype(str)
        .sort_values()
        .tolist()
    )

    return [
        name
        for name in names
        if name not in EXCLUDED_MISSING_GEOMETRIES
    ]


df, geo = load_data()
geo = prepare_geo(geo)

st.title("Mapa coroplético por provincias")

st.markdown(
    """
El mapa permite visualizar la distribución territorial de las variables hoteleras por provincia.
Puede seleccionarse un año, un mes concreto o el total anual.
"""
)

st.sidebar.header("Filtros del mapa")

label_variable = st.sidebar.selectbox(
    "Variable",
    list(VARIABLES_MAPA.keys()),
    index=list(VARIABLES_MAPA.keys()).index("Pernoctaciones"),
)

variable = VARIABLES_MAPA[label_variable]
available = df[df[variable].notna()].copy()

if available.empty:
    st.error("No hay datos disponibles para la variable seleccionada.")
    st.stop()

years = sorted(available["year"].unique())
default_year = 2025 if 2025 in years else years[-1]

year = st.sidebar.selectbox(
    "Año",
    years,
    index=years.index(default_year),
)

months_available = sorted(available[available["year"] == year]["month"].unique())

if not months_available:
    st.error("No hay meses disponibles para el año seleccionado.")
    st.stop()

month_display_options = ["Todo el año"] + [
    MONTH_NAMES.get(month, str(month)) for month in months_available
]

month_label_to_value = {"Todo el año": None}
month_label_to_value.update(
    {MONTH_NAMES.get(month, str(month)): month for month in months_available}
)

default_month_label = (
    "Agosto"
    if 8 in months_available
    else MONTH_NAMES.get(months_available[-1], str(months_available[-1]))
)

selected_month_label = st.sidebar.selectbox(
    "Mes",
    month_display_options,
    index=month_display_options.index(default_month_label),
)

month_value = month_label_to_value[selected_month_label]

color_scale = st.sidebar.selectbox(
    "Escala de color",
    ["Viridis", "Plasma", "Cividis", "Turbo", "Blues", "Reds"],
    index=0,
)

if is_log_transform_allowed(variable):
    scale_mode = st.sidebar.selectbox(
        "Transformación de valores para el color",
        ["Logarítmica", "Lineal"],
        index=0,
    )
else:
    scale_mode = "Lineal"
    st.sidebar.caption(
        "Las variables de porcentaje o ratio se muestran en escala lineal."
    )

map_data = aggregate_map_data(df, year, month_value, variable)

if map_data.empty:
    st.warning("No hay datos disponibles para los filtros seleccionados.")
    st.stop()

merged = geo.merge(map_data, on="prov_code", how="left")

if "provincia" in merged.columns and "prov_name" in merged.columns:
    merged["Provincia"] = merged["provincia"].fillna(merged["prov_name"])
elif "provincia" in merged.columns:
    merged["Provincia"] = merged["provincia"]
elif "prov_name" in merged.columns:
    merged["Provincia"] = merged["prov_name"]
else:
    merged["Provincia"] = merged["prov_code"]

if "ccaa" in merged.columns and "acom_name" in merged.columns:
    merged["Comunidad autónoma"] = merged["ccaa"].fillna(merged["acom_name"])
elif "ccaa" in merged.columns:
    merged["Comunidad autónoma"] = merged["ccaa"]
elif "acom_name" in merged.columns:
    merged["Comunidad autónoma"] = merged["acom_name"]
else:
    merged["Comunidad autónoma"] = ""

period_label = format_period(month_value, year)
missing_names = get_missing_geometries(merged, variable)
missing_count = len(missing_names)

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**Variable**")
    st.markdown(f"### {label_variable}")

with col2:
    st.markdown("**Periodo**")
    st.markdown(f"### {period_label}")

with col3:
    st.markdown("**Provincias con dato**")
    st.markdown(f"### {int(map_data[variable].notna().sum())}")

with col4:
    st.markdown("**Geometrías sin dato**")
    st.markdown(f"### {missing_count}")

if missing_count > 0:
    st.warning(
        "Algunas geometrías aparecen sin color porque no tienen dato disponible "
        f"para la variable y periodo seleccionados: {', '.join(missing_names)}."
    )

if scale_mode == "Logarítmica" and is_log_transform_allowed(variable):
    st.info(
        """
El color del mapa utiliza una transformación logarítmica `log10(valor + 1)`.
Esto reduce el efecto de las provincias con valores extremos y permite distinguir mejor
las diferencias entre provincias con valores intermedios o bajos. Los valores mostrados
en el tooltip, ranking y tabla siguen siendo los valores reales.
"""
    )

st.divider()

fig = build_choropleth(
    merged=merged,
    variable=variable,
    label_variable=label_variable,
    color_scale=color_scale,
    period_label=period_label,
    scale_mode=scale_mode,
)

st.plotly_chart(fig, width="stretch")

st.header("Ranking provincial")

ranking = map_data.sort_values(variable, ascending=False).copy()
ranking_top = ranking.head(20).copy()

fig_rank = px.bar(
    ranking_top,
    x=variable,
    y="provincia",
    color="ccaa",
    orientation="h",
    title=f"Top 20 provincias por {label_variable} - {period_label}",
    labels={
        variable: label_variable,
        "provincia": "Provincia",
        "ccaa": "Comunidad autónoma",
    },
    custom_data=["ccaa"],
)

fig_rank.update_traces(
    hovertemplate=(
        "Provincia=%{y}<br>"
        "Comunidad autónoma=%{customdata[0]}<br>"
        f"{label_variable}=%{{x:,.2f}}"
        "<extra></extra>"
    )
)

fig_rank.update_layout(
    yaxis={"categoryorder": "total ascending"},
    xaxis_title=label_variable,
    yaxis_title="Provincia",
    legend_title_text="Comunidad autónoma",
)

st.plotly_chart(fig_rank, width="stretch")

st.header("Tabla de datos")

table = ranking[
    [
        "prov_code",
        "provincia",
        "ccaa",
        variable,
    ]
].copy()

table["Valor"] = table[variable].apply(lambda x: format_number(x, variable))

table = table.rename(
    columns={
        "prov_code": "Código provincial",
        "provincia": "Provincia",
        "ccaa": "Comunidad autónoma",
    }
)

table = table[
    [
        "Código provincial",
        "Provincia",
        "Comunidad autónoma",
        "Valor",
    ]
]

table = table.rename(columns={"Valor": label_variable})

st.dataframe(
    table,
    width="stretch",
    hide_index=True,
)

st.info(
    """
Para las variables de conteo, como viajeros, pernoctaciones, establecimientos, plazas y personal empleado,
el total anual se calcula mediante suma. Para tasas o ratios, como ocupación, estancia media o valores por plaza,
se calcula la media de los meses disponibles. Las geometrías sin color corresponden a territorios sin dato
para la variable y periodo seleccionados.
"""
)