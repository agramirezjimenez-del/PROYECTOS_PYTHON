# modulos/validacion.py
import pandas as pd
import logging
from typing import List, Optional, Dict, Any

log = logging.getLogger("etl_productos_financieros")

# Esquema esperado para la capa GOLD armonizada
COLUMNAS_ESPERADAS = [
    "tarjeta_nombre",
    "banco",
    "marca",
    "categoria",
    "tea_soles_min",
    "tea_soles_max",
    "membresia_anual",
    "seguro_desgravamen_mensual",
    "ingreso_minimo_requerido",
    "requisito_exoneracion_membresia",
    "programa_recompensas",
    "ratio_acumulacion",
    "url_origen",
    "fecha_scraping",
]

# Esquema esperado para la capa GOLD enriquecida (con features adicionales)
COLUMNAS_ENRIQUECIDAS_ESPERADAS = [
    "tarjeta_nombre",
    "banco",
    "marca",
    "categoria",
    "tea_soles_min",
    "tea_soles_max",
    "membresia_anual",
    "seguro_desgravamen_mensual",
    "ingreso_minimo_requerido",
    "requisito_exoneracion_membresia",
    "programa_recompensas",
    "ratio_acumulacion",
    "url_origen",
    "fecha_scraping",
    # Columnas añadidas por feature_engineering
    "tea_soles_promedio",
    "tea_dolares_promedio",
    "costo_membresia_mensual",
    "costo_total_estimado",
    "tiene_recompensas",
    "nivel_beneficios",
    "puntaje_competitividad",
    "ratio_beneficio_costo",
    "grupo_ingreso",
    "categoria_riesgo",
    "recomendacion",
]

# Columnas esenciales que siempre deben existir
COLUMNAS_ESENCIALES = [
    "tarjeta_nombre",
    "banco",
    "tea_soles_min",
    "tea_soles_max",
    "membresia_anual",
]


def validar_gold_armonizado(df: pd.DataFrame) -> None:
    """
    Valida que la capa GOLD tenga todas las columnas del esquema armonizado.
    Lanza error si falta alguna columna.
    
    Args:
        df: DataFrame a validar
        
    Raises:
        ValueError: Si faltan columnas requeridas
    """
    if df is None or df.empty:
        log.error("❌ Validación GOLD armonizado falló: DataFrame vacío o None")
        raise ValueError("DataFrame vacío o None en capa GOLD armonizada")
    
    faltantes = [col for col in COLUMNAS_ESPERADAS if col not in df.columns]

    if faltantes:
        log.error(f"❌ Validación GOLD falló. Columnas faltantes: {faltantes}")
        raise ValueError(f"Columnas faltantes en GOLD: {faltantes}")

    log.info(f"✔ Validación GOLD OK: esquema completo y armonizado. ({len(df)} filas)")


def validar_gold_enriquecido(df: pd.DataFrame, modo_estricto: bool = False) -> None:
    """
    Valida que la capa GOLD enriquecida tenga las columnas esperadas.
    
    Args:
        df: DataFrame a validar
        modo_estricto: Si True, valida todas las columnas del esquema.
                       Si False, valida solo columnas esenciales.
    
    Raises:
        ValueError: Si faltan columnas requeridas o el DataFrame está vacío
    """
    if df is None or df.empty:
        log.error("❌ Validación GOLD enriquecida falló: DataFrame vacío o None")
        raise ValueError("DataFrame vacío o None en capa GOLD enriquecida")
    
    # Verificar columnas esenciales
    faltantes_esenciales = [col for col in COLUMNAS_ESENCIALES if col not in df.columns]
    if faltantes_esenciales:
        log.error(f"❌ Columnas esenciales faltantes: {faltantes_esenciales}")
        raise ValueError(f"Columnas esenciales faltantes en GOLD enriquecida: {faltantes_esenciales}")
    
    if modo_estricto:
        # Modo estricto: validar todas las columnas del esquema
        columnas_faltantes = [col for col in COLUMNAS_ENRIQUECIDAS_ESPERADAS if col not in df.columns]
        if columnas_faltantes:
            log.error(f"❌ Columnas de feature engineering faltantes: {columnas_faltantes}")
            raise ValueError(f"Columnas faltantes en GOLD enriquecida: {columnas_faltantes}")
    
    # Validaciones de calidad de datos
    _validar_calidad_datos_enriquecidos(df)
    
    # Log de estadísticas del DataFrame
    log.info(f"✅ Validación GOLD enriquecida OK: {len(df)} filas, {len(df.columns)} columnas")
    
    # Mostrar columnas disponibles
    log.info(f"📋 Columnas disponibles: {list(df.columns)}")
    
    # Mostrar estadísticas básicas de columnas numéricas
    columnas_numericas = df.select_dtypes(include=['number']).columns
    if len(columnas_numericas) > 0:
        log.info(f"📊 Columnas numéricas encontradas: {len(columnas_numericas)}")
        for col in columnas_numericas[:5]:  # Mostrar solo primeras 5
            if not df[col].isna().all():
                log.info(f"   {col}: media={df[col].mean():.2f}, min={df[col].min():.2f}, max={df[col].max():.2f}")


def validar_gold_enriquecido_adaptativo(df: pd.DataFrame, columnas_requeridas: Optional[List[str]] = None) -> None:
    """
    Valida la capa GOLD enriquecida de forma adaptativa,
    verificando solo las columnas que existen o las que se especifiquen.
    
    Args:
        df: DataFrame a validar
        columnas_requeridas: Lista opcional de columnas requeridas.
                            Si no se proporciona, usa COLUMNAS_ESENCIALES.
    
    Raises:
        ValueError: Si faltan columnas requeridas o el DataFrame está vacío
    """
    if df is None or df.empty:
        log.error("❌ Validación adaptativa falló: DataFrame vacío o None")
        raise ValueError("DataFrame vacío o None en capa GOLD enriquecida")
    
    # Usar columnas esenciales por defecto
    columnas_a_validar = columnas_requeridas if columnas_requeridas else COLUMNAS_ESENCIALES
    
    # Verificar columnas requeridas
    columnas_faltantes = [col for col in columnas_a_validar if col not in df.columns]
    if columnas_faltantes:
        log.error(f"❌ Columnas requeridas faltantes: {columnas_faltantes}")
        raise ValueError(f"Columnas requeridas faltantes: {columnas_faltantes}")
    
    log.info(f"✅ Validación adaptativa exitosa: {len(df)} filas, {len(df.columns)} columnas")
    
    # Registrar qué columnas de features están presentes
    features_esperadas = [
        'tea_soles_promedio', 'tea_dolares_promedio',
        'costo_membresia_mensual', 'costo_total_estimado',
        'tiene_recompensas', 'nivel_beneficios',
        'puntaje_competitividad', 'ratio_beneficio_costo',
        'grupo_ingreso', 'categoria_riesgo', 'recomendacion'
    ]
    
    features_presentes = [col for col in features_esperadas if col in df.columns]
    features_faltantes = [col for col in features_esperadas if col not in df.columns]
    
    if features_presentes:
        log.info(f"✅ Features encontrados: {features_presentes}")
    if features_faltantes:
        log.warning(f"⚠️ Features no generados: {features_faltantes}")


def _validar_calidad_datos_enriquecidos(df: pd.DataFrame) -> None:
    """
    Validaciones de calidad de datos para la capa enriquecida.
    
    Args:
        df: DataFrame a validar
    """
    # Verificar que no haya valores nulos en columnas críticas
    columnas_criticas = ['banco', 'tarjeta_nombre']
    for col in columnas_criticas:
        if col in df.columns and df[col].isna().any():
            nulos = df[col].isna().sum()
            log.warning(f"⚠️ Columna '{col}' tiene {nulos} valores nulos")
    
    # Verificar que tea_soles_min no sea mayor que tea_soles_max
    if 'tea_soles_min' in df.columns and 'tea_soles_max' in df.columns:
        inconsistentes = df[df['tea_soles_min'] > df['tea_soles_max']]
        if len(inconsistentes) > 0:
            log.warning(f"⚠️ {len(inconsistentes)} registros tienen tea_soles_min > tea_soles_max")
    
    # Verificar rangos razonables para tasas de interés
    if 'tea_soles_max' in df.columns:
        fuera_rango = df[(df['tea_soles_max'] < 0) | (df['tea_soles_max'] > 200)]
        if len(fuera_rango) > 0:
            log.warning(f"⚠️ {len(fuera_rango)} registros tienen TEA fuera de rango (0-200%)")
    
    # Verificar membresía anual
    if 'membresia_anual' in df.columns:
        negativos = df[df['membresia_anual'] < 0]
        if len(negativos) > 0:
            log.warning(f"⚠️ {len(negativos)} registros tienen membresía anual negativa")
    
    # Verificar ingresos mínimos
    if 'ingreso_minimo_requerido' in df.columns:
        ingresos_negativos = df[df['ingreso_minimo_requerido'] < 0]
        if len(ingresos_negativos) > 0:
            log.warning(f"⚠️ {len(ingresos_negativos)} registros tienen ingreso mínimo negativo")


def validar_columnas_numericas(df: pd.DataFrame, columnas: List[str]) -> None:
    """
    Valida que las columnas especificadas sean numéricas y tengan valores válidos.
    
    Args:
        df: DataFrame a validar
        columnas: Lista de columnas a verificar
        
    Raises:
        ValueError: Si no se pueden convertir a numérico
    """
    for col in columnas:
        if col in df.columns:
            try:
                # Intentar convertir a numérico
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Verificar valores no numéricos
                no_numericos = df[col].isna().sum()
                if no_numericos > 0:
                    log.warning(f"⚠️ Columna '{col}' tiene {no_numericos} valores no numéricos convertidos a NaN")
                    
            except Exception as e:
                log.error(f"❌ Error validando columna '{col}': {str(e)}")
                raise ValueError(f"Error validando columna '{col}': {str(e)}")


def validar_fechas(df: pd.DataFrame, columna_fecha: str = 'fecha_scraping') -> None:
    """
    Valida que la columna de fechas tenga el formato correcto.
    
    Args:
        df: DataFrame a validar
        columna_fecha: Nombre de la columna de fecha
        
    Raises:
        ValueError: Si la columna de fecha no es válida
    """
    if columna_fecha not in df.columns:
        log.warning(f"⚠️ Columna de fecha '{columna_fecha}' no encontrada")
        return
    
    try:
        # Intentar convertir a datetime
        df[columna_fecha] = pd.to_datetime(df[columna_fecha], errors='coerce')
        
        # Verificar fechas inválidas
        fechas_invalidas = df[columna_fecha].isna().sum()
        if fechas_invalidas > 0:
            log.warning(f"⚠️ {fechas_invalidas} fechas inválidas en columna '{columna_fecha}'")
            
    except Exception as e:
        log.error(f"❌ Error validando fechas en columna '{columna_fecha}': {str(e)}")
        raise ValueError(f"Error validando fechas: {str(e)}")


def resumen_estadistico(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Genera un resumen estadístico del DataFrame.
    
    Args:
        df: DataFrame a analizar
        
    Returns:
        Dict: Diccionario con estadísticas resumidas
    """
    if df is None or df.empty:
        log.warning("⚠️ DataFrame vacío, no se puede generar resumen")
        return {}
    
    resumen = {
        'total_registros': len(df),
        'total_columnas': len(df.columns),
        'memoria_uso_mb': df.memory_usage(deep=True).sum() / 1024**2,
    }
    
    # Información de bancos
    if 'banco' in df.columns:
        resumen['bancos'] = df['banco'].unique().tolist()
        resumen['total_bancos'] = len(resumen['bancos'])
        resumen['distribucion_bancos'] = df['banco'].value_counts().to_dict()
    
    # Información de categorías
    if 'categoria' in df.columns:
        resumen['categorias'] = df['categoria'].unique().tolist()
        resumen['total_categorias'] = len(resumen['categorias'])
    
    # Estadísticas de TEA
    for col in ['tea_soles_min', 'tea_soles_max']:
        if col in df.columns and not df[col].isna().all():
            resumen[col] = {
                'media': df[col].mean(),
                'min': df[col].min(),
                'max': df[col].max(),
                'mediana': df[col].median(),
                'std': df[col].std()
            }
    
    # Estadísticas de membresía
    if 'membresia_anual' in df.columns and not df['membresia_anual'].isna().all():
        resumen['membresia_anual'] = {
            'media': df['membresia_anual'].mean(),
            'min': df['membresia_anual'].min(),
            'max': df['membresia_anual'].max(),
            'mediana': df['membresia_anual'].median()
        }
    
    # Verificar valores nulos
    valores_nulos = df.isnull().sum()
    if valores_nulos.sum() > 0:
        resumen['valores_nulos'] = valores_nulos[valores_nulos > 0].to_dict()
    
    log.info(f"📊 Resumen del dataset: {resumen}")
    return resumen


def validar_integridad_referencial(df: pd.DataFrame) -> None:
    """
    Valida la integridad referencial de los datos.
    
    Args:
        df: DataFrame a validar
        
    Raises:
        ValueError: Si hay problemas de integridad referencial
    """
    if df is None or df.empty:
        return
    
    # Verificar que no haya duplicados en combinación banco-tarjeta
    if 'banco' in df.columns and 'tarjeta_nombre' in df.columns:
        duplicados = df.duplicated(subset=['banco', 'tarjeta_nombre'])
        if duplicados.any():
            num_duplicados = duplicados.sum()
            log.warning(f"⚠️ {num_duplicados} registros duplicados encontrados (banco + tarjeta)")
            
            # Mostrar ejemplos de duplicados
            duplicados_df = df[duplicados][['banco', 'tarjeta_nombre']].head(3)
            log.warning(f"Ejemplos de duplicados:\n{duplicados_df}")
    
    # Verificar que las tarjetas tengan nombre no vacío
    if 'tarjeta_nombre' in df.columns:
        nombres_vacios = df[df['tarjeta_nombre'].isna() | (df['tarjeta_nombre'] == '')]
        if len(nombres_vacios) > 0:
            log.warning(f"⚠️ {len(nombres_vacios)} tarjetas sin nombre")


def generar_reporte_validacion(df: pd.DataFrame) -> str:
    """
    Genera un reporte detallado de validación.
    
    Args:
        df: DataFrame a validar
        
    Returns:
        str: Reporte de validación en formato texto
    """
    if df is None or df.empty:
        return "⚠️ DataFrame vacío o None"
    
    reporte = []
    reporte.append("="*60)
    reporte.append("REPORTE DE VALIDACIÓN DE DATOS")
    reporte.append("="*60)
    reporte.append(f"Total de registros: {len(df)}")
    reporte.append(f"Total de columnas: {len(df.columns)}")
    reporte.append(f"Memoria utilizada: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    reporte.append("")
    
    # Columnas presentes
    reporte.append("📋 COLUMNAS PRESENTES:")
    for col in df.columns:
        tipo = df[col].dtype
        nulos = df[col].isna().sum()
        unicos = df[col].nunique()
        reporte.append(f"  - {col}: {tipo}, {nulos} nulos, {unicos} valores únicos")
    reporte.append("")
    
    # Distribución por banco
    if 'banco' in df.columns:
        reporte.append("🏦 DISTRIBUCIÓN POR BANCO:")
        for banco, count in df['banco'].value_counts().items():
            reporte.append(f"  - {banco}: {count} tarjetas")
        reporte.append("")
    
    # Resumen de TEA
    if 'tea_soles_min' in df.columns:
        reporte.append("📊 ESTADÍSTICAS DE TEA SOLES:")
        reporte.append(f"  - Mínimo: {df['tea_soles_min'].min():.2f}%")
        reporte.append(f"  - Máximo: {df['tea_soles_max'].max():.2f}%")
        reporte.append(f"  - Promedio (min): {df['tea_soles_min'].mean():.2f}%")
        reporte.append(f"  - Promedio (max): {df['tea_soles_max'].mean():.2f}%")
        reporte.append("")
    
    reporte.append("="*60)
    reporte.append("✅ VALIDACIÓN COMPLETADA")
    
    return "\n".join(reporte)