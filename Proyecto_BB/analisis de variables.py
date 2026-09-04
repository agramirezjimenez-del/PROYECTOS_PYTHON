import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Leer el archivo CSV
df = pd.read_csv("ventas_hamburguesas_con_descuentos_proyectado.csv")

# 2. Analizar qué es lo que más se repite (Moda)
moda_categoria = df["categoria"].mode()[0]
moda_producto = df["producto"].mode()[0]
moda_canal = df["canal_venta"].mode()[0]
moda_pago = df["metodo_pago"].mode()[0]

print(f"\nLa categoría con más ventas es: {moda_categoria}")
print(f"El producto estrella es: {moda_producto}")
print(f"El canal de venta más utilizado es: {moda_canal}")
print(f"El método de pago más utilizado es: {moda_pago}")

# 3. Analizar el dinero que ingresa (Variable Numérica Continua)
media_monto = df["monto_total"].mean()
mediana_monto = df["monto_total"].median()

print(f"\nEl promedio de venta (Media): S/ {media_monto:.2f}")
print(f"El punto medio real (Mediana): S/ {mediana_monto:.2f}")

# 4. Obtener un resumen estadístico rápido (Rango, máximos, mínimos)
descripcion_numerica = df.describe()
print(descripcion_numerica)

# 5. Detección visual de Outliers (Gráfico de Cajas / Boxplot)
plt.figure(figsize=(10, 5)) # Ajustamos el tamaño de la figura
sns.boxplot(x=df['monto_total'], color='skyblue')

# Personalizamos el gráfico con títulos y etiquetas
plt.title('Distribución del Monto Total por Pedido (Detección de Outliers)')
plt.xlabel('Monto Total (S/)')

# Mostramos el gráfico en pantalla
plt.show()