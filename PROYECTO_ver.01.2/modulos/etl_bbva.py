######### Librerías #########
# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
# Pandas, File y Tiempo
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

######### Rutas #########
with open("config/config.json", encoding="utf-8") as f:
    config = json.load(f)
    
# Ruta o rutas del producto financiero
urls_interbank = config["bancos"]["INTERBANK"]["Tarjeta de Crédito"]["urls"]
# Ruta de los User Agent
user_agents = config["user-agents"]["ua"]
# Ruta del Output
output = config["output"]["base_dir"]

######### ESQUEMA PANDERA (Validación de calidad) #########
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

######### Páginas y config inicial #########
CONFIG = {
    'url_inicio'  : urls_interbank[0] if urls_interbank else "https://interbank.pe/tarjetas/tarjetas-credito/millas-benefit",
    'timeout'     : 25,
    'pausa_min'   : 0.8,
    'pausa_max'   : 2.0,
    'directorio'  : output,
    'logs': 'logs',
    'max_intentos': 3,
}

######### Columnas numéricas finales #########
columnas_numericas = [
    "membresia_anual_soles",
    "millas_por_dolar_consumo",
    "bono_bienvenida_millas",
    "gasto_mensual_estimado_soles",
    "gasto_anual_estimado_soles",
    "valor_milla_soles",
    "millas_anuales_generadas",
    "valor_millas_anual_soles",
    "valor_bono_bienvenida_soles",
    "valor_neto_primer_anio_soles",
    "valor_neto_anual_recurrente_soles",
]

columnas_ordenadas = [
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

######### HELPERS #########
def setup_paths():
    os.makedirs(CONFIG['directorio'], exist_ok=True)
    os.makedirs(CONFIG['logs'], exist_ok=True)

def setup_driver(headless=True, window_size='1920,1080'):
    opts = Options()

    # Opciones esenciales
    if headless:
        opts.add_argument("--headless=new")       # nuevo modo headless (Chrome 112+)
    opts.add_argument("--no-sandbox")             # requerido en Linux/Docker
    opts.add_argument("--disable-dev-shm-usage")  # evita crashes por poca memoria
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={window_size}")

    # Anti-deteccion de bot
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # User-Agent realista
    ua = random.choice(user_agents) if user_agents else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    opts.add_argument(f"user-agent={ua}")
    log.info(f"User-Agent seleccionado: {ua}")

    # Silenciar logs innecesarios
    opts.add_argument("--log-level=3")

    # ChromeDriver automatico
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # Timeout implicito global: espera hasta N seg antes de NoSuchElement
    driver.implicitly_wait(5)
    return driver

def scroll_suave(driver, paso=600, pausa=0.3) -> None:
    """Realiza un scroll suave por la página para cargar contenido dinámico"""
    alto_pag = driver.execute_script('return document.body.scrollHeight')
    posicion_actual = 0

    while posicion_actual < alto_pag:
        posicion_actual += paso
        driver.execute_script(f'window.scrollTo(0, {posicion_actual});')
        time.sleep(pausa)

        alto_pag = driver.execute_script('return document.body.scrollHeight')

def clic_on_page(driver, wait: WebDriverWait, ByXPath: str = None, ByClassName: str = None, 
                 ByTagName: str = None, ByCSSSelector: str = None) -> None:
    """Realiza clic en un elemento de la página"""
    if ByXPath:
        ubicacion_elemento = driver.find_element(By.XPATH, ByXPath)
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            ubicacion_elemento
        )
        wait.until(EC.element_to_be_clickable((By.XPATH, ByXPath)))
        ubicacion_elemento.click()
        return
    
    if ByClassName:
        ubicacion_elemento = driver.find_element(By.CLASS_NAME, ByClassName)
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            ubicacion_elemento
        )
        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, ByClassName)))
        ubicacion_elemento.click()
        return
    
    if ByCSSSelector:
        ubicacion_elemento = driver.find_element(By.CSS_SELECTOR, ByCSSSelector)
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            ubicacion_elemento
        )
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ByCSSSelector)))
        ubicacion_elemento.click()
        return

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

######### FUNCIONES PARA CAPTURAR ESTADOS DE LA PÁGINA #########
def capture_states(driver, wait, url: str, max_reintentos: int = 3) -> dict:
    """Captura el estado de una página con reintentos"""
    for intento in range(1, max_reintentos + 1):
        try:
            log.info(f"📡 Cargando: {url} (intento {intento}/{max_reintentos})")
            driver.get(url)
            time.sleep(2)
            
            # Scroll para cargar contenido dinámico
            scroll_suave(driver, paso=600, pausa=0.3)
            
            # Esperar a que aparezca el contenido principal
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "o-account-categories__item")))
            except TimeoutException:
                # Intentar con otro selector
                try:
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
                except TimeoutException:
                    log.warning(f"⚠️ No se encontraron artículos en {url}")
            
            return {"url": url, "html": driver.page_source}
            
        except TimeoutException:
            espera = 2 ** intento   # 2, 4, 8 segundos
            log.warning(f"[{url}] Timeout en intento {intento}/{max_reintentos}, esperando {espera}s")
            time.sleep(espera)
        except Exception as e:
            log.warning(f"[{url}] Error en intento {intento}/{max_reintentos}: {e}")
            if intento < max_reintentos:
                time.sleep(2 ** intento)
    
    log.error(f"[{url}] Todos los reintentos fallaron")
    raise TimeoutException(f"No se pudo cargar {url} tras {max_reintentos} intentos")

######### FUNCIÓN PARA PARSEAR RESULTADOS #########
def parse(raw: dict) -> dict:
    """Parsea el HTML de una tarjeta Interbank"""
    url = raw['url']
    soup = BeautifulSoup(raw['html'], "lxml")
    
    # Fecha de extracción
    fecha_extraccion = datetime.now().isoformat(timespec="seconds")
    
    # Extraer categorías del data-tab-items (si existe)
    categorias_tab = {}
    cont_categorias = soup.find("div", class_="o-account-categories")
    if cont_categorias and cont_categorias.has_attr("data-tab-items"):
        try:
            categorias_tab = {
                c["ref"]: c.get("label", c["ref"])
                for c in json.loads(cont_categorias["data-tab-items"])
            }
        except Exception:
            pass
    
    # Buscar todos los artículos de tarjetas
    articulos = soup.find_all("article", class_="o-account-categories__item")
    resultados = []
    
    for art in articulos:
        # Título
        h2 = art.find("h2", class_="o-account-categories__item__title")
        if not h2:
            continue
        
        nombre_tarjeta = h2.get_text(strip=True)
        if not nombre_tarjeta:
            continue
        
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
            log.info(f"  ⏭️ Descartada '{nombre_tarjeta}' (sin membresía ni millas)")
            continue
        
        resultados.append({
            "nombre_tarjeta": nombre_tarjeta,
            "categoria": categoria,
            "membresia_anual_soles": membresia,
            "millas_por_dolar_consumo": millas_por_dolar,
            "bono_bienvenida_millas": bono_bienvenida or 0.0,
            "url_detalle": url_detalle,
            "fecha_extraccion": fecha_extraccion,
            "fuente": url,
        })
    
    return resultados

######### FUNCIONES DE ENRIQUECIMIENTO #########
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

######### FUNCIONES DE VALIDACIÓN #########
def validate(df: pd.DataFrame, min_filas: int = 1) -> bool:
    """Validación simple del DataFrame"""
    errores = []

    if len(df) < min_filas:
        errores.append(f"Filas insuficientes: {len(df)} < {min_filas}")

    faltantes = [c for c in columnas_ordenadas if c not in df.columns]
    if faltantes:
        errores.append(f"Faltan columnas obligatorias: {faltantes}")

    if errores:
        for e in errores:
            log.warning(f"Validación: {e}")
        return False

    log.info(f"Validación OK: {len(df)} filas, {len(df.columns)} columnas confirmadas.")
    return True

######### PIPELINE FINAL #########
def run():
    """Pipeline principal de extracción de Interbank"""
    # Pipeline
    setup_paths()
    # Inicio
    log.info('=' * 55)
    log.info(f'PIPELINE: EXTRACCIÓN DE TC')
    log.info(f'BANCO   : INTERBANK')
    log.info(f'URL     : {CONFIG["url_inicio"]}')
    log.info('=' * 55)

    t_inicio = time.time()
    stats = {'paginas_ok': 0, 'paginas_error': 0}

    # Config Driver
    driver = setup_driver(headless=True)
    wait = WebDriverWait(driver, timeout=CONFIG['timeout'])

    try:
        # Cargar la página principal
        log.info(f"Navegando a: {CONFIG['url_inicio']}")
        driver.get(CONFIG['url_inicio'])
        time.sleep(3)
        
        # Scroll para cargar todo el contenido
        scroll_suave(driver, paso=600, pausa=0.3)
        
        # Capturar el estado de la página
        raw = capture_states(driver, wait, CONFIG['url_inicio'])
        
        # Parsear los datos
        datos_tarjetas = parse(raw)
        stats['paginas_ok'] = 1
        
        t_total = time.time() - t_inicio
        log.info(f'Tiempo total   : {t_total:.1f}s')
        log.info(f'Paginas OK     : {stats["paginas_ok"]}')
        log.info(f'Paginas error  : {stats["paginas_error"]}')

        # Crear DataFrame
        df_final = pd.DataFrame(datos_tarjetas)
        
        if df_final.empty:
            df_final = pd.DataFrame(columns=columnas_ordenadas)
            log.error("No se extrajeron datos")
            return df_final
        else:
            # ============================================================
            # LIMPIEZA Y CALIDAD DE DATOS
            # ============================================================
            log.info("Aplicando limpieza y calidad de datos...")
            
            # Limpieza de strings
            for col in ["nombre_tarjeta", "categoria", "url_detalle"]:
                if col in df_final.columns:
                    df_final[col] = df_final[col].astype(str).str.strip()
                    df_final[col] = df_final[col].replace("nan", None)
            
            # Eliminar duplicados
            df_final = df_final.drop_duplicates(subset=["nombre_tarjeta", "fecha_extraccion"])
            
            # Convertir columnas numéricas
            for col in ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]:
                if col in df_final.columns:
                    df_final[col] = pd.to_numeric(df_final[col], errors="coerce")
            
            # Eliminar filas sin nombre de tarjeta
            df_final = df_final[df_final["nombre_tarjeta"].notna() & (df_final["nombre_tarjeta"] != "")]
            
            # Reemplazar nulos en columnas numéricas con 0
            for col in ["membresia_anual_soles", "millas_por_dolar_consumo", "bono_bienvenida_millas"]:
                if col in df_final.columns:
                    df_final[col] = df_final[col].fillna(0.0)
            
            log.info(f"🧹 Limpieza aplicada. Quedan {len(df_final)} filas.")
            
            # ============================================================
            # ENRIQUECIMIENTO Y NORMALIZACIÓN
            # ============================================================
            log.info("Aplicando reglas de negocio, Enriquecimiento y Normalización...")
            df_final = aplicar_enriquecimiento(df_final)
            
            # ============================================================
            # VALIDACIÓN CON PANDERA
            # ============================================================
            log.info("Ejecutando validación de calidad (Pandera)...")
            try:
                df_final = esquema_interbank.validate(df_final)
                log.info("✅ Validación de Pandera superada con éxito para INTERBANK.")
            except pa.errors.SchemaError as exc:
                log.error(f"❌ Error de validación en INTERBANK: {exc}")
                raise
            
            # ============================================================
            # PERSISTENCIA
            # ============================================================
            log.info("Guardando datos procesados...")
            
            # Guardar en Parquet
            parquet_path = Path(CONFIG['directorio']) / "processed/tarjetas_interbank_millas.parquet"
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            df_final.to_parquet(parquet_path, index=False)
            log.info(f"💾 Datos guardados en Parquet: {parquet_path}")
            
            # Guardar en CSV
            csv_path = Path(CONFIG['directorio']) / "processed/tarjetas_interbank_millas.csv"
            df_final.to_csv(csv_path, index=False, encoding='utf-8')
            log.info(f"💾 Datos guardados en CSV: {csv_path}")
            
            # ============================================================
            # VALIDACIÓN FINAL
            # ============================================================
            # Convertir columnas numéricas
            for col in columnas_numericas:
                if col in df_final.columns:
                    df_final[col] = pd.to_numeric(df_final[col], errors="coerce")
            
            df_final = df_final.replace({None: np.nan, "None": np.nan, "": np.nan})
            
            valido = validate(df_final, min_filas=1)
            
            log.info(f"Estado de validación: {'OK' if valido else 'CON ADVERTENCIAS'}")
            log.info("Se extrajeron correctamente los datos de INTERBANK")
            
            return df_final
            
    except Exception as e:
        log.exception(e)
        return pd.DataFrame()
    finally:
        driver.quit()
        log.info("Driver cerrado")

######### EJECUCIÓN PRINCIPAL #########
if __name__ == "__main__":
    try:
        df_resultado = run()
        
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