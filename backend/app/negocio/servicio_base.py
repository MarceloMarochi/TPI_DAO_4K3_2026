"""Contexto por servicio y solicitud. Las escrituras leen dentro de la transacción."""
from contextlib import contextmanager
from app.datos.catalogo_dao import CatalogoDAO
from app.negocio.catalogo_stock import Producto, Sucursal
from app.negocio.comunes import validar_texto
from app.negocio.errores import Conflicto, NoEncontrado


class ServicioBase:
    def __init__(self, conexion):
        self._conexion = conexion
        self._catalogo = CatalogoDAO(conexion)
        self._productos = {}
        self._sucursales = {}
        self._proveedores = {}

    def _cargar(self) -> None:
        self._productos, self._sucursales = self._catalogo.cargar_catalogo()
        self._proveedores = {p["codigo"]: p for p in self._catalogo.listar_proveedores()}

    @contextmanager
    def _escritura(self):
        """Transacción + catálogo leído dentro de ella (nadie puede cambiar el stock mientras tanto)."""
        with self._conexion.transaccion():
            self._cargar()
            yield

    def _producto(self, codigo) -> Producto:
        producto = self._productos.get(codigo)
        if producto is None:
            raise NoEncontrado(f"No existe el producto {codigo}")
        return producto

    def _sucursal(self, codigo) -> Sucursal:
        sucursal = self._sucursales.get(codigo)
        if sucursal is None:
            raise NoEncontrado(f"No existe el establecimiento {codigo}")
        return sucursal

    def _cd(self) -> Sucursal:
        for sucursal in self._sucursales.values():
            if sucursal.es_cd:
                return sucursal
        raise Conflicto("Todavía no se registró el Centro de Distribución")

    def _validar_proveedor(self, codigo) -> str:
        codigo = validar_texto(codigo, "proveedor_codigo")
        if codigo not in self._proveedores:
            raise ValueError(f"proveedor_codigo: no existe el proveedor {codigo}")
        return codigo
