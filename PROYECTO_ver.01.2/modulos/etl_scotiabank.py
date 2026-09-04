import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import pandera as pa
from pandera import Column, Check
import time
import random
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any

# Agregar el directorio padre al path para importar utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importamos el logger de utilidades
from utils import logger

log = logger.setup_log('etl_interbank')

# ============================================================
# CARGA DE CONFIGURACIÓN
# ============================================================
with open("config/config.json", encoding="utf-8") as f:
    config = json.load(f)

urls_interbank = config["bancos"]["INTERBANK"]["Tarjeta de Crédito"]["urls"]
user_agents = config["user-agents"]["ua"]

# ============================================================
# ESQUEMA PANDERA (Validación de calidad)
# ============================================================
esquema_interbank = pa.DataFrameSchema({
    "nombre_tarjeta": Column(str, nullable=False),
    "categoria": Column(str, nullable=True),
    "membresia_anual_soles": Column(float, Check.ge(0.0), nullable=True),
    "millas_por_dolar_consumo": Column(float, Check.ge(0.0), nullable=True),
    "bono_bienvenida_millas": Column(float, Check.ge(0.0), nullable=True),
    "url_detalle": Column(str, nullable=True),
    "fecha_extraccion": Column(str, nullable=False),
    "fuente": Column(str, nullable=False),
    "segmento_gasto": Column(str, Check.isin(['Básico', 'Intermedio', 'Premium', 'Elite']), nullable=False),
    "gasto_mensual_estimado_soles": Column(float, Check.ge(0.0), nullable=False),
    "gasto_anual_estimado_soles": Column(float, Check.ge(0.0), nullable=False),
    "valor_milla_soles": Column(float, Check.gt(0.0), nullable=False),
    "millas_anuales_generadas": Column(float, Check.ge(0.0), nullable=False),
    "valor_millas_anual_soles": Column(float, Check.ge(0.0), nullable=False),
    "valor_bono_bienvenida_soles": Column(float, Check.ge(0.0), nullable=False),
    "valor_neto_primer_anio_soles": Column(float, nullable=True),
    "valor_neto_anual_recurrente_soles": Column(float, nullable=True),
}, coerce=True)

# ============================================================
# CONFIGURACIÓN
# ============================================================
CONFIG = {
    "url_base": urls_interbank[0] if urls_interbank else "https://interbank.pe/tarjetas/tarjetas-credito/millas-benefit",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "output_dir": Path(config.get("output", {}).get("base_dir", "data")),
    "raw_html_path": Path(config.get("output", {}).get("base_dir", "data")) / "raw/interbank_millas.html",
    "parquet_path": Path(config.get("output", {}).get("base_dir", "data")) / "processed/tarjetas_interbank_millas.parquet",
    "avro_path": Path(config.get("output", {}).get("base_dir", "data")) / "processed/tarjetas_interbank_millas.avro",
    "log_path": Path("logs/scraper_interbank.log"),
    "timeout": 20,
    "delay_entre_requests": (2, 5),
    "max_intentos": 3,
}

# Columnas maestras para el output final
COLUMNAS_MAESTRAS = [
    "nombre_tarjeta",
    "categoria",
    "membresia_anual_soles",
    "millas_por_dolar_consumo",
    "bono_bienvenida_millas",
    "url_detalle",
    "fecha_extraccion",
    "fuente",
    "segmento_gasto",
    "gasto_mensual_estimado_soles",
    "gasto_anual_estimado_soles",
    "valor_milla_soles",
    "millas_anuales_generadas",
    "valor_millas_anual_soles",
    "valor_bono_bienvenida_soles",
    "valor_neto_primer_anio_soles",
    "valor_neto_anual_recurrente_soles",
]

# ============================================================
# UTILIDADES
# ============================================================
def _extraer_numero(texto: str, patron: str) -> Optional[float]:
    """Extrae un número de un texto usando expresión regular"""
    if not texto:
        return None
    m = re.search(patron, texto, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "").replace("%", ""))
    except (ValueError, IndexError):
        return None

def setup_paths():
    """Crea los directorios necesarios"""
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    CONFIG["raw_html_path"].parent.mkdir(parents=True, exist_ok=True)
    CONFIG["parquet_path"].parent.mkdir(parents=True, exist_ok=True)
    CONFIG["log_path"].parent.mkdir(parents=True, exist_ok=True)

def fetch_page(url: str, headers: Dict, max_intentos: int = 3, timeout: int = 20) -> str:
    """
    Obtiene el HTML de una página con reintentos
    
    Args:
        url: URL a scrapear
        headers: Headers para la petición
        max_intentos: Número máximo de intentos
        timeout: Timeout de la petición
    
    Returns:
        str: HTML de la página
    
    Raises:
        Exception: Si fallan todos los intentos
    """
    # Espera ética antes de la petición
    espera = random.uniform(*CONFIG["delay_entre_requests"])
    log.info(f"⏳ Esperando {espera:.1f}s antes de solicitar (buenas prácticas)")
    time.sleep(espera)
    
    ultimo_error = None
    for intento in range(1, max_intentos + 1):
        try:
            log.info(f"📡 Solicitando {url} (intento {intento}/{max_intentos})")
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            html = response.text
            
            # Validación básica de contenido
            if "<h2" not in html.lower():
                raise RuntimeError("La respuesta no contiene el contenido esperado (<h2>)")
            
            # Guardar HTML crudo
            CONFIG["raw_html_path"].write_text(html, encoding="utf-8")
            log.info(f"💾 HTML crudo guardado en {CONFIG['raw_html_path']}")
            return html
            
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            espera_retry = 5 * intento
            log.warning(f"⚠️ Error de red en intento {intento}/{max_intentos}: {e}")
            if intento < max_intentos:
                log.info(f"Reintentando en {espera_retry}s...")
                time.sleep(espera_retry)
        except Exception as e:
            ultimo_error = e
            log.warning(f"⚠️ Error en intento {intento}/{max_intentos}: {e}")
            if intento < max_intentos:
                espera_retry = 5 * intento
                log.info(f"Reintentando en {espera_retry}s...")
                time.sleep(espera_retry)
    
    log.error(f"❌ No se pudo obtener la página tras {max_intentos} intentos")
    raise ultimo_error or RuntimeError("Fallo en todos los intentos")

# ============================================================
# EXTRACCIÓN DE DATOS CON REQUESTS Y BEAUTIFULSOUP
# ============================================================
def extraer_datos_tarjetas(url: str, headers: Dict) -> List[Dict]:
    """
    Extrae los datos de las tarjetas de Interbank usando requests y BeautifulSoup
    
    Args:
        url: URL de la página
        headers: Headers para la petición
    
    Returns:
        List[Dict]: Lista de diccionarios con los datos extraídos
    """
    log.info(f"🔍 Extrayendo datos de: {url}")
    
    # Obtener HTML
    html = fetch_page(url, headers, max_intentos=CONFIG["max_intentos"], timeout=CONFIG["timeout"])
    
    # Parsear con BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    datos = []
    
    # Extraer categorías del data-tab-items
    categorias_tab = {}
    cont_categorias = soup.find("div", class_="o-account-categories")
    if cont_categorias and cont_categorias.has_attr("data-tab-items"):
        try:
            categorias_tab = {
                c["ref"]: c.get("label", c["ref"])
                for c in json.loads(cont_categorias["data-tab-items"])
            }
            log.info(f"📂 Categorías detectadas: {list(categorias_tab.values())}")
        except Exception as e:
            log.warning(f"No se pudo parsear data-tab-items: {e}")
    
    # Extraer artículos
    articulos = soup.find_all("article", class_="o-account-categories__item")
    total = len(articulos)
    log.info(f"📄 Bloques de tarjeta encontrados (<article>): {total}")
    
    for i, art in enumerate(articulos, start=1):
        # Título
        h2 = art.find("h2", class_="o-account-categories__item__title")
        if not h2:
            log.debug(f"Bloque [{i}/{total}] sin título, se omite")
            continue
        
        nombre = h2.get_text(strip=True)
        if not nombre:
            log.debug(f"Bloque [{i}/{total}] con título vacío, se omite")
            continue
        
        log.info(f"🔍 Procesando [{i}/{total}] {nombre}")
        
        # Extraer texto completo del bloque
        texto_bloque = art.get_text(" ", strip=True)
        
        # Extraer datos financieros
        membresia = _extraer_numero(texto_bloque, r"S/\s?([\d,]+)")
        millas_por_dolar = _extraer_numero(texto_bloque, r"(?:hasta\s+)?([\d.]+)\s+[Mm]illas?\s+por\s+cada\s+\$")
        bono_bienvenida = _extraer_numero(texto_bloque, r"([\d,]+)\s+[Mm]illas.*?bono de bienvenida")
        
        # URL de detalle
        link_tag = art.find("a", class_="a-button")
        url_detalle = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
        if url_detalle and not url_detalle.startswith("http"):
            url_detalle = url.rstrip("/") + "/" + url_detalle.lstrip("/")
        
        # Categoría
        tab_div = art.find_parent("div", id=True)
        tab_ref = tab_div["id"] if tab_div else None
        categoria = categorias_tab.get(tab_ref, tab_ref or "Sin categoría")
        
        # Validación: descartar si no tiene datos relevantes
        if membresia is None and millas_por_dolar is None:
            log.info(f"  ⏭️ Descartada '{nombre}' (sin membresía ni millas)")
            continue
        
        datos.append({
            "nombre_tarjeta": nombre,
            "categoria": categoria,
            "membresia_anual_soles": membresia,
            "millas_por_dolar_consumo": millas_por_dolar,
            "bono_bienvenida_millas": bono_bienvenida or 0.0,
            "url_detalle": url_detalle,
            "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
            "fuente": url,
        })
        
        log.info(f"  ✅ Extraída correctamente: {nombre}")
    
    log.info(f"📊 Tarjetas extraídas: {len(datos)}/{total}")
    return datos

# ============================================================
# ENRIQUECIMIENTO Y NORMALIZACIÓN
# ============================================================
def aplicar_enriquecimiento(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica reglas de negocio, enriquecimiento y normalización al DataFrame
    """
    df_enriched = df.copy()
    
    # Segmentación basada en membresía
    def clasificar_segmento(membresia: float) -> Tuple[str, float]:
        if pd.isna(membresia) or membresia == 0:
            return "Básico", 800.0
        if 0 < membresia < 90:
            return "Básico", 800.0
        if 90 <= membresia < 250:
            return "Intermedio", 2500.0
        if 250 <= membresia < 450:
            return "Premium", 6000.0
        return "Elite", 12000.0
    
    # Aplicar clasificación
    segmentos = df_enriched["membresia_anual_soles"].apply(
        lambda x: clasificar_segmento(x if pd.notna(x) else 0.0)
    )
    df_enriched["segmento_gasto"] = [s[0] for s in segmentos]
    df_enriched["gasto_mensual_estimado_soles"] = [s[1] for s in segmentos]
    
    # Cálculos financieros
    df_enriched["gasto_anual_estimado_soles"] = (
        df_enriched["gasto_mensual_estimado_soles"] * 12
    )
    
    # Valor de la milla (constante)
    valor_milla = 0.03
    df_enriched["valor_milla_soles"] = valor_milla
    
    # Cálculo de millas generadas
    tasa_millas = df_enriched["millas_por_dolar_consumo"].fillna(1.0)
    tipo_cambio = 3.75
    
    df_enriched["millas_anuales_generadas"] = (
        (df_enriched["gasto_anual_estimado_soles"] / tipo_cambio) * tasa_millas
    ).round(0)
    
    # Valor en soles
    df_enriched["valor_millas_anual_soles"] = (
        df_enriched["millas_anuales_generadas"] * df_enriched["valor_milla_soles"]
    ).round(2)
    
    df_enriched["valor_bono_bienvenida_soles"] = (
        df_enriched["bono_bienvenida_millas"] * df_enriched["valor_milla_soles"]
    ).round(2)
    
    # Valor neto (primer año y recurrente)
    df_enriched["valor_neto_primer_anio_soles"] = (
        df_enriched["valor_millas_anual_soles"]
        + df_enriched["valor_bono_bienvenida_soles"]
        - df_enriched["membresia_anual_soles"]
    ).round(2)
    
    df_enriched["valor_neto_anual_recurrente_soles"] = (
        df_enriched["valor_millas_anual_soles"] 
        - df_enriched["membresia_anual_soles"]
    ).round(2)
    
    # Optimización de memoria
    cols_float = df_enriched.select_dtypes(include=['float64']).columns
    df_enriched[cols_float] = df_enriched[cols_float].apply(pd.to_numeric, downcast='float')
    
    # Columnas categóricas
    cols_cat = ['segmento_gasto']
    df_enriched[cols_cat] = df_enriched[cols_cat].astype('category')
    
    log.info(f"📈 Enriquecimiento completado")
    log.info(f"   - Segmentos: {df_enriched['segmento_gasto'].value_counts().to_dict()}")
    log.info(f"   - Valor promedio de millas anuales: S/ {df_enriched['valor_millas_anual_soles'].mean():.2f}")
    log.info(f"   - Gasto mensual promedio estimado: S/ {df_enriched['gasto_mensual_estimado_soles'].mean():.2f}")
    
    return df_enriched

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================
def run_pipeline() -> pd.DataFrame:
    """
    Invoca la extracción y aplica enriquecimiento, binning, normalización y 
    validación de Pandera internamente antes de devolver el DataFrame.
    """
    log.info('=' * 55)
    log.info(f'PIPELINE: EXTRACCIÓN DE TC')
    log.info(f'BANCO   : INTERBANK')
    log.info(f'URL     : {CONFIG["url_base"]}')
    log.info('=' * 55)
    
    log.info("Iniciando extracción INTERBANK (Capa Silver)...")
    
    # Crear directorios necesarios
    setup_paths()
    
    datos_completos = []
    
    try:
        # Extraer datos de cada URL
        urls = CONFIG["url_base"] if isinstance(CONFIG["url_base"], list) else [CONFIG["url_base"]]
        for url in urls:
            datos = extraer_datos_tarjetas(url, CONFIG["headers"])
            datos_completos.extend(datos)
            
    except Exception as e:
        log.error(f"❌ Error en la extracción: {e}", exc_info=True)
        raise
    
    # Crear DataFrame
    df_interbank = pd.DataFrame(datos_completos)
    
    if df_interbank.empty:
        log.error("❌ No se extrajeron datos. Pipeline detenido.")
        return pd.DataFrame(columns=COLUMNAS_MAESTRAS)
    
    log.info(f"✅ Datos extraídos: {len(df_interbank)} tarjetas")
    
    # ============================================================
    # LIMPIEZA Y CALIDAD DE DATOS
    # ============================================================
    log.info("Aplicando limpieza y calidad de datos...")
    
    # Limpieza de strings
    for col in ["nombre_tarjeta", "categoria", "url_detalle"]:
        if col in df_interbank.columns:
            df_interbank[col] = df_interbank[col].astype(str).str.strip()
            df_interbank[col] = df_interbank[col].replace("nan", None)
    
    # Eliminar duplicados
    df_interbank = df_interbank.drop_duplicates(subset=["nombre_tarjeta", "fecha_extraccion"])
    
    # Convertir columnas numéricas
    for col in ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]:
        df_interbank[col] = pd.to_numeric(df_interbank[col], errors="coerce")
    
    # Eliminar filas sin nombre de tarjeta
    df_interbank = df_interbank[df_interbank["nombre_tarjeta"].notna() & (df_interbank["nombre_tarjeta"] != "")]
    
    # Reemplazar nulos en columnas numéricas con 0
    num_cols = ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]
    for col in num_cols:
        if col in df_interbank.columns:
            df_interbank[col] = df_interbank[col].fillna(0.0)
    
    log.info(f"🧹 Limpieza aplicada. Quedan {len(df_interbank)} filas.")
    
    # ============================================================
    # ENRIQUECIMIENTO Y NORMALIZACIÓN
    # ============================================================
    log.info("Aplicando reglas de negocio, Enriquecimiento y Normalización...")
    df_interbank = aplicar_enriquecimiento(df_interbank)
    
    # ============================================================
    # VALIDACIÓN CON PANDERA
    # ============================================================
    log.info("Ejecutando validación de calidad (Pandera)...")
    try:
        df_interbank = esquema_interbank.validate(df_interbank)
        log.info("✅ Validación de Pandera superada con éxito para INTERBANK.")
    except pa.errors.SchemaError as exc:
        log.error(f"❌ Error de validación en INTERBANK: {exc}")
        raise
    
    # ============================================================
    # PERSISTENCIA
    # ============================================================
    log.info("Guardando datos procesados...")
    
    # Guardar en Parquet
    df_interbank.to_parquet(CONFIG["parquet_path"], index=False)
    log.info(f"💾 Datos guardados en Parquet: {CONFIG['parquet_path']}")
    
    # Guardar en CSV (como en el código original de Scotiabank)
    csv_path = CONFIG["output_dir"] / "processed/tarjetas_interbank_millas.csv"
    df_interbank.to_csv(csv_path, index=False, encoding='utf-8')
    log.info(f"💾 Datos guardados en CSV: {csv_path}")
    
    # Guardar en Avro (opcional)
    try:
        import fastavro
        records = df_interbank.to_dict('records')
        schema = {
            "type": "record",
            "name": "TarjetaInterbank",
            "fields": [
                {"name": col, "type": ["null", "string", "float", "int"]} 
                for col in df_interbank.columns
            ]
        }
        with open(CONFIG["avro_path"], 'wb') as f:
            fastavro.writer(f, schema, records)
        log.info(f"💾 Datos guardados en Avro: {CONFIG['avro_path']}")
    except ImportError:
        log.warning("⚠️ Fastavro no instalado. Saltando guardado en Avro.")
    except Exception as e:
        log.warning(f"⚠️ Error guardando en Avro: {e}")
    
    log.info(f"✅ Módulo INTERBANK finalizado completamente. Registros: {len(df_interbank)}")
    
    return df_interbank

# ============================================================
# FUNCIONES DE EXTRACCIÓN SIMPLIFICADAS (Compatibilidad con el original)
# ============================================================
def extraer_hrefs(url: str, headers: Dict) -> List[str]:
    """
    Función simplificada para extraer hrefs (compatibilidad con el código original)
    """
    log.info(f"🔗 Extrayendo URLs de: {url}")
    html = fetch_page(url, headers)
    soup = BeautifulSoup(html, "lxml")
    
    # Buscar enlaces a tarjetas
    hrefs = []
    links = soup.find_all("a", href=True)
    for link in links:
        href = link.get("href", "")
        if "tarjeta" in href.lower() or "credito" in href.lower():
            if href.startswith("/"):
                hrefs.append(href)
            elif href.startswith("http"):
                hrefs.append(href)
    
    log.info(f"📎 Encontrados {len(hrefs)} enlaces")
    return hrefs

def extraer_datos_simplificado(hrefs: List[str], headers: Dict) -> List[Dict]:
    """
    Función simplificada para extraer datos (compatibilidad con el código original)
    """
    resultados = []
    for href in hrefs:
        if href.startswith("/"):
            full_url = f"https://interbank.pe{href}"
        else:
            full_url = href
        
        try:
            html = fetch_page(full_url, headers)
            soup = BeautifulSoup(html, "lxml")
            
            # Extraer datos básicos
            nombre = soup.find("h1")
            nombre_texto = nombre.get_text(strip=True) if nombre else "Desconocido"
            
            # Buscar datos financieros en el texto
            texto_pagina = soup.get_text(" ", strip=True)
            membresia = _extraer_numero(texto_pagina, r"S/\s?([\d,]+)")
            millas = _extraer_numero(texto_pagina, r"([\d.]+)\s+[Mm]illas")
            
            resultados.append({
                "nombre_tarjeta": nombre_texto,
                "categoria": "Sin categoría",
                "membresia_anual_soles": membresia,
                "millas_por_dolar_consumo": millas,
                "bono_bienvenida_millas": 0.0,
                "url_detalle": full_url,
                "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
                "fuente": "interbank.pe",
            })
            
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            log.warning(f"⚠️ Error extrayendo {full_url}: {e}")
    
    return resultados

def run_simplificado() -> pd.DataFrame:
    """
    Versión simplificada que imita el flujo del código original de Scotiabank
    """
    hrefs = extraer_hrefs(CONFIG["url_base"], CONFIG["headers"])
    datos = extraer_datos_simplificado(hrefs, CONFIG["headers"])
    return pd.DataFrame(datos)

# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================
if __name__ == "__main__":
    try:
        # Ejecutar pipeline completo
        df_resultado = run_pipeline()
        
        if df_resultado is not None and not df_resultado.empty:
            print("\n" + "="*70)
            print("📊 RESUMEN DE DATOS EXTRAÍDOS".center(70))
            print("="*70)
            print(f"Total de tarjetas: {len(df_resultado)}")
            print("\nSegmentos encontrados:")
            print(df_resultado['segmento_gasto'].value_counts().to_string())
            print("\nPrimeras 5 tarjetas:")
            print(df_resultado[['nombre_tarjeta', 'segmento_gasto', 
                               'membresia_anual_soles', 'millas_por_dolar_consumo']].head().to_string())
            
            # Mostrar estadísticas de enriquecimiento
            print("\n📈 Estadísticas de enriquecimiento:")
            print(f"Valor promedio de millas anuales: S/ {df_resultado['valor_millas_anual_soles'].mean():.2f}")
            print(f"Valor neto promedio primer año: S/ {df_resultado['valor_neto_primer_anio_soles'].mean():.2f}")
            print(f"Gasto mensual promedio estimado: S/ {df_resultado['gasto_mensual_estimado_soles'].mean():.2f}")
            
    except KeyboardInterrupt:
        print("\n⚠️ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")