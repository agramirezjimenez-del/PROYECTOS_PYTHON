from vehiculos import Auto, Moto

def main():
    print("=== SISTEMA DE GESTIÓN DE FLOTA 'MÓVIL' ===\n")
    
    while True:
        tipo = input("¿Qué vehículo desea alquilar? (1=Auto, 2=Moto): ").strip()
        if tipo in ['1', '2']:
            break
        print("Error: Ingrese 1 para Auto o 2 para Moto\n")
    
    placa = input("Ingrese la placa del vehículo: ").strip()
    
    while True:
        try:
            precio_base = float(input("Ingrese el precio base por día (S/.): "))
            if precio_base > 0:
                break
            print("Error: El precio debe ser mayor a 0\n")
        except ValueError:
            print("Error: Ingrese un número válido\n")
    
    while True:
        try:
            dias = int(input("Ingrese los días de alquiler: "))
            if dias > 0:
                break
            print("Error: Los días deben ser mayores a 0\n")
        except ValueError:
            print("Error: Ingrese un número entero válido\n")
    
    if tipo == '1':
        while True:
            try:
                puertas = int(input("Ingrese el número de puertas del auto: "))
                if puertas > 0:
                    break
                print("Error: El número de puertas debe ser positivo\n")
            except ValueError:
                print("Error: Ingrese un número entero válido\n")
        
        vehiculo = Auto(placa, precio_base, puertas)
        tipo_nombre = "Auto"
        detalle_extra = f"Número de puertas: {puertas}"
        
    else:
        while True:
            try:
                cilindrada = int(input("Ingrese la cilindrada de la moto (cc): "))
                if cilindrada > 0:
                    break
                print("Error: La cilindrada debe ser positiva\n")
            except ValueError:
                print("Error: Ingrese un número entero válido\n")
        
        vehiculo = Moto(placa, precio_base, cilindrada)
        tipo_nombre = "Moto"
        detalle_extra = f"Cilindrada: {cilindrada}cc"
    
    total = vehiculo.calcular_alquiler(dias)
    
    print("\n" + "="*50)
    print("RESUMEN DEL ALQUILER")
    print("="*50)
    print(f"Tipo de vehículo: {tipo_nombre}")
    print(f"Placa: {vehiculo._placa}")
    print(f"Precio base por día: S/. {precio_base:.2f}")
    print(f"Días de alquiler: {dias}")
    print(detalle_extra)
    print("-"*50)
    print(f"TOTAL A PAGAR: S/. {total:.2f}")
    print("="*50)

if __name__ == "__main__":
    main()