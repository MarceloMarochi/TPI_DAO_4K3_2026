"""Casos de uso de catalogo del alcance simplificado."""
from __future__ import annotations

from app.negocio.comunes import validar_texto
from app.negocio.errores import Conflicto, NoEncontrado
from app.negocio.conversiones import _a_entero, _a_bool
from app.negocio.servicio_base import ServicioBase
from app.negocio.catalogo_stock import Producto, Sucursal, IngresoStock
from app.negocio.representaciones import _producto_a_dict, _sucursal_a_dict, _ingreso_a_dict

TIPOS_CATALOGO = ("proveedor", "sucursal", "producto")


class ServicioCatalogo(ServicioBase):
    def guardar_catalogo(self, tipo: str, datos: dict, alta: bool = True) -> dict:
        """Alta (alta=True) o edición de un proveedor, sucursal o producto. Los códigos no cambian."""
        with self._escritura():
            return self._guardar_catalogo(tipo, datos, alta)

    def _guardar_catalogo(self, tipo, datos, alta) -> dict:
        if tipo == "proveedor":
            return self._guardar_proveedor(datos, alta)
        if tipo == "sucursal":
            return self._guardar_sucursal(datos, alta)
        if tipo == "producto":
            return self._guardar_producto(datos, alta)
        raise ValueError(f"tipo: catálogo desconocido ({tipo}); opciones: {', '.join(TIPOS_CATALOGO)}")

    def _verificar_alta_o_edicion(self, existe: bool, alta: bool, descripcion: str) -> None:
        if alta and existe:
            raise Conflicto(f"Ya existe {descripcion}")
        if not alta and not existe:
            raise NoEncontrado(f"No existe {descripcion}")

    def _guardar_proveedor(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        nombre = validar_texto(datos.get("nombre"), "nombre")
        self._verificar_alta_o_edicion(codigo in self._proveedores, alta, f"el proveedor {codigo}")
        proveedor = {"codigo": codigo, "nombre": nombre}
        self._catalogo.guardar_proveedor(proveedor)
        self._proveedores[codigo] = proveedor
        return dict(proveedor)

    def _guardar_sucursal(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        existente = self._sucursales.get(codigo)
        self._verificar_alta_o_edicion(existente is not None, alta, f"el establecimiento {codigo}")
        if alta:
            es_cd = _a_bool(datos.get("es_cd", False), "es_cd")
            if es_cd and any(s.es_cd for s in self._sucursales.values()):
                raise Conflicto("Ya existe un Centro de Distribución; sólo puede haber uno")
            sucursal = Sucursal(codigo, datos.get("nombre"), es_cd)
        else:
            sucursal = existente
            if "es_cd" in datos and _a_bool(datos["es_cd"], "es_cd") != sucursal.es_cd:
                raise Conflicto("No se puede cambiar si un establecimiento es el CD")
            sucursal.nombre = datos.get("nombre")
        self._catalogo.guardar_sucursal(sucursal)
        self._sucursales[codigo] = sucursal
        return _sucursal_a_dict(sucursal)

    def _guardar_producto(self, datos, alta) -> dict:
        codigo = validar_texto(datos.get("codigo"), "codigo")
        existente = self._productos.get(codigo)
        self._verificar_alta_o_edicion(existente is not None, alta, f"el producto {codigo}")
        proveedor = self._validar_proveedor(datos.get("proveedor_codigo"))
        if alta:
            producto = Producto(codigo, datos.get("nombre"), datos.get("categoria"), proveedor,
                                datos.get("precio"), datos.get("costo_referencia"))
        else:
            producto = existente
            producto.nombre = datos.get("nombre")
            producto.categoria = datos.get("categoria")
            producto.proveedor_codigo = proveedor
            producto.precio = datos.get("precio")
            if datos.get("costo_referencia") is not None:
                producto.costo_referencia = datos["costo_referencia"]
        self._catalogo.guardar_producto(producto)
        self._productos[codigo] = producto
        return _producto_a_dict(producto)

    def configurar_minimo(self, sucursal_codigo: str, producto_codigo: str, minimo) -> dict:
        with self._escritura():
            return self._configurar_minimo(sucursal_codigo, producto_codigo, minimo)

    def _configurar_minimo(self, sucursal_codigo, producto_codigo, minimo) -> dict:
        sucursal = self._sucursal(sucursal_codigo)
        existencia = sucursal.existencia_para(self._producto(producto_codigo))
        existencia.minimo = _a_entero(minimo, "minimo")
        self._catalogo.guardar_existencias(sucursal)
        return {
            "sucursal_codigo": sucursal.codigo, "producto_codigo": existencia.producto.codigo,
            "disponible": existencia.cantidad, "minimo": existencia.minimo, "faltante": existencia.faltante(),
        }

    def registrar_ingreso(self, datos: dict) -> dict:
        with self._escritura():
            return self._registrar_ingreso(datos)

    def _registrar_ingreso(self, datos) -> dict:
        numero = validar_texto(datos.get("numero"), "numero")
        if self._catalogo.buscar_ingreso(numero, self._productos) is not None:
            raise Conflicto(f"Ya existe el ingreso {numero}")
        ingreso = IngresoStock(
            numero, self._producto(datos.get("producto_codigo")),
            self._validar_proveedor(datos.get("proveedor_codigo")),
            _a_entero(datos.get("cantidad"), "cantidad"), datos.get("costo_unitario"),
        )
        cd = self._cd()
        ingreso.aplicar(cd)
        self._catalogo.insertar_ingreso(ingreso)
        self._catalogo.guardar_producto(ingreso.producto)  # costo de referencia actualizado
        self._catalogo.guardar_existencias(cd)
        return _ingreso_a_dict(ingreso)

    def consultar_catalogo(self, tipo: str | None = None) -> dict | list:
        catalogos = self._catalogo.listar_catalogos()
        if tipo is None:
            return catalogos
        clave = {"proveedor": "proveedores", "sucursal": "sucursales", "producto": "productos"}.get(tipo)
        if clave is None:
            raise ValueError(f"tipo: catálogo desconocido ({tipo})")
        return catalogos[clave]

    def consultar_existencias(self, sucursal_codigo: str | None = None,
                              producto_codigo: str | None = None) -> list[dict]:
        return self._catalogo.consultar_existencias(sucursal_codigo, producto_codigo)

    def consultar_ingreso(self, numero: str) -> dict:
        self._cargar()
        ingreso = self._catalogo.buscar_ingreso(numero, self._productos)
        if ingreso is None:
            raise NoEncontrado(f"No existe el ingreso {numero}")
        return _ingreso_a_dict(ingreso)
