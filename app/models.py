from dataclasses import dataclass
from typing import Optional


@dataclass
class Socio:
    codigo: str
    nombre: str
    ahorro: float = 0.0
    saldo: float = 0.0
    cupones: float = 0.0
    otros: float = 0.0
    ctahor: float = 0.0
    cta_cupon: float = 0.0
    ctapres: float = 0.0
    ap: str = "P"
    estado: str = "ACTIVO"
    cuenta: Optional[str] = None
    observ: Optional[str] = None


@dataclass
class Movimiento:
    clave: str
    codigo: str
    nombre: str
    fecha: str
    cantidad: float
    saldo: float
    cuotas: int = 0
    valcuota: float = 0.0
    cheque: str = ""
    fiador: str = ""
    fiador2: str = ""
    cupom_num: str = ""
