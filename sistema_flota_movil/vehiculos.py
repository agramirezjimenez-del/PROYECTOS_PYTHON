class Vehiculo:
    def __init__(self, placa: str, precio_base: float):
        self._placa = placa
        self._precio_base = precio_base
    
    
    def precio_base(self):
        return self._precio_base
    

    def precio_base(self, valor: float):
        if valor >= 0:
            self._precio_base = valor
        else:
            raise ValueError("El precio base debe ser positivo")
    
    def calcular_alquiler(self, dias: int) -> float:
        return self._precio_base * dias


class Auto(Vehiculo):
    def __init__(self, placa: str, precio_base: float, puertas: int):
        super().__init__(placa, precio_base)
        self._puertas = puertas
    
    
    def puertas(self):
        return self._puertas
    
    def calcular_alquiler(self, dias: int) -> float:
        total = super().calcular_alquiler(dias)
        if self._puertas > 2:
            total += 10 * dias
        return total


class Moto(Vehiculo):
    def __init__(self, placa: str, precio_base: float, cilindrada: int):
        super().__init__(placa, precio_base)
        self._cilindrada = cilindrada
    
    
    def cilindrada(self):
        return self._cilindrada
    
    def calcular_alquiler(self, dias: int) -> float:
        total = super().calcular_alquiler(dias)
        if self._cilindrada > 250:
            total += 5
        return total