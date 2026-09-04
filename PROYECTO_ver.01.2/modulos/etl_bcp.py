import pandas as pd
import numpy as np
import pandera as pa
from pandera import Column, Check
import time
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    StaleElementReferenceException, ElementNotInteractableException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

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
    "output_dir": Path(config.get("output", {}).get("base_dir", "data")),
    "raw_html_path": Path(config.get("output", {}).get("base_dir", "data")) / "raw/interbank_millas.html",
    "parquet_path": Path(config.get("output", {}).get("base_dir", "data")) / "processed/tarjetas_interbank_millas.parquet",
    "avro_path": Path(config.get("output", {}).get("base_dir", "data")) / "processed/tarjetas_interbank_millas.avro",
    "log_path": Path("logs/scraper_interbank.log"),
    "timeout": 25,
    "pausa_min": 0.8,
    "pausa_max": 2.0,
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
def setup_driver(headless=False):
    """Configuración Cross-Browser (Brave/Chrome/Edge)"""
    try:
        opts = ChromeOptions()
        if headless: 
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--log-level=3")
        
        # Anti-detección de bot
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        
        # User-Agent realista
        if user_agents:
            ua = random.choice(user_agents)
            opts.add_argument(f"user-agent={ua}")
            log.info(f"User-Agent seleccionado: {ua}")
        
        # Intentar Brave primero
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe")
        ]
        for path in brave_paths:
            if os.path.exists(path):
                opts.binary_location = path
                break
                
        driver = webdriver.Chrome(options=opts)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        log.warning(f"Brave/Chrome falló. Iniciando Edge de respaldo... Error: {e}")
        opts_edge = EdgeOptions()
        if headless: 
            opts_edge.add_argument("--headless=new")
        opts_edge.add_argument("--no-sandbox")
        opts_edge.add_argument("--disable-dev-shm-usage")
        opts_edge.add_argument("--log-level=3")
        
        driver = webdriver.Edge(options=opts_edge)
        driver.implicitly_wait(5)
        return driver

def scroll_suave(driver, paso=600, pausa=0.5):
    """Realiza un scroll suave por la página para cargar contenido dinámico"""
    alto_pag = driver.execute_script('return document.body.scrollHeight')
    posicion_actual = 0
    
    while posicion_actual < alto_pag:
        posicion_actual += paso
        driver.execute_script(f'window.scrollTo(0, {posicion_actual});')
        time.sleep(pausa)
        alto_pag = driver.execute_script('return document.body.scrollHeight')

def esperar_y_clickear(driver, selector, by=By.CSS_SELECTOR, timeout=10):
    """Espera a que un elemento sea clickeable y hace clic"""
    try:
        wait = WebDriverWait(driver, timeout)
        elemento = wait.until(EC.element_to_be_clickable((by, selector)))
        elemento.click()
        return True
    except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
        return False

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

# ============================================================
# EXTRACCIÓN DE DATOS CON SELENIUM
# ============================================================
def extraer_datos_tarjetas(driver, url):
    """
    Extrae los datos de las tarjetas de Interbank usando Selenium
    
    Args:
        driver: Driver de Selenium
        url: URL de la página
    
    Returns:
        List[Dict]: Lista de diccionarios con los datos extraídos
    """
    log.info(f"Navegando a: {url}")
    driver.get(url)
    time.sleep(3)
    
    # Scroll para cargar todo el contenido dinámico
    scroll_suave(driver, paso=600, pausa=0.3)
    
    # Esperar a que cargue el contenido
    try:
        WebDriverWait(driver, CONFIG["timeout"]).until(
            EC.presence_of_element_located((By.CLASS_NAME, "o-account-categories__item"))
        )
    except TimeoutException:
        log.warning("⚠️ No se encontraron artículos, pero se continuará...")
    
    # Obtener el HTML
    html = driver.page_source
    
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
    CONFIG["output_dir"].mkdir(parents=True, exist_ok=True)
    CONFIG["raw_html_path"].parent.mkdir(parents=True, exist_ok=True)
    CONFIG["parquet_path"].parent.mkdir(parents=True, exist_ok=True)
    CONFIG["log_path"].parent.mkdir(parents=True, exist_ok=True)
    
    driver = None
    datos_completos = []
    
    try:
        # Configurar driver (headless=False para debugging, True para producción)
        driver = setup_driver(headless=False)
        
        # Extraer datos de cada URL
        for url in CONFIG["url_base"] if isinstance(CONFIG["url_base"], list) else [CONFIG["url_base"]]:
            datos = extraer_datos_tarjetas(driver, url)
            datos_completos.extend(datos)
            time.sleep(random.uniform(CONFIG["pausa_min"], CONFIG["pausa_max"]))
            
    except Exception as e:
        log.error(f"❌ Error en la extracción: {e}", exc_info=True)
        raise
    finally:
        if driver:
            log.info("Cerrando navegador INTERBANK...")
            driver.quit()
    
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
# EJECUCIÓN PRINCIPAL
# ============================================================
if __name__ == "__main__":
    try:
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