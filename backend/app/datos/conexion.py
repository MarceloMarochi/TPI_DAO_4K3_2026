"""Conexión SQLite compartida por los DAOs de una operación.

Se crea una conexión por solicitud. Los DAOs nunca hacen commit: la transacción
la abre y la cierra quien coordina el caso de uso (SistemaVentas) con:

    with conexion.transaccion():
        ...  # lecturas de stock y escrituras de varios DAOs

Si algo falla dentro del bloque, se revierte todo.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

RUTA_ESQUEMA = Path(__file__).with_name("schema.sql")


class ConexionSQLite:
    def __init__(self, ruta: str | Path):
        self._ruta = str(ruta)
        # isolation_level=None: el módulo no abre transacciones implícitas; las controlamos nosotros.
        # check_same_thread=False: FastAPI puede atender una misma solicitud desde otro hilo;
        # la conexión igual nunca se comparte entre solicitudes.
        self._conexion = sqlite3.connect(self._ruta, isolation_level=None, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.execute("PRAGMA foreign_keys = ON")
        self._conexion.execute("PRAGMA busy_timeout = 5000")
        self._en_transaccion = False

    @property
    def ruta(self) -> str:
        return self._ruta

    @property
    def en_transaccion(self) -> bool:
        return self._en_transaccion

    def crear_esquema(self) -> None:
        self._conexion.executescript(RUTA_ESQUEMA.read_text(encoding="utf-8"))

    @contextmanager
    def transaccion(self):
        """BEGIN IMMEDIATE toma el bloqueo de escritura antes de leer saldos (evita carreras)."""
        if self._en_transaccion:
            raise RuntimeError("Ya hay una transacción abierta en esta conexión")
        self._conexion.execute("BEGIN IMMEDIATE")
        self._en_transaccion = True
        try:
            yield self
        except BaseException:
            self._conexion.execute("ROLLBACK")
            raise
        else:
            self._conexion.execute("COMMIT")
        finally:
            self._en_transaccion = False

    def ejecutar(self, sql: str, parametros=()) -> sqlite3.Cursor:
        return self._conexion.execute(sql, parametros)

    def ejecutar_varios(self, sql: str, filas) -> None:
        self._conexion.executemany(sql, filas)

    def consultar(self, sql: str, parametros=()) -> list[sqlite3.Row]:
        return self._conexion.execute(sql, parametros).fetchall()

    def consultar_uno(self, sql: str, parametros=()) -> sqlite3.Row | None:
        return self._conexion.execute(sql, parametros).fetchone()

    def cerrar(self) -> None:
        self._conexion.close()

    def __enter__(self) -> ConexionSQLite:
        return self

    def __exit__(self, *excepcion) -> None:
        self.cerrar()
