import pandas as pd
from datetime import datetime


class FileManager:
    def leer_csv(self, ruta_del_archivo):
        """
        Lee un archivo CSV y lo convierte en una tabla de Pandas (DataFrame).
        """
        try:
            # Usamos varios parámetros para que la lectura sea robusta:
            # 1. sep=None: Le dice a Pandas 'adivina tú mismo si el separador es coma o punto y coma'.
            # 2. engine='python': Un motor más flexible para detectar el separador automáticamente.
            # 3. encoding='utf-8-sig': Especial para archivos de Excel; evita caracteres raros al inicio.

            tabla_datos = pd.read_csv(
                ruta_del_archivo, sep=None, engine="python", encoding="utf-8-sig"
            )
            return tabla_datos

        except Exception as error:
            print(f"Hubo un problema al leer el archivo: {error}")
            # Si falla, devolvemos una tabla vacía para que el programa no se detenga
            return pd.DataFrame()

    def registrar_log(self, mensaje_de_evento, ruta_log="data/outputs/log.txt"):
        """
        Escribe un mensaje en un archivo de texto, añadiendo la fecha y hora actual.
        """
        # 1. Obtenemos el momento exacto de la operación
        ahora = datetime.now()
        # 2. Le damos un formato legible: Año-Mes-Día Hora:Minuto:Segundo
        fecha_formateada = ahora.strftime("%Y-%m-%d %H:%M:%S")

        try:
            # 3. Abrimos el archivo en modo 'a' (Append).
            # Esto significa 'Añadir al final', para no borrar lo que ya estaba escrito.
            with open(ruta_log, "a") as archivo_texto:
                linea_a_escribir = f"[{fecha_formateada}] {mensaje_de_evento}\n"
                archivo_texto.write(linea_a_escribir)

        except Exception as error:
            print(f"Hubo un problema al escribir en el registro: {error}")
