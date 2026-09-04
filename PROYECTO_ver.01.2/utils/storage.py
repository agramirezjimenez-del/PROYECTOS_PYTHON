# utils/storage.py
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
import os

log = logging.getLogger('etl_productos_financieros')

def save(df: pd.DataFrame, rutas: dict) -> dict:
    rutas_guardadas = {}

    for nombre, ruta in rutas.items():
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(ruta), exist_ok=True)

        if ruta.endswith(".csv"):
            df.to_csv(ruta, index=False, encoding="utf-8-sig")

        elif ruta.endswith(".parquet"):
            df.to_parquet(ruta, index=False, compression="snappy")

        elif ruta.endswith(".xlsx"):
            df.to_excel(ruta, index=False)

        else:
            raise ValueError(f"Formato no soportado: {ruta}")

        rutas_guardadas[nombre] = ruta
        log.info(f"Archivo guardado: {ruta}")

    return rutas_guardadas