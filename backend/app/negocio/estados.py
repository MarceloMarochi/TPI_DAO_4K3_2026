"""Patrón State: ciclo de vida del bulto.

    PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO → VERIFICADO
                                  │            │
                                  └────────────┴──→ RECHAZADO

Bulto (el contexto) delega cada operación en su estado actual. La clase base
rechaza todas las operaciones; cada estado concreto redefine sólo las que admite.
No hay if/elif por tipo de estado: el comportamiento lo decide el polimorfismo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.negocio.comunes import validar_texto
from app.negocio.errores import Conflicto

if TYPE_CHECKING:
    from app.negocio.bultos import Bulto


@dataclass(frozen=True)
class _Transicion:
    """Resultado sin efectos laterales; Bulto lo aplica como una sola operación."""

    nuevo: EstadoBulto
    motivo: str
    precinto: str | None = None
    intacto: bool | None = None
    acreditar: bool = False


class EstadoBulto(ABC):
    """Estado abstracto del bulto. Por defecto, ninguna operación está permitida."""

    @abstractmethod
    def nombre(self) -> str:
        """Código del estado, tal como se guarda en la base y viaja por la API."""

    @abstractmethod
    def permite_sucesor(self, nombre: str) -> bool:
        """Indica si se puede pasar de este estado al estado `nombre`."""

    def acciones_permitidas(self) -> list[str]:
        """Operaciones que admite el estado (la API las informa al frontend)."""
        return []

    def es_final(self) -> bool:
        return False

    def estado_remito(self) -> str:
        """El remito queda Pendiente hasta que el bulto termina verificado o rechazado."""
        return "PENDIENTE"

    # Operaciones del bulto: rechazadas por defecto.

    def precintar(self, bulto: Bulto, numero: str) -> _Transicion:
        self._rechazar("precintar")

    def despachar(self, bulto: Bulto) -> _Transicion:
        self._rechazar("despachar")

    def recibir(self, bulto: Bulto, intacto: bool, motivo: str = "") -> _Transicion:
        self._rechazar("recibir")

    def verificar(self, bulto: Bulto, conforme: bool, motivo: str = "") -> _Transicion:
        self._rechazar("verificar")

    def _rechazar(self, operacion: str) -> None:
        raise Conflicto(f"No se puede {operacion} un bulto en estado {self.nombre()}")

    def __eq__(self, otro) -> bool:
        return isinstance(otro, EstadoBulto) and otro.nombre() == self.nombre()

    def __hash__(self) -> int:
        return hash(self.nombre())

    def __repr__(self) -> str:
        return self.nombre()


class Preparado(EstadoBulto):
    """Contenido armado; el disponible del CD ya se descontó al preparar."""

    def nombre(self) -> str:
        return "PREPARADO"

    def permite_sucesor(self, nombre: str) -> bool:
        return nombre == "PRECINTADO"

    def acciones_permitidas(self) -> list[str]:
        return ["precintar"]

    def precintar(self, bulto: Bulto, numero: str) -> _Transicion:
        numero = validar_texto(numero, "numero de precinto")
        return _Transicion(Precintado(), f"Precinto {numero}", precinto=numero)


class Precintado(EstadoBulto):
    """Bulto cerrado con precinto, listo para salir del CD."""

    def nombre(self) -> str:
        return "PRECINTADO"

    def permite_sucesor(self, nombre: str) -> bool:
        return nombre == "EN_TRANSITO"

    def acciones_permitidas(self) -> list[str]:
        return ["despachar"]

    def despachar(self, bulto: Bulto) -> _Transicion:
        # No se vuelve a descontar el CD: ya se hizo al preparar.
        return _Transicion(EnTransito(), "Despachado desde el CD")


class EnTransito(EstadoBulto):
    """Viajando hacia el local. Al llegar se controla el precinto."""

    def nombre(self) -> str:
        return "EN_TRANSITO"

    def permite_sucesor(self, nombre: str) -> bool:
        return nombre in ("RECIBIDO", "RECHAZADO")

    def acciones_permitidas(self) -> list[str]:
        return ["recibir"]

    def recibir(self, bulto: Bulto, intacto: bool, motivo: str = "") -> _Transicion:
        if not isinstance(intacto, bool):
            raise ValueError("intacto: debe indicarse si el precinto llegó intacto")
        # Evaluar el precinto es una validación de datos; el estado siguiente
        # sigue siendo responsabilidad de este estado concreto.
        if intacto:
            return _Transicion(Recibido(), motivo.strip() if motivo else "Precinto intacto", intacto=True)
        else:
            motivo = validar_texto(motivo, "motivo del rechazo")
            return _Transicion(Rechazado(), motivo, intacto=False)


class Recibido(EstadoBulto):
    """En el local, pendiente de controlar remito y contenido. Todavía no se puede vender."""

    def nombre(self) -> str:
        return "RECIBIDO"

    def permite_sucesor(self, nombre: str) -> bool:
        return nombre in ("VERIFICADO", "RECHAZADO")

    def acciones_permitidas(self) -> list[str]:
        return ["verificar"]

    def verificar(self, bulto: Bulto, conforme: bool, motivo: str = "") -> _Transicion:
        if not isinstance(conforme, bool):
            raise ValueError("conforme: debe indicarse si el control fue conforme")
        if conforme:
            return _Transicion(Verificado(), motivo.strip() if motivo else "Remito y contenido conformes",
                               acreditar=True)
        else:
            motivo = validar_texto(motivo, "motivo del rechazo")
            return _Transicion(Rechazado(), motivo)


class Verificado(EstadoBulto):
    """Final. La mercadería ya está disponible para la venta en el local."""

    def nombre(self) -> str:
        return "VERIFICADO"

    def permite_sucesor(self, nombre: str) -> bool:
        return False

    def es_final(self) -> bool:
        return True

    def estado_remito(self) -> str:
        return "VERIFICADO"


class Rechazado(EstadoBulto):
    """Final. La mercadería queda fuera de venta; no vuelve sola al CD ni se da por perdida."""

    def nombre(self) -> str:
        return "RECHAZADO"

    def permite_sucesor(self, nombre: str) -> bool:
        return False

    def es_final(self) -> bool:
        return True

    def estado_remito(self) -> str:
        return "RECHAZADO"


# Registro para reconstruir el estado a partir del código guardado en la base.
ESTADOS_BULTO: dict[str, type[EstadoBulto]] = {
    clase().nombre(): clase
    for clase in (Preparado, Precintado, EnTransito, Recibido, Verificado, Rechazado)
}


def estado_desde_nombre(nombre: str) -> EstadoBulto:
    clase = ESTADOS_BULTO.get(nombre)
    if clase is None:
        raise ValueError(f"estado de bulto desconocido: {nombre}")
    return clase()
