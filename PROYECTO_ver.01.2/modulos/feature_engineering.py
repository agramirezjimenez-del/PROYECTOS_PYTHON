import re
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

pd.set_option("mode.copy_on_write", True)

# ---------------------------------------------------------------------------
# 0. Limpieza mínima de categóricas (homogeneizar mayúsculas/minúsculas)
# ---------------------------------------------------------------------------

MAPA_MARCA = {
    "mastercard": "Mastercard",
    "visa": "Visa",
    "visa/mastercard": "Visa/Mastercard",
    "american express": "American Express",
}


def limpiar_categoricas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza casing de marca/banco/categoria (vectorizado con .str)."""
    df = df.copy()
    df["marca"] = df["marca"].str.strip().str.lower().map(MAPA_MARCA).fillna(df["marca"])
    df["banco"] = df["banco"].str.strip().str.upper()
    df["categoria"] = df["categoria"].str.strip()
    return df


# ---------------------------------------------------------------------------
# 1. ENRIQUECIMIENTO INTERNO
# ---------------------------------------------------------------------------

# --- 1.a Regla de negocio: jerarquía de nivel de tarjeta ---------------------
# Fundamento: en el mercado peruano las categorías de tarjetas siguen una
# jerarquía de beneficios/exclusividad reconocida por la industria. Se
# mapea cada categoría observada en el scraping a un nivel ordinal 1-4.
NIVEL_CATEGORIA = {
    "Visa Cero": 1, "Bfree": 1, "Clásica": 1,
    "Oro": 2, "Platinum": 2, "Amex - Millas Benefit": 2, "Visa - Millas Benefit": 2,
    "Signature": 3, "Black": 3, "Premium": 3,
    "Visa Infinite": 4,
}

# --- 1.b Regla de negocio: bins de TEA máxima ---------------------------------
# Fundamento: cuartiles observados en la data real (Q1=95.9, mediana=109.8,
# Q3=112.98) más el criterio de mercado de que una TCEA por debajo de 70%
# es competitiva y por encima de 110% es de las más caras del mercado.
BINS_TEA = [0, 70, 95.9, 110, np.inf]
LABELS_TEA = ["Baja", "Media", "Alta", "Muy alta"]

# --- 1.c Regla de negocio: bins de ingreso mínimo requerido -------------------
# Fundamento: segmentación estándar de banca de consumo en Perú
# (masivo / medio / premium / banca privada).
BINS_INGRESO = [0, 1500, 4000, 8000, np.inf]
LABELS_INGRESO = ["Masivo", "Medio", "Premium", "Banca privada"]

# --- 1.d Regla de negocio: bins de membresía anual ---------------------------
# Fundamento: cuartiles observados (Q1=80, mediana=170, Q3=386.75).
BINS_MEMBRESIA = [-0.01, 0, 150, 350, np.inf]
LABELS_MEMBRESIA = ["Gratuita", "Baja", "Media", "Alta"]


def crear_variables_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    tea_min = pd.to_numeric(df["tea_soles_min"], errors="coerce")
    tea_max = pd.to_numeric(df["tea_soles_max"], errors="coerce")
    membresia = pd.to_numeric(df["membresia_anual"], errors="coerce")
    seguro = pd.to_numeric(df["seguro_desgravamen_mensual"], errors="coerce")

    # TEA promedio y rango (cuando solo hay un valor de TEA, min==max)
    df["tea_promedio"] = pd.concat([tea_min, tea_max], axis=1).mean(axis=1, skipna=True)
    df["rango_tea"] = (tea_max - tea_min).clip(lower=0)

    # Regla de negocio: costo mínimo anual de mantener la tarjeta,
    # sin contar consumos ni intereses (membresía + seguro desgravamen anualizado).
    df["costo_anual_base"] = membresia.fillna(0) + (seguro.fillna(0) * 12)

    # Regla de negocio: extraer el monto de consumo mínimo exigido para
    # exonerar la membresía, cuando el requisito viene como texto tipo
    # "Consumo promedio mensual mínimo S/ 5,000" (vectorizado con regex).
    texto_requisito = df["requisito_exoneracion_membresia"].astype("string")
    extraido = texto_requisito.str.extract(r"S/\s*([\d,]+)", expand=False)
    df["consumo_minimo_exoneracion_soles"] = (
        extraido.str.replace(",", "", regex=False).astype("Float64")
    )
    df["exonera_por_consumo"] = texto_requisito.str.contains("Consumo", case=False, na=False)

    # Regla de negocio: bandera simple de si la tarjeta tiene programa de
    # puntos/millas/cashback documentado.
    programa = df["programa_recompensas"].astype("string")
    df["tiene_programa_recompensas"] = programa.notna() & (programa.str.strip() != "")

    # Nivel ordinal de categoría (jerarquía de mercado)
    df["nivel_categoria"] = df["categoria"].map(NIVEL_CATEGORIA).astype("Int8")

    return df


def crear_agregaciones(df: pd.DataFrame) -> pd.DataFrame:
    """Agregaciones por banco y por categoría, unidas de vuelta (vectorizado con transform)."""
    df = df.copy()

    df["tea_promedio_del_banco"] = df.groupby("banco")["tea_promedio"].transform("mean")
    df["membresia_promedio_del_banco"] = df.groupby("banco")["membresia_anual"].transform("mean")
    df["num_tarjetas_del_banco"] = df.groupby("banco")["tarjeta_nombre"].transform("count")

    df["ingreso_min_promedio_categoria"] = (
        df.groupby("categoria")["ingreso_minimo_requerido"].transform("mean")
    )

    # Diferencial de la tarjeta vs. el promedio de su banco (más info que el valor solo)
    df["tea_vs_promedio_banco"] = df["tea_promedio"] - df["tea_promedio_del_banco"]

    return df


def aplicar_binning(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["tea_max_bin"] = pd.cut(
        pd.to_numeric(df["tea_soles_max"], errors="coerce"),
        bins=BINS_TEA, labels=LABELS_TEA
    )
    df["ingreso_minimo_bin"] = pd.cut(
        pd.to_numeric(df["ingreso_minimo_requerido"], errors="coerce"),
        bins=BINS_INGRESO, labels=LABELS_INGRESO
    )
    df["membresia_bin"] = pd.cut(
        pd.to_numeric(df["membresia_anual"], errors="coerce"),
        bins=BINS_MEMBRESIA, labels=LABELS_MEMBRESIA
    )
    return df


def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    """Orquesta el paso 1 completo: limpieza + variables + agregaciones + binning."""
    df = limpiar_categoricas(df)
    df = crear_variables_derivadas(df)
    df = crear_agregaciones(df)
    df = aplicar_binning(df)
    return df


# ---------------------------------------------------------------------------
# 2. NORMALIZACIÓN / ESTANDARIZACIÓN
# ---------------------------------------------------------------------------
# Se elige el algoritmo según la distribución observada de cada variable:
#
#   - tea_soles_min / tea_soles_max / tea_promedio:
#       distribución razonablemente simétrica, sin outliers extremos
#       -> Z-score (StandardScaler)
#
#   - membresia_anual:
#       variable acotada (0 a ~600) que se quiere comparar en escala 0-1
#       entre bancos -> Min-Max Scaling
#
#   - ingreso_minimo_requerido:
#       fuertemente asimétrica (600 a 12,000, cola larga a la derecha)
#       -> RobustScaler (usa mediana/IQR, resiste outliers)

COLUMNAS_ZSCORE = ["tea_soles_min", "tea_soles_max", "tea_promedio"]
COLUMNAS_MINMAX = ["membresia_anual"]
COLUMNAS_ROBUST = ["ingreso_minimo_requerido"]


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for cols, scaler_cls, sufijo in [
        (COLUMNAS_ZSCORE, StandardScaler, "_zscore"),
        (COLUMNAS_MINMAX, MinMaxScaler, "_minmax"),
        (COLUMNAS_ROBUST, RobustScaler, "_robust"),
    ]:
        datos = df[cols].apply(pd.to_numeric, errors="coerce")
        mascara_valida = datos.notna().all(axis=1)
        if mascara_valida.sum() == 0:
            continue
        scaler = scaler_cls()
        valores_norm = scaler.fit_transform(datos.loc[mascara_valida])
        for i, col in enumerate(cols):
            nueva_col = col + sufijo
            df[nueva_col] = np.nan
            df.loc[mascara_valida, nueva_col] = valores_norm[:, i]

    return df


# ---------------------------------------------------------------------------
# 3. OPTIMIZACIÓN DE MEMORIA: downcasting y vectorización
# ---------------------------------------------------------------------------

COLUMNAS_CATEGORICAS = [
    "banco", "marca", "categoria",
    "tea_max_bin", "ingreso_minimo_bin", "membresia_bin",
]

COLUMNAS_FLOAT = [
    "tea_soles_min", "tea_soles_max", "tea_promedio", "rango_tea",
    "membresia_anual", "seguro_desgravamen_mensual", "ingreso_minimo_requerido",
    "bono_bienvenida", "costo_anual_base", "consumo_minimo_exoneracion_soles",
    "tea_promedio_del_banco", "membresia_promedio_del_banco",
    "ingreso_min_promedio_categoria", "tea_vs_promedio_banco",
]

COLUMNAS_INT = ["num_tarjetas_del_banco", "nivel_categoria"]

COLUMNAS_BOOL = ["exonera_por_consumo", "tiene_programa_recompensas"]


def optimizar_memoria(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Reduce memoria mediante:
      - downcasting de floats/enteros a la precisión mínima necesaria
      - conversión de strings de baja cardinalidad a dtype 'category'
      - conversión a bool nativo donde aplica

    Todo vectorizado: pd.to_numeric(..., downcast=...) opera sobre la
    Serie completa, sin loops fila por fila.
    """
    df = df.copy()
    mem_antes = df.memory_usage(deep=True).sum()

    for col in COLUMNAS_FLOAT:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce", downcast="float")

    for col in COLUMNAS_INT:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce", downcast="integer")

    for col in COLUMNAS_BOOL:
        if col in df.columns:
            df[col] = df[col].astype("boolean")

    for col in COLUMNAS_CATEGORICAS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    # Columnas de texto libre que mezclan números y strings en el
    # scraping (ej. requisito_exoneracion_membresia trae "200" o
    # "Consumo promedio mensual mínimo S/ 5,000" según el banco).
    # Se homogeneizan a 'string' para que Parquet no falle al inferir tipo.
    columnas_texto_libre = [
        "tarjeta_nombre", "requisito_exoneracion_membresia",
        "programa_recompensas", "ratio_acumulacion", "url_origen",
        "fecha_scraping",
    ]
    for col in columnas_texto_libre:
        if col in df.columns:
            df[col] = df[col].astype("string")

    mem_despues = df.memory_usage(deep=True).sum()

    if verbose:
        ahorro_pct = (1 - mem_despues / mem_antes) * 100 if mem_antes else 0
        print(f"Memoria antes:   {mem_antes / 1024:.2f} KB")
        print(f"Memoria después: {mem_despues / 1024:.2f} KB")
        print(f"Ahorro:          {ahorro_pct:.1f}%")

    return df


# ---------------------------------------------------------------------------
# Orquestador general del Tema 4
# ---------------------------------------------------------------------------

def ejecutar_tema4(df_gold: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    df_gold: DataFrame YA ARMONIZADO (ver schema.harmonizar_y_unificar).
    Devuelve el DataFrame enriquecido, normalizado y optimizado.
    """
    df = enriquecer(df_gold)
    df = normalizar(df)
    df = optimizar_memoria(df, verbose=verbose)
    return df