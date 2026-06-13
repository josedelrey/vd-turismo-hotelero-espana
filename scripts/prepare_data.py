from pathlib import Path
import re
import unicodedata
import requests
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

URLS = {
    "turismo": "https://www.ine.es/jaxiT3/files/t/csv_bdsc/49371.csv",
    "oferta": "https://www.ine.es/jaxiT3/files/t/csv_bdsc/2066.csv",
    "geojson": "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/georef-spain-provincia/exports/geojson?lang=es&timezone=Europe%2FMadrid",
}


def norm_text(x):
    x = str(x).strip().lower()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(c for c in x if not unicodedata.combining(c))
    x = re.sub(r"[^a-z0-9]+", " ", x)
    x = re.sub(r"\s+", " ", x)
    return x.strip()


def download_file(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        print(f"Ya existe: {path}")
        return

    print(f"Descargando: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=120)
    r.raise_for_status()
    path.write_bytes(r.content)
    print(f"Guardado: {path}")


def read_ine_csv(path):
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="latin1")

    df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]
    return df


def find_col(df, candidates):
    normalized = {norm_text(c): c for c in df.columns}

    for wanted in candidates:
        wanted_norm = norm_text(wanted)

        for col_norm, original in normalized.items():
            if wanted_norm == col_norm:
                return original

        for col_norm, original in normalized.items():
            if wanted_norm in col_norm:
                return original

    return None


def parse_number(series):
    s = series.astype(str).str.strip()
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    s = s.replace(
        {
            "": None,
            "..": None,
            "...": None,
            "nan": None,
            "NaN": None,
            "None": None,
        }
    )
    return pd.to_numeric(s, errors="coerce")


def parse_period(x):
    s = str(x).strip()

    m = re.search(r"(\d{4})M(\d{1,2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"(\d{4})[-/](\d{1,2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    month_names = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    s_norm = norm_text(s)
    year_match = re.search(r"(\d{4})", s_norm)

    if year_match:
        year = int(year_match.group(1))
        for name, month in month_names.items():
            if name in s_norm:
                return year, month
        return year, 1

    return None, None


def metric_from_concept(x):
    s = norm_text(x)

    if "viajer" in s:
        return "viajeros"

    if "pernoct" in s:
        return "pernoctaciones"

    if "personal" in s:
        return "personal_empleado"

    if "establec" in s:
        return "establecimientos"

    if "plaza" in s and "estimad" in s:
        return "plazas"

    if "plaza" in s and "ocupacion" not in s and "grado" not in s:
        return "plazas"

    if "grado" in s and "ocupacion" in s and "plaza" in s:
        return "ocupacion_plazas"

    if "grado" in s and "ocupacion" in s and "habitacion" in s:
        return "ocupacion_habitaciones"

    return None


def clean_province_name(series):
    return (
        series.astype(str)
        .str.replace(r"^\s*\d+\s*", "", regex=True)
        .str.strip()
    )


def tidy_ine_table(path):
    df = read_ine_csv(path)

    prov_col = find_col(df, ["provincias", "provincia"])
    ccaa_col = find_col(
        df,
        [
            "comunidades y ciudades autonomas",
            "comunidades y ciudades autónomas",
            "comunidad autonoma",
            "comunidad autónoma",
            "ccaa",
        ],
    )
    period_col = find_col(df, ["periodo"])

    concept_col = find_col(
        df,
        [
            "concepto",
            "viajeros y pernoctaciones",
            "establecimientos y personal empleado plazas",
            "establecimientos y personal empleado",
            "establecimientos",
            "variables",
        ],
    )

    residence_col = find_col(
        df,
        [
            "residencia nivel 1",
            "residencia: nivel 1",
            "residencia",
            "origen",
        ],
    )

    value_col = "Total" if "Total" in df.columns else df.columns[-1]

    required = {
        "provincia": prov_col,
        "periodo": period_col,
        "concepto": concept_col,
        "valor": value_col,
    }

    missing = [k for k, v in required.items() if v is None]

    if missing:
        print("Columnas encontradas:", list(df.columns))
        raise ValueError(f"Faltan columnas necesarias: {missing}")

    if residence_col is not None:
        df = df[df[residence_col].map(norm_text).eq("total")].copy()

    df["prov_code"] = df[prov_col].astype(str).str.extract(r"^\s*(\d{2})")[0]
    df = df[df["prov_code"].notna()].copy()

    df["provincia"] = clean_province_name(df[prov_col])

    if ccaa_col is not None:
        df["ccaa"] = clean_province_name(df[ccaa_col])
    else:
        df["ccaa"] = None

    parsed = df[period_col].apply(parse_period)
    df["year"] = parsed.apply(lambda x: x[0])
    df["month"] = parsed.apply(lambda x: x[1])

    df = df[df["year"].notna() & df["month"].notna()].copy()

    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)

    df["date"] = pd.to_datetime(
        df["year"].astype(str)
        + "-"
        + df["month"].astype(str).str.zfill(2)
        + "-01"
    )

    df["metric"] = df[concept_col].apply(metric_from_concept)
    df = df[df["metric"].notna()].copy()

    df["value"] = parse_number(df[value_col])

    return df[
        [
            "prov_code",
            "provincia",
            "ccaa",
            "year",
            "month",
            "date",
            "metric",
            "value",
        ]
    ]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    turismo_path = RAW_DIR / "ine_49371_viajeros_pernoctaciones.csv"
    oferta_path = RAW_DIR / "ine_2066_oferta_hotelera.csv"
    geojson_path = PROCESSED_DIR / "provincias.geojson"

    download_file(URLS["turismo"], turismo_path)
    download_file(URLS["oferta"], oferta_path)
    download_file(URLS["geojson"], geojson_path)

    print("\nProcesando tabla de viajeros y pernoctaciones...")
    turismo = tidy_ine_table(turismo_path)
    print(turismo["metric"].value_counts())

    print("\nProcesando tabla de oferta hotelera...")
    oferta = tidy_ine_table(oferta_path)
    print(oferta["metric"].value_counts())

    long_df = pd.concat([turismo, oferta], ignore_index=True)

    df = (
        long_df.pivot_table(
            index=["prov_code", "provincia", "ccaa", "year", "month", "date"],
            columns="metric",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    df.columns.name = None

    if "viajeros" in df.columns and "pernoctaciones" in df.columns:
        df["estancia_media"] = df["pernoctaciones"] / df["viajeros"]

    if "pernoctaciones" in df.columns and "plazas" in df.columns:
        df["pernoctaciones_por_plaza"] = df["pernoctaciones"] / df["plazas"]

    if "viajeros" in df.columns and "plazas" in df.columns:
        df["viajeros_por_plaza"] = df["viajeros"] / df["plazas"]

    df = df.sort_values(["year", "month", "prov_code"])

    output_path = PROCESSED_DIR / "turismo_hotelero_provincias.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")

    print("\nCSV creado:")
    print(output_path)

    print("\nGeoJSON creado:")
    print(geojson_path)

    print("\nPrimeras filas:")
    print(df.head())

    print("\nColumnas finales:")
    print(df.columns.tolist())

    print("\nDimensiones:")
    print(df.shape)

    print("\nRango temporal:")
    print(df["date"].min(), "->", df["date"].max())


if __name__ == "__main__":
    main()