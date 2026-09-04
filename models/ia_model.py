from transformers import pipeline


class AnalizadorIA:
    def __init__(self):
        """
        Al crear la clase, preparamos el motor de Inteligencia Artificial.
        """
        try:
            # Intentamos cargar 'BETO', que es un modelo experto en español
            nombre_modelo_experto = "finiteautomata/beto-sentiment-analysis"

            # El pipeline es una herramienta que hace todo el trabajo sucio:
            # Limpia el texto, lo traduce a números y predice el sentimiento
            self.motor_ia = pipeline("sentiment-analysis", model=nombre_modelo_experto)
            print("Motor de IA (BETO) cargado con éxito.")

        except Exception:
            # Si no hay internet o falla la descarga, usamos un motor por defecto 
            print("No se pudo cargar el modelo experto. Usando motor básico...")
            self.motor_ia = pipeline("sentiment-analysis")

    def analizar(self, texto_usuario):
        """
        Recibe un texto y nos dice si es POSITIVO, NEGATIVO o NEUTRAL.
        """
        # 1. Quitamos espacios vacíos al inicio y al final
        texto_limpio = texto_usuario.strip()

        # 2. Si el texto está vacío, no perdemos tiempo analizando
        if not texto_limpio:
            return "NEUTRAL", 0.0

        # 3. Le pedimos al motor que analice el texto.
        # El motor devuelve una lista con los resultados.
        lista_de_resultados = self.motor_ia(texto_limpio)

        # 4. Tomamos el primer resultado de la lista (el más importante)
        primer_resultado = lista_de_resultados[0]

        # 5. Extraemos la etiqueta (ej: 'POS') y el puntaje de confianza (ej: 0.99)
        etiqueta_sentimiento = primer_resultado["label"]
        puntaje_confianza = primer_resultado["score"]

        return etiqueta_sentimiento, puntaje_confianza
