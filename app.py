import os
from datetime import datetime
from models import StarcuakDB, AnalizadorIA, FileManager


def inicializar_entorno():
    """Crea las carpetas necesarias si no existen."""
    if not os.path.exists("data/inputs"):
        os.makedirs("data/inputs")

    if not os.path.exists("data/outputs"):
        os.makedirs("data/outputs")


def mostrar_menu():
    print("\n" + "=" * 40)
    print("      ☕ STARCUAK CLI ADMIN PRO")
    print("=" * 40)
    print("1. Analizar Reseña Manual")
    print("2. Carga Masiva desde CSV")
    print("3. Ver Historial de Base de Datos")
    print("4. Resumen Estadístico (Dashboard)")
    print("5. Vaciar Base de Datos")
    print("0. Salir")
    print("=" * 40)
    opcion = input("Seleccione una opción: ")
    return opcion


def main():
    inicializar_entorno()

    # Creamos las herramientas que vamos a usar
    db = StarcuakDB()
    ia = AnalizadorIA()
    fm = FileManager()

    while True:
        opcion = mostrar_menu()

        if opcion == "1":
            print("\n--- NUEVA RESEÑA ---")
            productos = ["Espresso", "Americano", "Latte", "Capuccino"]

            # Mostramos los productos de forma clara
            for i, p in enumerate(productos, 1):
                print(f"{i}. {p}")

            try:
                entrada_usuario = input("Seleccione producto (1-4): ")
                idx = int(entrada_usuario) - 1

                if idx >= 0 and idx < len(productos):
                    prod = productos[idx]
                else:
                    prod = "Café"
            except ValueError:
                prod = "Café"

            txt = input("\nComentario del cliente: ")

            # Procesamos con la IA
            label, score = ia.analizar(txt)
            ahora = datetime.now()
            fecha = ahora.strftime("%d/%m/%Y %H:%M")

            # Guardamos la información
            db.insertar_resena(prod, txt, label, score, fecha)
            fm.registrar_log(f"Manual: {prod} -> {label}")

            print(f"RESULTADO: [{label}] con {score:.2f} de confianza.")

        elif opcion == "2":
            print("\n--- CARGA MASIVA ---")
            nombre_archivo = input(
                "Nombre del archivo en data/inputs/ (ej: datos.csv): "
            )
            ruta = os.path.join("data/inputs", nombre_archivo)

            df = fm.leer_csv(ruta)

            if not df.empty and "comentario" in df.columns:
                total_filas = len(df)
                print(f"Procesando {total_filas} filas...")

                for indice, fila in df.iterrows():
                    comentario_texto = str(fila["comentario"])
                    label, score = ia.analizar(comentario_texto)

                    # Intentamos obtener el producto, si no existe usamos "Café"
                    producto_nombre = fila.get("producto", "Café")

                    db.insertar_resena(producto_nombre, comentario_texto, label, score)

                fm.registrar_log(f"Carga Masiva: {total_filas} registros.")
                print("Carga masiva completada con éxito.")
            else:
                print("Error: Columna 'comentario' no encontrada o archivo vacío.")

        elif opcion == "3":
            print("\n--- ÚLTIMOS REGISTROS ---")
            datos = db.obtener_datos()
            if not datos.empty:
                # Seleccionamos las columnas y las mostramos sin el índice extra de Pandas
                ultimas_diez = datos.tail(10)
                columnas_limpias = ultimas_diez[
                    ["id", "producto", "sentimiento", "confianza"]
                ]
                print(columnas_limpias.to_string(index=False))
            else:
                print("Base de datos vacía.")

        elif opcion == "4":
            print("\n--- RESUMEN EJECUTIVO ---")
            df = db.obtener_datos()

            if not df.empty:
                total = len(df)
                # Filtramos para contar solo los positivos
                solo_positivos = df[df["sentimiento"] == "POS"]
                cantidad_pos = len(solo_positivos)

                # Calculamos porcentajes y promedios
                efectividad = (cantidad_pos / total) * 100
                promedio_confianza = df["confianza"].mean()

                print(f"Total Reseñas: {total}")
                print(f"Efectividad Positiva: {efectividad:.1f}%")
                print(f"Confianza Promedio: {promedio_confianza:.2f}")

                print("\nResultados por Producto:")
                # Desglosamos el conteo por producto
                agrupado = df.groupby("producto")["sentimiento"]
                conteo_sentimientos = agrupado.value_counts()
                tabla_final = conteo_sentimientos.unstack().fillna(0)
                print(tabla_final)
            else:
                print("No hay datos para generar el resumen.")

        elif opcion == "5":
            conf = input("¿Está SEGURO de borrar todo? (s/n): ")
            if conf.lower() == "s":
                db.limpiar_datos()
                fm.registrar_log("Base de datos vaciada manualmente.")
                print(" Base de datos limpia.")

        elif opcion == "0":
            print("Cerrando sistema... ¡Buen día!")
            break
        else:
            print("Opción inválida, intente de nuevo.")


if __name__ == "__main__":
    main()
