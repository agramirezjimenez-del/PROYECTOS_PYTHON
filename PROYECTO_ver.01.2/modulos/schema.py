import pandas as pd
import numpy as np
 
# ---------------------------------------------------------------------------
# Esquema canónico (gold "de verdad")
# ---------------------------------------------------------------------------
ESQUEMA_CANONICO = [
    "banco",
    "tarjeta_nombre",
    "marca",
    "categoria",
    "tea_soles_min",
    "tea_soles_max",
    "membresia_anual",
    "requisito_exoneracion_membresia",
    "programa_recompensas",
    "ratio_acumulacion",
    "seguro_desgravamen_mensual",
    "ingreso_minimo_requerido",
    "bono_bienvenida",
    "fecha_scraping",
    "url_origen",
]
 
# Mapeos: {columna_origen: columna_canonica}
MAPEO_SCOTIABANK = {
    "Banco": "banco",
    "Tarjeta_nombre": "tarjeta_nombre",
    "Marca": "marca",
    "Categoria": "categoria",
    "tea_soles_min": "tea_soles_min",
    "tea_soles_max ": "tea_soles_max",
    "membresia_anual": "membresia_anual",
    "requisitos_exoneracion": "requisito_exoneracion_membresia",
    "programa_compensas": "programa_recompensas",
    "ratio_acumulacion ": "ratio_acumulacion",
    "seguro_desgravamen": "seguro_desgravamen_mensual",
    "Ingreso minimo requerido": "ingreso_minimo_requerido",
    "fecha_scraping ": "fecha_scraping",
    "url_origen ": "url_origen",
}
 
MAPEO_INTERBANK = {
    "nombre_tarjeta": "tarjeta_nombre",
    "categoria": "categoria",
    "membresia_anual_soles": "membresia_anual",
    "millas_por_dolar_consumo": "ratio_acumulacion",
    "bono_bienvenida_millas": "bono_bienvenida",
    "url_detalle": "url_origen",
    "fecha_extraccion": "fecha_scraping",
}
 
 
def _strip_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df
 
 
def _corregir_unidad_tea_bbva(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("tea_soles_min", "tea_soles_max"):
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            es_fraccion = valores <= 1.5
            valores = np.where(es_fraccion, valores * 100, valores)
            df[col] = valores
    return df
 
 
def harmonizar_bbva(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_column_names(df)
    df = _corregir_unidad_tea_bbva(df)
    df["banco"] = "BBVA"
    return df
 
 
def harmonizar_bcp(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_column_names(df)
    df["banco"] = "BCP"
    return df
 
 
def harmonizar_banbif(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_column_names(df)
    df["banco"] = "BANBIF"
    return df
 
 
def harmonizar_scotiabank(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_column_names(df)
    df = df.rename(columns={k.strip(): v for k, v in MAPEO_SCOTIABANK.items()})
    df["banco"] = "SCOTIABANK"
    return df
 
 
def harmonizar_interbank(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_column_names(df)
    df = df.rename(columns=MAPEO_INTERBANK)
    df["banco"] = "INTERBANK"
    return df
 
 
COLUMNAS_NUMERICAS = [
    "tea_soles_min",
    "tea_soles_max",
    "membresia_anual",
    "seguro_desgravamen_mensual",
    "ingreso_minimo_requerido",
    "bono_bienvenida",
]

COLUMNAS_TEXTO = [
    "banco",
    "tarjeta_nombre",
    "marca",
    "categoria",
    "requisito_exoneracion_membresia",
    "programa_recompensas",
    "ratio_acumulacion",
    "fecha_scraping",
    "url_origen",
]
 
 
def aplicar_esquema_canonico(df: pd.DataFrame) -> pd.DataFrame:
    for col in ESQUEMA_CANONICO:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[ESQUEMA_CANONICO].copy()

    # Convertir numéricas
    for col in COLUMNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convertir textuales a string (incluye ratio_acumulacion)
    for col in COLUMNAS_TEXTO:
        df[col] = df[col].astype("string")

    return df
 
 
HARMONIZADORES = {
    "BBVA": harmonizar_bbva,
    "BCP": harmonizar_bcp,
    "BANBIF": harmonizar_banbif,
    "SCOTIABANK": harmonizar_scotiabank,
    "INTERBANK": harmonizar_interbank,
}
 
 
def harmonizar_y_unificar(dfs_por_banco: dict) -> pd.DataFrame:
    partes = []
    for banco, df in dfs_por_banco.items():
        if df is None or df.empty:
            continue
        harmonizador = HARMONIZADORES[banco]
        df_h = harmonizador(df)
        df_h = aplicar_esquema_canonico(df_h)
        partes.append(df_h)
 
    df_gold = pd.concat(partes, ignore_index=True)
    return df_gold

