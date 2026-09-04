import re
import json
import time
import random
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, List, Any
import pandas as pd
import numpy as np
import pandera as pa
from pandera import Column, Check

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException,
    StaleElementReferenceException, ElementNotInteractableException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager

from bs4 import BeautifulSoup

# ============================================================
# CARGA DE CONFIGURACIÓN
# ============================================================
def load_config(config_path: str = "config/config.json") -> Dict:
    """Carga la configuración desde un archivo JSON"""
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuración por defecto si no existe el archivo
        return {
            "bancos": {
                "INTERBANK": {
                    "Tarjeta de Crédito": {
                        "urls": ["https://interbank.pe/tarjetas/tarjetas-credito/millas-benefit"]
                    }
                }
            },
            "user-agents": {
                "ua": [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ]
            },
            "output": {
                "base_dir": "data"
            }
        }

config_global = load_config()

# Configuración específica de Interbank
urls_interbank = config_global["bancos"]["INTERBANK"]["Tarjeta de Crédito"]["urls"]
user_agents = config_global["user-agents"]["ua"]

# ============================================================
# CONFIGURACIÓN
# ============================================================
CONFIG = {
    "url_base": urls_interbank[0] if urls_interbank else "https://interbank.pe/tarjetas/tarjetas-credito/millas-benefit",
    "output_dir": Path(config_global["output"]["base_dir"]),
    "raw_html_path": Path(config_global["output"]["base_dir"]) / "raw/interbank_millas.html",
    "parquet_path": Path(config_global["output"]["base_dir"]) / "processed/tarjetas_interbank_millas.parquet",
    "avro_path": Path(config_global["output"]["base_dir"]) / "processed/tarjetas_interbank_millas.avro",
    "log_path": Path("logs/scraper_interbank.log"),
    "timeout": 25,
    "pausa_min": 0.8,
    "pausa_max": 2.0,
    "max_intentos": 3,
}

# Columnas ordenadas para el output final
COLUMNAS_ORDENADAS = [
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
# LOGGING
# ============================================================
def setup_logging() -> logging.Logger:
    """Configura el sistema de logging con formato consistente"""
    CONFIG["log_path"].parent.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("interbank_scraper")
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    file_handler = logging.FileHandler(CONFIG["log_path"], encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# ============================================================
# UTILIDADES
# ============================================================
def log_separador(logger: logging.Logger, titulo: Optional[str] = None) -> None:
    """Imprime un separador visual en los logs"""
    logger.info("=" * 70)
    if titulo:
        logger.info(titulo.center(70))
        logger.info("=" * 70)

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

# ============================================================
# SETUP DRIVER (Selenium)
# ============================================================
def setup_driver(headless: bool = True, window_size: str = '1920,1080') -> webdriver.Chrome:
    """
    Configura y retorna un driver de Chrome con opciones anti-detección
    
    Args:
        headless: Si se ejecuta en modo headless
        window_size: Tamaño de la ventana
    
    Returns:
        webdriver.Chrome: Driver configurado
    """
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={window_size}")
    
    # Anti-detección de bot
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    
    # User-Agent realista
    ua = random.choice(user_agents) if user_agents else CONFIG.get("user_agent", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    opts.add_argument(f"user-agent={ua}")
    
    # Silenciar logs innecesarios
    opts.add_argument("--log-level=3")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(5)
    
    return driver

def scroll_suave(driver: webdriver.Chrome, paso: int = 600, pausa: float = 0.5) -> None:
    """
    Realiza un scroll suave por la página para cargar contenido dinámico
    
    Args:
        driver: Driver de Selenium
        paso: Píxeles a desplazar en cada paso
        pausa: Pausa entre pasos
    """
    alto_pag = driver.execute_script('return document.body.scrollHeight')
    posicion_actual = 0
    
    while posicion_actual < alto_pag:
        posicion_actual += paso
        driver.execute_script(f'window.scrollTo(0, {posicion_actual});')
        time.sleep(pausa)
        alto_pag = driver.execute_script('return document.body.scrollHeight')

def esperar_y_clickear(driver: webdriver.Chrome, selector: str, by: By = By.CSS_SELECTOR, 
                        timeout: int = 10) -> bool:
    """
    Espera a que un elemento sea clickeable y hace clic
    
    Args:
        driver: Driver de Selenium
        selector: Selector del elemento
        by: Tipo de selector
        timeout: Tiempo de espera máximo
    
    Returns:
        bool: True si se hizo clic, False si no se encontró el elemento
    """
    try:
        wait = WebDriverWait(driver, timeout)
        elemento = wait.until(EC.element_to_be_clickable((by, selector)))
        elemento.click()
        return True
    except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
        return False

# ============================================================
# EXTRACCIÓN DE PÁGINA CON SELENIUM
# ============================================================
def fetch_page_with_selenium(
    url: str,
    logger: logging.Logger,
    max_intentos: int = 3,
    timeout: int = 25,
    headless: bool = True
) -> Tuple[Optional[str], Optional[webdriver.Chrome]]:
    """
    Obtiene el HTML de una página usando Selenium con reintentos
    
    Args:
        url: URL a scrapear
        logger: Logger para registro
        max_intentos: Número máximo de intentos
        timeout: Timeout de espera
        headless: Modo headless
    
    Returns:
        Tuple[Optional[str], Optional[webdriver.Chrome]]: (HTML, driver)
    """
    driver = None
    ultimo_error = None
    
    for intento in range(1, max_intentos + 1):
        try:
            logger.info(f"📡 Solicitando {url} (intento {intento}/{max_intentos})")
            
            if driver is None:
                driver = setup_driver(headless=headless)
            
            driver.get(url)
            logger.info(f"✅ Página cargada: {driver.current_url}")
            
            # Esperar a que la página cargue contenido
            time.sleep(random.uniform(CONFIG["pausa_min"], CONFIG["pausa_max"]))
            
            # Scroll para cargar contenido dinámico
            scroll_suave(driver, paso=600, pausa=0.3)
            
            # Esperar a que aparezca el contenido principal
            try:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
            except TimeoutException:
                # Intentar con otro selector
                try:
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "o-account-categories__item"))
                    )
                except TimeoutException:
                    logger.warning("⚠️ No se encontraron artículos, pero se continuará...")
            
            html = driver.page_source
            
            # Guardar HTML crudo
            CONFIG["raw_html_path"].write_text(html, encoding="utf-8")
            logger.info(f"💾 HTML crudo guardado en {CONFIG['raw_html_path']}")
            
            return html, driver
            
        except Exception as e:
            ultimo_error = e
            logger.warning(f"⚠️ Error en intento {intento}/{max_intentos}: {e}")
            
            if driver is not None:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
            
            if intento < max_intentos:
                espera = 5 * intento
                logger.info(f"Reintentando en {espera}s...")
                time.sleep(espera)
    
    logger.error(f"❌ No se pudo obtener la página tras {max_intentos} intentos")
    if driver is not None:
        try:
            driver.quit()
        except:
            pass
    raise ultimo_error or RuntimeError("Fallo en todos los intentos")

# ============================================================
# PARSING DE HTML (Adaptado con BeautifulSoup)
# ============================================================
def parse(html: str, base_url: str, logger: logging.Logger) -> pd.DataFrame:
    """
    Parse el HTML y extrae los datos de las tarjetas
    
    Args:
        html: HTML de la página
        base_url: URL base para construir URLs completas
        logger: Logger para registro
    
    Returns:
        pd.DataFrame: DataFrame con los datos extraídos
    """
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
            logger.info(f"📂 Categorías detectadas: {list(categorias_tab.values())}")
        except Exception as e:
            logger.warning(f"No se pudo parsear data-tab-items: {e}")
    
    # Extraer artículos
    articulos = soup.find_all("article", class_="o-account-categories__item")
    total = len(articulos)
    logger.info(f"📄 Bloques de tarjeta encontrados (<article>): {total}")
    
    for i, art in enumerate(articulos, start=1):
        # Título
        h2 = art.find("h2", class_="o-account-categories__item__title")
        if not h2:
            logger.debug(f"Bloque [{i}/{total}] sin título, se omite")
            continue
        
        nombre = h2.get_text(strip=True)
        if not nombre:
            logger.debug(f"Bloque [{i}/{total}] con título vacío, se omite")
            continue
        
        logger.info(f"🔍 Procesando [{i}/{total}] {nombre}")
        
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
            url_detalle = base_url.rstrip("/") + "/" + url_detalle.lstrip("/")
        
        # Categoría
        tab_div = art.find_parent("div", id=True)
        tab_ref = tab_div["id"] if tab_div else None
        categoria = categorias_tab.get(tab_ref, tab_ref or "Sin categoría")
        
        # Validación: descartar si no tiene datos relevantes
        if membresia is None and millas_por_dolar is None:
            logger.info(f"  ⏭️ Descartada '{nombre}' (sin membresía ni millas)")
            continue
        
        datos.append({
            "nombre_tarjeta": nombre,
            "categoria": categoria,
            "membresia_anual_soles": membresia,
            "millas_por_dolar_consumo": millas_por_dolar,
            "bono_bienvenida_millas": bono_bienvenida or 0.0,
            "url_detalle": url_detalle,
            "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
            "fuente": base_url,
        })
        
        logger.info(f"  ✅ Extraída correctamente: {nombre}")
    
    logger.info(f"📊 Tarjetas extraídas: {len(datos)}/{total}")
    return pd.DataFrame(datos)

# ============================================================
# LIMPIEZA Y CALIDAD DE DATOS
# ============================================================
def diagnosticar_y_limpiar(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Diagnostica y limpia el DataFrame aplicando reglas de calidad
    """
    total_nulos = int(df.isna().sum().sum())
    duplicados = int(df.duplicated(subset=["nombre_tarjeta", "fecha_extraccion"]).sum())
    estado = "OK" if duplicados == 0 else "REVISAR"
    
    log_separador(logger, "CALIDAD DE DATOS")
    logger.info(f"📊 Registros      : {len(df)}")
    logger.info(f"📊 Columnas       : {df.shape[1]}")
    logger.info(f"📊 Duplicados     : {duplicados}")
    logger.info(f"📊 Valores nulos  : {total_nulos}")
    logger.info(f"📊 Estado         : {estado}")
    logger.info("=" * 70)
    
    # Copia para no modificar el original
    df_clean = df.copy()
    filas_antes = len(df_clean)
    
    # Limpieza de strings
    for col in ["nombre_tarjeta", "categoria", "url_detalle"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str).str.strip()
            df_clean[col] = df_clean[col].replace("nan", None)
    
    # Eliminar duplicados exactos
    df_clean = df_clean.drop_duplicates(subset=["nombre_tarjeta", "fecha_extraccion"])
    
    # Convertir columnas numéricas
    for col in ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")
    
    # Eliminar filas sin nombre de tarjeta
    df_clean = df_clean[df_clean["nombre_tarjeta"].notna() & (df_clean["nombre_tarjeta"] != "")]
    
    # Reemplazar nulos en columnas numéricas con 0
    num_cols = ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]
    for col in num_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna(0.0)
    
    filas_despues = len(df_clean)
    logger.info(
        f"🧹 Limpieza aplicada: {filas_antes - filas_despues} filas removidas "
        f"(duplicadas o sin nombre de tarjeta). Quedan {filas_despues} filas."
    )
    
    return df_clean.reset_index(drop=True)

# ============================================================
# ENRIQUECIMIENTO DE DATOS
# ============================================================
def enrich(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Enriquece el DataFrame con columnas sintéticas y cálculos financieros
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
    
    logger.info(f"📈 Enriquecimiento completado")
    logger.info(f"   - Segmentos: {df_enriched['segmento_gasto'].value_counts().to_dict()}")
    logger.info(f"   - Valor promedio de millas anuales: S/ {df_enriched['valor_millas_anual_soles'].mean():.2f}")
    logger.info(f"   - Gasto mensual promedio estimado: S/ {df_enriched['gasto_mensual_estimado_soles'].mean():.2f}")
    
    return df_enriched

# ============================================================
# VALIDACIÓN CON PANDERA
# ============================================================
def validar_con_pandera(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Valida el DataFrame contra el esquema definido
    """
    try:
        df_validado = esquema_interbank.validate(df, lazy=True)
        logger.info("✅ Validación de Pandera superada con éxito para Interbank.")
        return df_validado
    except pa.errors.SchemaError as exc:
        logger.error(f"❌ Error de validación en Interbank: {exc}")
        if hasattr(exc, 'schema_errors'):
            for error in exc.schema_errors:
                logger.error(f"  - {error}")
        raise

def validate(df: pd.DataFrame, min_filas: int = 1) -> bool:
    """
    Validación simple del DataFrame antes de Pandera
    """
    errores = []
    
    if len(df) < min_filas:
        errores.append(f"Filas insuficientes: {len(df)} < {min_filas}")
    
    faltantes = [c for c in COLUMNAS_ORDENADAS if c not in df.columns]
    if faltantes:
        errores.append(f"Faltan columnas obligatorias: {faltantes}")
    
    if errores:
        for e in errores:
            logging.getLogger("interbank_scraper").warning(f"Validación: {e}")
        return False
    
    return True

# ============================================================
# PIPELINE PRINCIPAL
# ============================================================
def run_pipeline() -> Optional[pd.DataFrame]:
    """
    Ejecuta el pipeline completo de ETL para Interbank usando Selenium
    """
    logger = setup_logging()
    inicio = time.time()
    
    # Crear directorios
    setup_paths()
    
    log_separador(logger, "🚀 PIPELINE - CATÁLOGO TARJETAS INTERBANK (SELENIUM)")
    logger.info(f"📅 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🔗 URL: {CONFIG['url_base']}")
    
    driver = None
    
    try:
        # ===== ETAPA 1: EXTRACCIÓN CON SELENIUM =====
        log_separador(logger, "ETAPA 1 - EXTRACCIÓN DE DATOS CON SELENIUM")
        html, driver = fetch_page_with_selenium(
            CONFIG["url_base"],
            logger,
            max_intentos=CONFIG["max_intentos"],
            timeout=CONFIG["timeout"],
            headless=True
        )
        
        if html is None:
            logger.error("❌ No se pudo obtener el HTML de la página")
            return None
        
        # ===== ETAPA 2: PARSING =====
        log_separador(logger, "ETAPA 2 - PARSING DE HTML")
        df = parse(html, CONFIG["url_base"], logger)
        
        if df.empty:
            logger.error("❌ No se extrajeron datos. Pipeline detenido.")
            return None
        
        # ===== ETAPA 3: LIMPIEZA =====
        log_separador(logger, "ETAPA 3 - LIMPIEZA Y CALIDAD DE DATOS")
        df = diagnosticar_y_limpiar(df, logger)
        
        if df.empty:
            logger.error("❌ DataFrame vacío después de la limpieza.")
            return None
        
        # ===== ETAPA 4: ENRIQUECIMIENTO =====
        log_separador(logger, "ETAPA 4 - ENRIQUECIMIENTO DE DATOS")
        df = enrich(df, logger)
        
        # ===== ETAPA 5: VALIDACIÓN SIMPLE =====
        log_separador(logger, "ETAPA 5 - VALIDACIÓN DE DATOS")
        valido = validate(df, min_filas=1)
        logger.info(f"Estado de validación: {'OK' if valido else 'CON ADVERTENCIAS'}")
        
        # ===== ETAPA 6: VALIDACIÓN CON PANDERA =====
        try:
            df = validar_con_pandera(df, logger)
        except pa.errors.SchemaError as e:
            logger.error(f"❌ Error de validación Pandera: {e}")
            return None
        
        # ===== ETAPA 7: PERSISTENCIA =====
        log_separador(logger, "ETAPA 6 - PERSISTENCIA DE DATOS")
        
        # Guardar en Parquet
        df.to_parquet(CONFIG["parquet_path"], index=False)
        logger.info(f"💾 Datos guardados en Parquet: {CONFIG['parquet_path']}")
        
        # Guardar en Avro (opcional)
        try:
            import fastavro
            records = df.to_dict('records')
            schema = {
                "type": "record",
                "name": "TarjetaInterbank",
                "fields": [
                    {"name": col, "type": ["null", "string", "float", "int"]} 
                    for col in df.columns
                ]
            }
            with open(CONFIG["avro_path"], 'wb') as f:
                fastavro.writer(f, schema, records)
            logger.info(f"💾 Datos guardados en Avro: {CONFIG['avro_path']}")
        except ImportError:
            logger.warning("⚠️ Fastavro no instalado. Saltando guardado en Avro.")
        except Exception as e:
            logger.warning(f"⚠️ Error guardando en Avro: {e}")
        
        # ===== RESUMEN FINAL =====
        tiempo = time.time() - inicio
        log_separador(logger, "✅ PROCESO COMPLETADO")
        logger.info(f"📊 Tarjetas extraídas : {len(df)}")
        logger.info(f"📊 Columnas          : {df.shape[1]}")
        logger.info(f"⏱️  Tiempo total      : {tiempo:.1f}s")
        logger.info(f"📅 Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_separador(logger)
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error en pipeline: {e}", exc_info=True)
        return None
    
    finally:
        if driver is not None:
            try:
                driver.quit()
                logger.info("Driver cerrado correctamente")
            except Exception as e:
                logger.warning(f"Error al cerrar driver: {e}")

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
            
    except KeyboardInterrupt:
        print("\n⚠️ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")