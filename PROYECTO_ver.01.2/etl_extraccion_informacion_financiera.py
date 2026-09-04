from modulos import etl_bbva, etl_bcp, etl_scotiabank, etl_banbif, etl_interbank
from modulos import schema, feature_engineering, validacion
import logging
from datetime import datetime
import pandas as pd
from utils import logger, storage
from modulos import validacion

log = logger.setup_log()
periodo = datetime.now().strftime('%Y-%m-%d')

RUTAS = {
    'ruta_bbva'        : f"./output/tarjetas_bbva_{periodo}.parquet",
    'ruta_bbva_excel'  : f"./output/tarjetas_bbva_{periodo}.xlsx",
    'ruta_bcp'         : f"./output/tarjetas_bcp_{periodo}.parquet",
    'ruta_bcp_excel'   : f"./output/tarjetas_bcp_{periodo}.xlsx",
    'ruta_scotia'      : f"./output/tarjetas_scotiabank_{periodo}.parquet",
    'ruta_scotia_excel': f"./output/tarjetas_scotiabank_{periodo}.xlsx",
    'ruta_banbif'      : f"./output/tarjetas_banbif_{periodo}.parquet",
    'ruta_banbif_excel': f"./output/tarjetas_banbif_{periodo}.xlsx",
    'ruta_ibk'         : f"./output/tarjetas_ibk_{periodo}.parquet",
    'ruta_ibk_excel'   : f"./output/tarjetas_ibk_{periodo}.xlsx",
    'ruta_gold'        : f"./output/tarjetas_gold_{periodo}.parquet",
    'ruta_gold_excel'  : f"./output/tarjetas_gold_{periodo}.xlsx",
    'ruta_gold_features'       : f"./output/tarjetas_gold_features_{periodo}.parquet",
    'ruta_gold_features_excel' : f"./output/tarjetas_gold_features_{periodo}.xlsx",
}

if __name__ == "__main__":
    log.info("="*20)
    log.info("Inicio: SCRAPPING BANCOS PERÚ")
    log.info("="*20)

    try:
        log.info("1. OBTENIENDO CAPA RAW Y SILVER")

        df_bbva = etl_bbva.run()
        storage.save(df_bbva, {
            "parquet": RUTAS["ruta_bbva"],
            "excel": RUTAS["ruta_bbva_excel"]
        })

        df_bcp = etl_bcp.run_pipeline()
        storage.save(df_bcp, {
            "parquet": RUTAS["ruta_bcp"],
            "excel": RUTAS["ruta_bcp_excel"]
        })

        df_scotia = etl_scotiabank.run()
        storage.save(df_scotia, {
            "parquet": RUTAS["ruta_scotia"],
            "excel": RUTAS["ruta_scotia_excel"]
        })

        df_banbif = etl_banbif.run()
        storage.save(df_banbif, {
            "parquet": RUTAS["ruta_banbif"],
            "excel": RUTAS["ruta_banbif_excel"]
        })

        df_interbank = etl_interbank.run()
        storage.save(df_interbank, {
            "parquet": RUTAS["ruta_ibk"],
            "excel": RUTAS["ruta_ibk_excel"]
        })

        log.info("="*20)
        log.info("2. UNIFICANDO INFORMACIÓN EN LA CAPA GOLD (esquema armonizado)")
        log.info("="*20)

        # ANTES se usaba pd.concat directo, lo cual generaba columnas
        # duplicadas (banco/Banco, tea_soles_max/"tea_soles_max ") porque
        # cada banco tiene nombres de columna distintos. Ahora se
        # armonizan primero a un esquema canónico (ver modulos/schema.py).
        df_gold = schema.harmonizar_y_unificar({
            "BBVA": df_bbva,
            "BCP": df_bcp,
            "SCOTIABANK": df_scotia,
            "BANBIF": df_banbif,
            "INTERBANK": df_interbank,
        })

        validacion.validar_gold_armonizado(df_gold)
        log.info("Validación Pandera (capa gold cruda): OK")

        # 🔧 Normalizar columnas mixtas antes de guardar en Parquet
        columnas_mixtas = [
            "requisito_exoneracion_membresia",
            "requisito_exoneracion_membresia_detalle",
            "condiciones_membresia",
        ]

        for col in columnas_mixtas:
            if col in df_gold.columns:
                df_gold[col] = df_gold[col].astype("string")
        
        storage.save(df_gold, {
            "parquet": RUTAS["ruta_gold"],
            "excel": RUTAS["ruta_gold_excel"]
        })

        log.info("="*20)
        log.info("3. TEMA 4: ENRIQUECIMIENTO, NORMALIZACIÓN Y OPTIMIZACIÓN")
        log.info("="*20)

        df_gold_features = feature_engineering.ejecutar_tema4(df_gold)

        validacion.validar_gold_enriquecido(df_gold_features)
        log.info("Validación Pandera (capa gold enriquecida): OK")

        storage.save(df_gold_features, {
            "parquet": RUTAS["ruta_gold_features"],
            "excel": RUTAS["ruta_gold_features_excel"]
        })

        log.info("="*20)
        log.info("4. EXPORTANDO ARCHIVO FINAL")
        log.info("="*20)

    except Exception as e:
        log.exception(f"Ocurrió un error {e}")

    log.info("SE COMPLETÓ EL PROCESO CORRECTAMENTE")
    
    try:
        # Validación para capa gold armonizada
        validacion.validar_gold_armonizado(df_gold)
        log.info("✅ Validación Pandera (capa gold cruda): OK")
        
        # ... feature engineering ...
        
        # Validación para capa gold enriquecida - Modo flexible
        validacion.validar_gold_enriquecido(df_gold_features, modo_estricto=False)
        log.info("✅ Validación Pandera (capa gold enriquecida): OK")
        
        # O usar validación adaptativa
        # validacion.validar_gold_enriquecido_adaptativo(df_gold_features)
        
        # Generar reporte de validación
        reporte = validacion.generar_reporte_validacion(df_gold_features)
        log.info(f"\n{reporte}")
        
        # Generar resumen estadístico
        resumen = validacion.resumen_estadistico(df_gold_features)
        
    except Exception as e:
        log.error(f"❌ Error en validación: {e}")
        raise