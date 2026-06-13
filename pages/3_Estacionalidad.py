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

MONTH_ORDER = list(MONTH_NAMES.values())


st.set_page_config(
    page_title="Estacionalidad",
    page_icon="📅",
    layout="wide",
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate_monthly(df, level_col, variable):
    group_cols = [level_col, "year", "month"]

    if variable in RATIO_VARIABLES:
        return df.groupby(group_cols, as_index=False)[variable].mean()

    return df.groupby(group_cols, as_index=False)[variable].sum()


def format_number(value, variable):
    if pd.isna(value):
        return "Sin dato"

    if variable in RATIO_VARIABLES:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"{value:,.0f}".replace(",", ".")


def month_name(month):
    return MONTH_NAMES.get(int(month), str(month))


def compute_seasonality(monthly_df, level_col, variable, year):
    year_df = monthly_df[
        (monthly_df["year"] == year)
        & monthly_df[variable].notna()
    ].copy()

    if year_df.empty:
        return pd.DataFrame()

    rows = []

    for territory, group in year_df.groupby(level_col):
        values = group[variable].dropna()

        if len(values) < 3:
            continue

        mean_value = values.mean()
        max_value = values.max()
        min_value = values.min()
        std_value = values.std(ddof=0)

        if mean_value == 0 or pd.isna(mean_value):
            continue

        max_month = int(group.loc[group[variable].idxmax(), "month"])
        min_month = int(group.loc[group[variable].idxmin(), "month"])

        summer = group[group["month"].isin([6, 7, 8, 9])][variable].sum()
        total = group[variable].sum()

        rows.append(
            {
                level_col: territory,
                "meses_disponibles": int(len(values)),
                "media_mensual": mean_value,
                "maximo_mensual": max_value,
                "minimo_mensual": min_value,
                "mes_maximo": month_name(max_month),
                "mes_minimo": month_name(min_month),
                "indice_estacional": max_value / mean_value,
                "coeficiente_variacion": std_value / mean_value,
                "concentracion_verano": summer / total if total and not pd.isna(total) else None,
            }
        )

    return pd.DataFrame(rows)


df = load_data()

st.title("Estacionalidad turística")

st.markdown(
    """
Esta página analiza los patrones mensuales de la actividad hotelera. El objetivo es observar
qué territorios tienen una actividad más concentrada en determinados meses y cuáles mantienen
un comportamiento más estable durante el año.
"""
)

st.sidebar.header("Filtros")

modo = st.sidebar.radio(
    "Tipo de variable",
    ["Oferta hotelera histórica", "Demanda turística reciente"],
)

if modo == "Oferta hotelera histórica":
    variables = VARIABLES_HISTORICAS
    default_variable = "Ocupación por plazas (%)"
else:
    variables = VARIABLES_RECIENTES
    default_variable = "Pernoctaciones"

label_variable = st.sidebar.selectbox(
    "Variable",
    list(variables.keys()),
    index=list(variables.keys()).index(default_variable),
)

variable = variables[label_variable]

available = df[df[variable].notna()].copy()

if available.empty:
    st.error("No hay datos disponibles para la variable seleccionada.")
    st.stop()

nivel = st.sidebar.radio(
    "Nivel territorial",
    ["Provincia", "Comunidad autónoma"],
)

level_col = "provincia" if nivel == "Provincia" else "ccaa"

territories = sorted(available[level_col].dropna().unique())

preferred_territories = [
    "Balears, Illes",
    "Málaga",
    "Barcelona",
    "Madrid",
    "Alicante/Alacant",
    "Canarias",
    "Andalucía",
    "Cataluña",
]

default_territory = next(
    (territory for territory in preferred_territories if territory in territories),
    territories[0],
)

territory = st.sidebar.selectbox(
    nivel,
    territories,
    index=territories.index(default_territory),
)

years = sorted(available["year"].unique())
min_year = int(min(years))
max_year = int(max(years))

if min_year == max_year:
    year_range = (min_year, max_year)
else:
    default_start = max(min_year, max_year - 10)
    year_range = st.sidebar.slider(
        "Rango de años para heatmap y perfil mensual",
        min_value=min_year,
        max_value=max_year,
        value=(default_start, max_year),
        step=1,
    )

ranking_year = st.sidebar.selectbox(
    "Año para ranking de estacionalidad",
    years,
    index=years.index(2025) if 2025 in years else len(years) - 1,
)

ranking_metric_label = st.sidebar.selectbox(
    "Métrica de estacionalidad",
    [
        "Índice estacional máximo/media",
        "Coeficiente de variación mensual",
        "Concentración junio-septiembre",
    ],
)

metric_map = {
    "Índice estacional máximo/media": "indice_estacional",
    "Coeficiente de variación mensual": "coeficiente_variacion",
    "Concentración junio-septiembre": "concentracion_verano",
}

ranking_metric = metric_map[ranking_metric_label]

monthly = aggregate_monthly(available, level_col, variable)

selected = monthly[
    (monthly[level_col] == territory)
    & (monthly["year"] >= year_range[0])
    & (monthly["year"] <= year_range[1])
    & monthly[variable].notna()
].copy()

if selected.empty:
    st.warning("No hay datos disponibles para los filtros seleccionados.")
    st.stop()

months_per_year = (
    selected.groupby("year")["month"]
    .nunique()
    .reset_index(name="meses_disponibles")
)

incomplete_years = months_per_year[months_per_year["meses_disponibles"] < 12]["year"].tolist()

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**Nivel territorial**")
    st.markdown(f"### {nivel}")

with col2:
    st.markdown("**Territorio**")
    st.markdown(f"### {territory}")

with col3:
    st.markdown("**Variable**")
    st.markdown(f"### {label_variable}")

with col4:
    st.markdown("**Rango temporal**")
    st.markdown(f"### {year_range[0]}–{year_range[1]}")

if incomplete_years:
    st.info(
        "Algunos años del rango seleccionado no tienen los 12 meses completos: "
        + ", ".join(str(year) for year in incomplete_years)
        + ". En el heatmap, esos meses aparecen como datos no disponibles."
    )

if variable in RATIO_VARIABLES:
    st.info(
        """
Para tasas y ratios se usan medias mensuales. Para variables de conteo, como viajeros,
pernoctaciones, establecimientos, plazas o personal empleado, se usan sumas territoriales.
"""
    )

st.divider()

st.header("1. Heatmap mensual")

heatmap_data = selected.copy()
heatmap_data["Mes"] = heatmap_data["month"].map(MONTH_NAMES)

pivot = heatmap_data.pivot_table(
    index="year",
    columns="Mes",
    values=variable,
    aggfunc="mean",
)

pivot = pivot.reindex(columns=MONTH_ORDER)
pivot = pivot.sort_index()

hover_values = pivot.map(lambda x: format_number(x, variable))

fig_heatmap = px.imshow(
    pivot,
    aspect="auto",
    color_continuous_scale="Viridis",
    labels={
        "x": "Mes",
        "y": "Año",
        "color": label_variable,
    },
    title=f"Patrón mensual de {label_variable} en {territory}",
)

fig_heatmap.update_traces(
    customdata=hover_values.to_numpy(),
    hovertemplate=(
        "Mes: %{x}<br>"
        "Año: %{y}<br>"
        f"{label_variable}: %{{customdata}}"
        "<extra></extra>"
    ),
)

fig_heatmap.update_layout(
    xaxis_title="Mes",
    yaxis_title="Año",
    coloraxis_colorbar={"title": label_variable},
)

st.plotly_chart(fig_heatmap, width="stretch")

st.header("2. Perfil mensual medio")

profile = (
    selected.groupby("month", as_index=False)[variable]
    .mean()
    .sort_values("month")
)

profile["Mes"] = profile["month"].map(MONTH_NAMES)
profile["Valor mostrado"] = profile[variable].apply(lambda x: format_number(x, variable))

fig_profile = px.line(
    profile,
    x="Mes",
    y=variable,
    markers=True,
    title=f"Perfil mensual medio de {label_variable} en {territory}",
    labels={
        "Mes": "Mes",
        variable: label_variable,
    },
    custom_data=["Valor mostrado"],
)

fig_profile.update_traces(
    hovertemplate=(
        "Mes: %{x}<br>"
        f"{label_variable}: %{{customdata[0]}}"
        "<extra></extra>"
    )
)

fig_profile.update_layout(
    xaxis_title="Mes",
    yaxis_title=label_variable,
    xaxis={"categoryorder": "array", "categoryarray": MONTH_ORDER},
)

st.plotly_chart(fig_profile, width="stretch")

st.header("3. Ranking de estacionalidad territorial")

seasonality = compute_seasonality(
    monthly_df=monthly,
    level_col=level_col,
    variable=variable,
    year=ranking_year,
)

if seasonality.empty or ranking_metric not in seasonality.columns:
    st.warning("No hay datos suficientes para calcular el ranking de estacionalidad.")
else:
    ranking = seasonality.dropna(subset=[ranking_metric]).copy()
    ranking = ranking.sort_values(ranking_metric, ascending=False).head(20)

    fig_ranking = px.bar(
        ranking,
        x=ranking_metric,
        y=level_col,
        orientation="h",
        title=f"Top 20 territorios por {ranking_metric_label} en {ranking_year}",
        labels={
            ranking_metric: ranking_metric_label,
            level_col: nivel,
        },
        hover_data={
            "meses_disponibles": True,
            "mes_maximo": True,
            "mes_minimo": True,
            "media_mensual": ":,.2f",
            "maximo_mensual": ":,.2f",
            "minimo_mensual": ":,.2f",
        },
    )

    fig_ranking.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_title=ranking_metric_label,
        yaxis_title=nivel,
    )

    st.plotly_chart(fig_ranking, width="stretch")

    st.subheader("Tabla de estacionalidad")

    table = ranking[
        [
            level_col,
            "meses_disponibles",
            "media_mensual",
            "maximo_mensual",
            "minimo_mensual",
            "mes_maximo",
            "mes_minimo",
            "indice_estacional",
            "coeficiente_variacion",
            "concentracion_verano",
        ]
    ].copy()

    table = table.rename(
        columns={
            level_col: nivel,
            "meses_disponibles": "Meses disponibles",
            "media_mensual": "Media mensual",
            "maximo_mensual": "Máximo mensual",
            "minimo_mensual": "Mínimo mensual",
            "mes_maximo": "Mes máximo",
            "mes_minimo": "Mes mínimo",
            "indice_estacional": "Índice máximo/media",
            "coeficiente_variacion": "Coeficiente de variación",
            "concentracion_verano": "Concentración junio-septiembre",
        }
    )

    for col in [
        "Media mensual",
        "Máximo mensual",
        "Mínimo mensual",
        "Índice máximo/media",
        "Coeficiente de variación",
        "Concentración junio-septiembre",
    ]:
        table[col] = table[col].map(lambda x: "" if pd.isna(x) else f"{x:.3f}")

    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
    )

st.info(
    """
El índice máximo/media mide cuánto se separa el mes de mayor actividad respecto al comportamiento mensual medio.
El coeficiente de variación mide la dispersión relativa de los meses. La concentración junio-septiembre indica
qué proporción del total anual se concentra en los meses de verano.
"""
)