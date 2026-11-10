"""Identificador estable para detalles persistidos."""
from app.negocio.comunes import validar_positivo


class _ConId:
    """Identificador numérico asignado por la base al guardar; se asigna una sola vez."""

    _id: int | None = None

    @property
    def id(self) -> int | None:
        return self._id

    def asignar_id(self, valor: int) -> None:
        if self._id is not None:
            raise ValueError("El identificador ya fue asignado")
        self._id = validar_positivo(valor, "id")
