import sqlite3
import pandas as pd


class StarcuakDB:
    def __init__(self, ruta_base_datos="data/starcuak.db"):
        """Al crear el objeto, se asegura de que la tabla exista."""

        # Guardamos la ruta donde se creará el archivo de la base de datos
        self.ruta = ruta_base_datos
        # Al crear el objeto, llamamos automáticamente a la creación de la tabla
        self._crear_tabla_inicial()

    def _crear_tabla_inicial(self):
        """Crea la tabla 'Resenas' si es la primera vez que se corre el programa."""
        try:
            # 'with' asegura que la conexión se cierre sola al terminar
            with sqlite3.connect(self.ruta) as conexion:
                # El cursor es como un 'puntero' para escribir comandos SQL
                cursor = conexion.cursor()

                # Definimos las columnas o atributos de la tabla
                comando_sql = """
                    CREATE TABLE IF NOT EXISTS Resenas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        producto TEXT,
                        comentario TEXT,
                        sentimiento TEXT,
                        confianza REAL,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                cursor.execute(comando_sql)
                # 'commit' guarda los cambios permanentemente
                conexion.commit()
        except sqlite3.Error as error_db:
            print(f"Hubo un problema al crear la tabla: {error_db}")

    def insertar_resena(self, producto, comentario, sentimiento, confianza, fecha=None):
        """Recibe los datos de una reseña y los guarda en una fila nueva."""
        try:
            with sqlite3.connect(self.ruta) as conexion:
                cursor = conexion.cursor()

                # Usamos '?' para seguir los standards de seguridad
                query_insertar = """
                    INSERT INTO Resenas (producto, comentario, sentimiento, confianza, fecha) 
                    VALUES (?, ?, ?, ?, ?)
                """
                datos_a_guardar = (producto, comentario, sentimiento, confianza, fecha)

                cursor.execute(query_insertar, datos_a_guardar)
                conexion.commit()
        except sqlite3.Error as error_db:
            print(f"No se pudo guardar la reseña: {error_db}")

    def obtener_datos(self):
        """Trae toda la información guardada y la convierte en una tabla (DataFrame)"""
        with sqlite3.connect(self.ruta) as conexion:
            # Pandas lee el SQL y lo transforma directamente en un formato tabular
            return pd.read_sql("SELECT * FROM Resenas", conexion)

    def limpiar_datos(self):
        """Elimina todos los registros y reinicia los contadores de ID."""
        try:
            with sqlite3.connect(self.ruta) as conexion:
                cursor = conexion.cursor()
                # 1. Borramos todo el contenido de la tabla
                cursor.execute("DELETE FROM Resenas")
                # 2. Reiniciamos el contador de IDs para que empiece de 1 otra vez
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='Resenas'")
                conexion.commit()
        except sqlite3.Error as error_db:
            print(f"Error al vaciar la base de datos: {error_db}")
