import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os


# 0. FUNCIONES REUTILIZABLES

def graficar_barras(data, x, y, titulo, xlabel, ylabel, rotacion=30, color="#2a78d6"):
    plt.figure(figsize=(9, 4))
    plt.bar(data[x], data[y], color=color)
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=rotacion)
    plt.tight_layout()
    plt.show()

def graficar_linea(data, x, y, titulo, xlabel, ylabel, color="#2a78d6"):
    plt.figure(figsize=(8, 4))
    plt.plot(data[x], data[y], marker="o", color=color)
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.show()

def graficar_comparacion_linea(x_sin, y_sin, x_con, y_con, titulo, xlabel, ylabel):
    plt.figure(figsize=(9, 4))
    plt.plot(x_sin, y_sin, marker="o", linewidth=2, color="blue", label="Sin descuento")
    plt.plot(x_con, y_con, marker="s", linewidth=2, color="red", label="Con descuento (proyectado)")
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="-", linewidth=0.3, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()

def graficar_comparacion_barras(categorias, valores_sin, valores_con, titulo, xlabel, ylabel):
    x = np.arange(len(categorias))
    ancho = 0.35

    plt.figure(figsize=(9, 4))
    plt.bar(x - ancho / 2, valores_sin, width=ancho, label="Sin descuento", color="#898781")
    plt.bar(x + ancho / 2, valores_con, width=ancho, label="Con descuento (proyectado)", color="#2a78d6")
    plt.xticks(x, categorias, rotation=30)
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.tight_layout()
    plt.show()

def graficar_dispersion(data, x, y, titulo, xlabel, ylabel):
    plt.figure(figsize=(8, 5))
    sns.regplot(data=data, x=x, y=y, line_kws={"color": "black"})
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.show()


# 1. CARGAR LOS DATASETS (automático: coma o punto y coma)

ventas_sin_descuentos = pd.read_csv(
    "ventas_hamburguesas.csv",
    sep=None,
    engine="python",
    encoding="utf-8-sig"
)

ventas_con_descuentos = pd.read_csv(
    "ventas_hamburguesas_con_descuentos_proyectado.csv",
    sep=None,
    engine="python",
    encoding="utf-8-sig"
)

print("Columnas sin descuentos:", ventas_sin_descuentos.columns.tolist())
print("Columnas con descuentos:", ventas_con_descuentos.columns.tolist())


# 2. VALORES NULOS

print("\nNulos sin descuentos:")
print((ventas_sin_descuentos.isna().sum() / len(ventas_sin_descuentos) * 100).round(2))

print("\nNulos con descuentos:")
print((ventas_con_descuentos.isna().sum() / len(ventas_con_descuentos) * 100).round(2))


# 3. PREPARAR FECHA, HORA Y DÍA

for df in (ventas_sin_descuentos, ventas_con_descuentos):
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], format="mixed", dayfirst=True)
    df["hour"] = df["fecha_hora"].dt.hour
    df["weekday"] = df["fecha_hora"].dt.dayofweek
    df["weekday_name"] = df["fecha_hora"].dt.day_name()

col_revenue_con = "monto_total_proyectado" if "monto_total_proyectado" in ventas_con_descuentos.columns else "monto_total"


# 3.1 VARIABLE DERIVADA: pct_descuento


ventas_con_descuentos["pct_descuento"] = (
    ventas_con_descuentos["descuento_unitario"]
    / ventas_con_descuentos["precio_unitario"] * 100
)


# 3.2 ESTADÍSTICA DESCRIPTIVA

print("\nEstadística descriptiva - Ventas sin descuentos:")
print(ventas_sin_descuentos.describe().round(2))

print("\nEstadística descriptiva - Ventas con descuentos:")
print(ventas_con_descuentos.describe().round(2))


# 4. TRANSACCIONES POR HORA

trans_by_hour = (
    ventas_sin_descuentos.groupby("hour", as_index=False)
    .agg(transactions=("id_pedido", "count"))
    .sort_values("hour")
)

graficar_linea(
    trans_by_hour, "hour", "transactions",
    "Transacciones por hora", "Hora", "Número de transacciones"
)



# 5. REVENUE POR HORA — COMPARATIVO

rev_sin = (
    ventas_sin_descuentos.groupby("hour", as_index=False)
    .agg(revenue=("monto_total", "sum"))
)

rev_con = (
    ventas_con_descuentos.groupby("hour", as_index=False)
    .agg(revenue=(col_revenue_con, "sum"))
)

graficar_comparacion_linea(
    rev_sin["hour"], rev_sin["revenue"],
    rev_con["hour"], rev_con["revenue"],
    "Revenue por hora: Sin vs Con descuento",
    "Hora", "Revenue (S/.)"
)




# 6. PRECIO vs CANTIDAD (relación precio-demanda)

corr_precio_cantidad = ventas_con_descuentos["precio_unitario"].corr(
    ventas_con_descuentos["cantidad"]
)
print(f"\nCorrelación precio_unitario vs cantidad: {corr_precio_cantidad:.3f}")

graficar_dispersion(
    ventas_con_descuentos, "precio_unitario", "cantidad",
    "Precio unitario vs. Cantidad vendida",
    "Precio unitario (S/.)", "Cantidad vendida"
)


print("\nAnálisis completo.")

revenue_categoria = (
    ventas_con_descuentos
    .groupby("categoria", as_index=False)
    .agg(
        revenue=("monto_total", "sum"),
        unidades=("cantidad", "sum")
    )
    .sort_values("revenue", ascending=True)   # ascendente para que la barra más alta quede arriba en barh
)
print("\nRevenue por categoría:")
print(revenue_categoria)
 
colores_categoria = ["#B85042", "#97BC62", "#5b9bd5", "#2a78d6", "#1E2761"]
 
plt.figure(figsize=(9, 5))
 
plt.barh(
    revenue_categoria["categoria"],
    revenue_categoria["revenue"],
    color=colores_categoria
)
 
plt.grid(True, axis="x", alpha=0.3)
 
plt.title("Revenue total por categoría de producto", fontsize=17)
plt.xlabel("Revenue (S/)", fontsize=14)
plt.ylabel("Categoría", fontsize=14)
 
# 7. Mostrar valores al final de cada barra
for categoria, valor in zip(revenue_categoria["categoria"], revenue_categoria["revenue"]):
    plt.text(valor, categoria, f" S/{valor:,.0f}", va="center")
 
plt.tight_layout()
plt.show()
