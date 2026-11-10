"""Representaciones de objetos ya calculados; sin consultas ni escrituras."""
from app.negocio.modelos import Producto, Sucursal, IngresoStock, Bulto, Devolucion

def _producto_a_dict(p: Producto) -> dict:
    return {
        "codigo": p.codigo, "nombre": p.nombre, "categoria": p.categoria,
        "proveedor_codigo": p.proveedor_codigo, "precio": p.precio, "costo_referencia": p.costo_referencia,
    }


def _sucursal_a_dict(s: Sucursal) -> dict:
    return {"codigo": s.codigo, "nombre": s.nombre, "es_cd": s.es_cd}


def _ingreso_a_dict(i: IngresoStock) -> dict:
    return {
        "numero": i.numero, "fecha": i.fecha, "producto_codigo": i.producto.codigo,
        "proveedor_codigo": i.proveedor_codigo, "cantidad": i.cantidad,
        "costo_unitario": i.costo_unitario, "importe": i.importe(),
    }


def _bulto_a_dict(b: Bulto) -> dict:
    return {
        "codigo": b.codigo, "orden_numero": b.orden.numero, "destino_codigo": b.destino.codigo,
        "remito_numero": b.remito_numero, "precinto_numero": b.precinto_numero,
        "precinto_intacto": b.precinto_intacto, "estado": b.estado.nombre(),
        "estado_remito": b.estado_remito(), "acciones_permitidas": b.acciones_permitidas(),
        "unidades": b.unidades(),
        "detalles": [
            {"detalle_id": d.pedido.id, "producto_codigo": d.producto.codigo,
             "producto_nombre": d.producto.nombre, "cantidad": d.cantidad}
            for d in b.detalles
        ],
        "historial": [
            {"secuencia": c.secuencia, "fecha": c.fecha, "anterior": c.anterior,
             "nuevo": c.nuevo, "motivo": c.motivo}
            for c in b.historial
        ],
    }


def _devolucion_a_dict(d: Devolucion) -> dict:
    return {
        "numero": d.numero, "fecha": d.fecha, "venta_numero": d.venta.numero, "detalle_id": d.detalle.id,
        "producto_codigo": d.detalle.producto.codigo, "cantidad": d.cantidad,
        "apta_reventa": d.apta_reventa, "motivo": d.motivo,
        "importe_reintegrado": d.importe_reintegrado, "medio_codigo": d.medio_codigo,
    }
