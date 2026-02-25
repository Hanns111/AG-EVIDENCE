# -*- coding: utf-8 -*-
"""
Contrato de Datos Tipado — ExpedienteJSON
==========================================
Tarea #17 del Plan de Desarrollo (Fase 2: Contrato + Router)

Define el formato JSON intermedio tipado entre el pipeline de extracción
(OCR + VLM + PyMuPDF) y los módulos consumidores (Excel, validaciones,
reportes). Este es el artefacto central que implementa:

  - Regla 1: Elimina necesidad de hardcode (todo viene del JSON)
  - Regla 3: Cada campo tiene valor o abstención, nunca inferencia
  - Regla 4: Contrato único de extracción con JSON obligatorio
  - Regla 5: Campos ILEGIBLE se marcan con AbstencionPolicy
  - Regla 6: Excel y reportes solo consumen ExpedienteJSON
  - Regla 7: Cada campo lleva fuente, página, confianza, motor

Estructura jerárquica:
  ExpedienteJSON
  ├── DatosAnexo3 (resumen de rendición)
  ├── List[ComprobanteExtraido] (comprobantes de pago)
  │   └── 11 Grupos (A-K) de PARSING_COMPROBANTES_SPEC.md
  ├── List[GastoDeclaracionJurada] (gastos sin comprobante)
  ├── List[BoletoTransporte] (boletos y boarding pass)
  ├── Optional[DocumentosConvenio] (expedientes Estado-Estado)
  ├── ResumenExtraccion (estadísticas)
  └── IntegridadExpediente (hash, custodia, status)

Cada campo individual es un CampoExtraido (abstencion.py) — NO un
string plano — garantizando fuente, página, confianza, bbox y motor.

Versión: 1.0.0
Fecha: 2026-02-19
"""

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# Asegurar que el directorio raíz del proyecto esté en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.extraction.abstencion import (
    CampoExtraido,
    EvidenceStatus,
)

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_CONTRATO = "1.0.0"
TOLERANCIA_ARITMETICA = 0.02  # ±0.02 soles


# ==============================================================================
# ENUMERACIONES ESPECÍFICAS DEL CONTRATO
# ==============================================================================


class TipoComprobante(Enum):
    """Tipos de comprobante de pago SUNAT."""

    FACTURA = "FACTURA"
    BOLETA = "BOLETA"
    NOTA_CREDITO = "NOTA_CREDITO"
    NOTA_DEBITO = "NOTA_DEBITO"
    RECIBO_HONORARIOS = "RECIBO_HONORARIOS"
    LIQUIDACION_COMPRA = "LIQUIDACION_COMPRA"
    TICKET = "TICKET"
    OTRO = "OTRO"


class CategoriaGasto(Enum):
    """Categorías de gasto para rendición de viáticos."""

    ALIMENTACION = "ALIMENTACION"
    HOSPEDAJE = "HOSPEDAJE"
    TRANSPORTE = "TRANSPORTE"
    MOVILIDAD_LOCAL = "MOVILIDAD_LOCAL"
    OTROS = "OTROS"


class MetodoExtraccionContrato(Enum):
    """Método de extracción en el contexto del contrato."""

    PYMUPDF = "pymupdf"
    PADDLEOCR_GPU = "paddleocr_gpu"
    PADDLEOCR_CPU = "paddleocr_cpu"
    TESSERACT = "tesseract"
    QWEN_VL = "qwen_vl"
    MANUAL = "manual"


class TipoBoleto(Enum):
    """Tipos de boleto de transporte."""

    AEREO = "AEREO"
    TERRESTRE = "TERRESTRE"
    BOARDING_PASS = "BOARDING_PASS"


class ConfianzaGlobal(Enum):
    """Nivel de confianza global de extracción."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class IntegridadStatus(Enum):
    """Estado de integridad del expediente."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ==============================================================================
# GRUPO A — Datos del Emisor
# ==============================================================================


@dataclass
class DatosEmisor:
    """
    Grupo A — Datos del emisor del comprobante.
    Cada campo es Optional[CampoExtraido] para soportar abstención.
    """

    ruc_emisor: Optional[CampoExtraido] = None
    razon_social: Optional[CampoExtraido] = None
    nombre_comercial: Optional[CampoExtraido] = None
    direccion_emisor: Optional[CampoExtraido] = None
    ubigeo_emisor: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v.to_dict() if v is not None else None
            for k, v in {
                "ruc_emisor": self.ruc_emisor,
                "razon_social": self.razon_social,
                "nombre_comercial": self.nombre_comercial,
                "direccion_emisor": self.direccion_emisor,
                "ubigeo_emisor": self.ubigeo_emisor,
            }.items()
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosEmisor":
        if not data:
            return cls()
        return cls(
            ruc_emisor=CampoExtraido.from_dict(data["ruc_emisor"])
            if data.get("ruc_emisor")
            else None,
            razon_social=CampoExtraido.from_dict(data["razon_social"])
            if data.get("razon_social")
            else None,
            nombre_comercial=CampoExtraido.from_dict(data["nombre_comercial"])
            if data.get("nombre_comercial")
            else None,
            direccion_emisor=CampoExtraido.from_dict(data["direccion_emisor"])
            if data.get("direccion_emisor")
            else None,
            ubigeo_emisor=CampoExtraido.from_dict(data["ubigeo_emisor"])
            if data.get("ubigeo_emisor")
            else None,
        )

    def campos_list(self) -> List[CampoExtraido]:
        """Retorna lista de campos no-None para evaluación."""
        return [
            v
            for v in [
                self.ruc_emisor,
                self.razon_social,
                self.nombre_comercial,
                self.direccion_emisor,
                self.ubigeo_emisor,
            ]
            if v is not None
        ]


# ==============================================================================
# GRUPO B — Datos del Comprobante
# ==============================================================================


@dataclass
class DatosComprobante:
    """Grupo B — Datos identificadores del comprobante."""

    tipo_comprobante: Optional[CampoExtraido] = None
    serie: Optional[CampoExtraido] = None
    numero: Optional[CampoExtraido] = None
    fecha_emision: Optional[CampoExtraido] = None
    fecha_vencimiento: Optional[CampoExtraido] = None
    moneda: Optional[CampoExtraido] = None
    forma_pago: Optional[CampoExtraido] = None
    es_electronico: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosComprobante":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO C — Datos del Adquirente
# ==============================================================================


@dataclass
class DatosAdquirente:
    """Grupo C — Datos del comprador/adquirente."""

    ruc_adquirente: Optional[CampoExtraido] = None
    razon_social_adquirente: Optional[CampoExtraido] = None
    direccion_adquirente: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosAdquirente":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO D — Condiciones Comerciales
# ==============================================================================


@dataclass
class CondicionesComerciales:
    """Grupo D — Condiciones comerciales del comprobante."""

    condicion_pago: Optional[CampoExtraido] = None
    guia_remision: Optional[CampoExtraido] = None
    orden_compra: Optional[CampoExtraido] = None
    observaciones: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "CondicionesComerciales":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO E — Detalle de Ítems
# ==============================================================================


@dataclass
class ItemDetalle:
    """Un ítem individual del comprobante (Grupo E)."""

    cantidad: Optional[CampoExtraido] = None
    unidad: Optional[CampoExtraido] = None
    descripcion: Optional[CampoExtraido] = None
    valor_unitario: Optional[CampoExtraido] = None
    importe: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ItemDetalle":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO F — Totales y Tributos
# ==============================================================================


@dataclass
class TotalesTributos:
    """Grupo F — Totales y tributos del comprobante."""

    subtotal: Optional[CampoExtraido] = None
    igv_tasa: Optional[CampoExtraido] = None
    igv_monto: Optional[CampoExtraido] = None
    total_gravado: Optional[CampoExtraido] = None
    total_exonerado: Optional[CampoExtraido] = None
    total_inafecto: Optional[CampoExtraido] = None
    total_gratuito: Optional[CampoExtraido] = None
    otros_cargos: Optional[CampoExtraido] = None
    descuentos: Optional[CampoExtraido] = None
    importe_total: Optional[CampoExtraido] = None
    monto_letras: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "TotalesTributos":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO G — Clasificación del Gasto
# ==============================================================================


@dataclass
class ClasificacionGasto:
    """Grupo G — Clasificación del gasto."""

    categoria_gasto: Optional[CampoExtraido] = None
    subcategoria: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ClasificacionGasto":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO H — Datos Específicos de Hospedaje
# ==============================================================================


@dataclass
class DatosHospedaje:
    """Grupo H — Datos específicos cuando el gasto es hospedaje."""

    fecha_checkin: Optional[CampoExtraido] = None
    fecha_checkout: Optional[CampoExtraido] = None
    numero_noches: Optional[CampoExtraido] = None
    numero_habitacion: Optional[CampoExtraido] = None
    nombre_huesped: Optional[CampoExtraido] = None
    numero_reserva: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosHospedaje":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO I — Datos Específicos de Movilidad
# ==============================================================================


@dataclass
class DatosMovilidad:
    """Grupo I — Datos específicos cuando el gasto es transporte/movilidad."""

    origen: Optional[CampoExtraido] = None
    destino: Optional[CampoExtraido] = None
    fecha_servicio: Optional[CampoExtraido] = None
    placa_vehiculo: Optional[CampoExtraido] = None
    nombre_pasajero: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosMovilidad":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [v for v in self.__dict__.values() if v is not None]


# ==============================================================================
# GRUPO J — Validaciones Aritméticas
# ==============================================================================


@dataclass
class ValidacionesAritmeticas:
    """
    Grupo J — Resultados de validaciones aritméticas.
    EJECUTA PYTHON, NO LA IA (Regla de Oro).
    """

    suma_items_ok: Optional[bool] = None
    igv_ok: Optional[bool] = None
    total_ok: Optional[bool] = None
    noches_ok: Optional[bool] = None
    tolerancia_usada: float = TOLERANCIA_ARITMETICA
    errores_detalle: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suma_items_ok": self.suma_items_ok,
            "igv_ok": self.igv_ok,
            "total_ok": self.total_ok,
            "noches_ok": self.noches_ok,
            "tolerancia_usada": self.tolerancia_usada,
            "errores_detalle": self.errores_detalle,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ValidacionesAritmeticas":
        if not data:
            return cls()
        return cls(
            suma_items_ok=data.get("suma_items_ok"),
            igv_ok=data.get("igv_ok"),
            total_ok=data.get("total_ok"),
            noches_ok=data.get("noches_ok"),
            tolerancia_usada=data.get("tolerancia_usada", TOLERANCIA_ARITMETICA),
            errores_detalle=data.get("errores_detalle", []),
        )

    def todas_ok(self) -> bool:
        """True si todas las validaciones ejecutadas pasaron."""
        checks = [
            v
            for v in [self.suma_items_ok, self.igv_ok, self.total_ok, self.noches_ok]
            if v is not None
        ]
        return all(checks) if checks else True


# ==============================================================================
# GRUPO K — Metadatos de Extracción
# ==============================================================================


@dataclass
class MetadatosExtraccion:
    """Grupo K — Metadatos del proceso de extracción."""

    pagina_origen: int = 0
    metodo_extraccion: str = ""
    confianza_global: str = "baja"
    campos_no_encontrados: List[str] = field(default_factory=list)
    timestamp_extraccion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pagina_origen": self.pagina_origen,
            "metodo_extraccion": self.metodo_extraccion,
            "confianza_global": self.confianza_global,
            "campos_no_encontrados": self.campos_no_encontrados,
            "timestamp_extraccion": self.timestamp_extraccion,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "MetadatosExtraccion":
        if not data:
            return cls()
        return cls(
            pagina_origen=data.get("pagina_origen", 0),
            metodo_extraccion=data.get("metodo_extraccion", ""),
            confianza_global=data.get("confianza_global", "baja"),
            campos_no_encontrados=data.get("campos_no_encontrados", []),
            timestamp_extraccion=data.get("timestamp_extraccion", ""),
        )


# ==============================================================================
# COMPROBANTE EXTRAÍDO — Estructura completa (Grupos A-K)
# ==============================================================================


@dataclass
class ComprobanteExtraido:
    """
    Un comprobante de pago completo con todos los 11 Grupos (A-K)
    de PARSING_COMPROBANTES_SPEC.md.
    """

    grupo_a: DatosEmisor = field(default_factory=DatosEmisor)
    grupo_b: DatosComprobante = field(default_factory=DatosComprobante)
    grupo_c: DatosAdquirente = field(default_factory=DatosAdquirente)
    grupo_d: CondicionesComerciales = field(default_factory=CondicionesComerciales)
    grupo_e: List[ItemDetalle] = field(default_factory=list)
    grupo_f: TotalesTributos = field(default_factory=TotalesTributos)
    grupo_g: ClasificacionGasto = field(default_factory=ClasificacionGasto)
    grupo_h: Optional[DatosHospedaje] = None
    grupo_i: Optional[DatosMovilidad] = None
    grupo_j: ValidacionesAritmeticas = field(default_factory=ValidacionesAritmeticas)
    grupo_k: MetadatosExtraccion = field(default_factory=MetadatosExtraccion)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grupo_a": self.grupo_a.to_dict(),
            "grupo_b": self.grupo_b.to_dict(),
            "grupo_c": self.grupo_c.to_dict(),
            "grupo_d": self.grupo_d.to_dict(),
            "grupo_e": [item.to_dict() for item in self.grupo_e],
            "grupo_f": self.grupo_f.to_dict(),
            "grupo_g": self.grupo_g.to_dict(),
            "grupo_h": self.grupo_h.to_dict() if self.grupo_h else None,
            "grupo_i": self.grupo_i.to_dict() if self.grupo_i else None,
            "grupo_j": self.grupo_j.to_dict(),
            "grupo_k": self.grupo_k.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ComprobanteExtraido":
        if not data:
            return cls()
        return cls(
            grupo_a=DatosEmisor.from_dict(data.get("grupo_a")),
            grupo_b=DatosComprobante.from_dict(data.get("grupo_b")),
            grupo_c=DatosAdquirente.from_dict(data.get("grupo_c")),
            grupo_d=CondicionesComerciales.from_dict(data.get("grupo_d")),
            grupo_e=[ItemDetalle.from_dict(i) for i in data.get("grupo_e", [])],
            grupo_f=TotalesTributos.from_dict(data.get("grupo_f")),
            grupo_g=ClasificacionGasto.from_dict(data.get("grupo_g")),
            grupo_h=DatosHospedaje.from_dict(data.get("grupo_h")) if data.get("grupo_h") else None,
            grupo_i=DatosMovilidad.from_dict(data.get("grupo_i")) if data.get("grupo_i") else None,
            grupo_j=ValidacionesAritmeticas.from_dict(data.get("grupo_j")),
            grupo_k=MetadatosExtraccion.from_dict(data.get("grupo_k")),
        )

    def todos_los_campos(self) -> List[CampoExtraido]:
        """Retorna todos los CampoExtraido del comprobante para evaluación."""
        campos = []
        campos.extend(self.grupo_a.campos_list())
        campos.extend(self.grupo_b.campos_list())
        campos.extend(self.grupo_c.campos_list())
        campos.extend(self.grupo_d.campos_list())
        for item in self.grupo_e:
            campos.extend(item.campos_list())
        campos.extend(self.grupo_f.campos_list())
        campos.extend(self.grupo_g.campos_list())
        if self.grupo_h:
            campos.extend(self.grupo_h.campos_list())
        if self.grupo_i:
            campos.extend(self.grupo_i.campos_list())
        return campos

    def get_serie_numero(self) -> str:
        """Retorna serie-número para identificación."""
        serie = self.grupo_b.serie.valor if self.grupo_b.serie else ""
        numero = self.grupo_b.numero.valor if self.grupo_b.numero else ""
        if serie and numero:
            return f"{serie}-{numero}"
        return serie or numero or "SIN_IDENTIFICAR"


# ==============================================================================
# GASTO DECLARACIÓN JURADA (DJ movilidad)
# ==============================================================================


@dataclass
class GastoDeclaracionJurada:
    """Un gasto sin comprobante (Declaración Jurada de movilidad)."""

    fecha: Optional[CampoExtraido] = None
    descripcion: Optional[CampoExtraido] = None
    monto: Optional[CampoExtraido] = None
    origen: Optional[CampoExtraido] = None
    destino: Optional[CampoExtraido] = None
    metadatos: MetadatosExtraccion = field(default_factory=MetadatosExtraccion)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fecha": self.fecha.to_dict() if self.fecha else None,
            "descripcion": self.descripcion.to_dict() if self.descripcion else None,
            "monto": self.monto.to_dict() if self.monto else None,
            "origen": self.origen.to_dict() if self.origen else None,
            "destino": self.destino.to_dict() if self.destino else None,
            "metadatos": self.metadatos.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "GastoDeclaracionJurada":
        if not data:
            return cls()
        return cls(
            fecha=CampoExtraido.from_dict(data["fecha"]) if data.get("fecha") else None,
            descripcion=CampoExtraido.from_dict(data["descripcion"])
            if data.get("descripcion")
            else None,
            monto=CampoExtraido.from_dict(data["monto"]) if data.get("monto") else None,
            origen=CampoExtraido.from_dict(data["origen"]) if data.get("origen") else None,
            destino=CampoExtraido.from_dict(data["destino"]) if data.get("destino") else None,
            metadatos=MetadatosExtraccion.from_dict(data.get("metadatos")),
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [
            v
            for v in [self.fecha, self.descripcion, self.monto, self.origen, self.destino]
            if v is not None
        ]


# ==============================================================================
# BOLETO DE TRANSPORTE
# ==============================================================================


@dataclass
class BoletoTransporte:
    """Un boleto de transporte o boarding pass."""

    tipo: Optional[CampoExtraido] = None  # AEREO, TERRESTRE, BOARDING_PASS
    empresa: Optional[CampoExtraido] = None
    ruta: Optional[CampoExtraido] = None  # origen-destino
    fecha: Optional[CampoExtraido] = None
    pasajero: Optional[CampoExtraido] = None
    numero_boleto: Optional[CampoExtraido] = None
    monto: Optional[CampoExtraido] = None
    metadatos: MetadatosExtraccion = field(default_factory=MetadatosExtraccion)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo.to_dict() if self.tipo else None,
            "empresa": self.empresa.to_dict() if self.empresa else None,
            "ruta": self.ruta.to_dict() if self.ruta else None,
            "fecha": self.fecha.to_dict() if self.fecha else None,
            "pasajero": self.pasajero.to_dict() if self.pasajero else None,
            "numero_boleto": self.numero_boleto.to_dict() if self.numero_boleto else None,
            "monto": self.monto.to_dict() if self.monto else None,
            "metadatos": self.metadatos.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "BoletoTransporte":
        if not data:
            return cls()
        return cls(
            tipo=CampoExtraido.from_dict(data["tipo"]) if data.get("tipo") else None,
            empresa=CampoExtraido.from_dict(data["empresa"]) if data.get("empresa") else None,
            ruta=CampoExtraido.from_dict(data["ruta"]) if data.get("ruta") else None,
            fecha=CampoExtraido.from_dict(data["fecha"]) if data.get("fecha") else None,
            pasajero=CampoExtraido.from_dict(data["pasajero"]) if data.get("pasajero") else None,
            numero_boleto=CampoExtraido.from_dict(data["numero_boleto"])
            if data.get("numero_boleto")
            else None,
            monto=CampoExtraido.from_dict(data["monto"]) if data.get("monto") else None,
            metadatos=MetadatosExtraccion.from_dict(data.get("metadatos")),
        )

    def campos_list(self) -> List[CampoExtraido]:
        return [
            v
            for v in [
                self.tipo,
                self.empresa,
                self.ruta,
                self.fecha,
                self.pasajero,
                self.numero_boleto,
                self.monto,
            ]
            if v is not None
        ]


# ==============================================================================
# DATOS DEL ANEXO 3 (Resumen de rendición)
# ==============================================================================


@dataclass
class ItemAnexo3:
    """Una línea del Anexo 3 (resumen de gasto)."""

    nro: Optional[CampoExtraido] = None
    fecha: Optional[CampoExtraido] = None
    tipo_documento: Optional[CampoExtraido] = None
    razon_social: Optional[CampoExtraido] = None
    numero_comprobante: Optional[CampoExtraido] = None
    concepto: Optional[CampoExtraido] = None
    importe: Optional[CampoExtraido] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() if v is not None else None for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ItemAnexo3":
        if not data:
            return cls()
        return cls(
            **{
                k: CampoExtraido.from_dict(v) if v else None
                for k, v in data.items()
                if k in cls.__dataclass_fields__
            }
        )


@dataclass
class DatosAnexo3:
    """Datos completos del Anexo 3 de rendición."""

    sinad: Optional[CampoExtraido] = None
    comisionado: Optional[CampoExtraido] = None
    dni: Optional[CampoExtraido] = None
    unidad_ejecutora: Optional[CampoExtraido] = None
    destino: Optional[CampoExtraido] = None
    fecha_salida: Optional[CampoExtraido] = None
    fecha_regreso: Optional[CampoExtraido] = None
    viatico_otorgado: Optional[CampoExtraido] = None
    total_gastado: Optional[CampoExtraido] = None
    devolucion: Optional[CampoExtraido] = None
    items: List[ItemAnexo3] = field(default_factory=list)
    metadatos: MetadatosExtraccion = field(default_factory=MetadatosExtraccion)

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for k, v in self.__dict__.items():
            if k == "items":
                result["items"] = [item.to_dict() for item in self.items]
            elif k == "metadatos":
                result["metadatos"] = self.metadatos.to_dict()
            elif isinstance(v, CampoExtraido):
                result[k] = v.to_dict()
            else:
                result[k] = v.to_dict() if v is not None and hasattr(v, "to_dict") else None
        return result

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DatosAnexo3":
        if not data:
            return cls()
        campo_fields = [
            "sinad",
            "comisionado",
            "dni",
            "unidad_ejecutora",
            "destino",
            "fecha_salida",
            "fecha_regreso",
            "viatico_otorgado",
            "total_gastado",
            "devolucion",
        ]
        kwargs = {}
        for f in campo_fields:
            kwargs[f] = CampoExtraido.from_dict(data[f]) if data.get(f) else None
        kwargs["items"] = [ItemAnexo3.from_dict(i) for i in data.get("items", [])]
        kwargs["metadatos"] = MetadatosExtraccion.from_dict(data.get("metadatos"))
        return cls(**kwargs)


# ==============================================================================
# DOCUMENTOS CONVENIO (expedientes Estado-Estado — Pautas 5.1.11)
# ==============================================================================


@dataclass
class DocumentosConvenio:
    """
    Documentos específicos de convenio interinstitucional.
    Ref: docs/CONVENIOS_INTERINSTITUCIONALES.md
    Identificador: GOV_RULE_CONVENIOS_INTERINSTITUCIONALES_v1
    """

    convenio_vigente: Optional[CampoExtraido] = None
    documento_cobranza: Optional[CampoExtraido] = None
    detalle_consumo: Optional[CampoExtraido] = None
    informe_tecnico: Optional[CampoExtraido] = None
    certificacion_presupuestal: Optional[CampoExtraido] = None
    derivacion_sinad: Optional[CampoExtraido] = None
    entidad_contraparte: Optional[CampoExtraido] = None
    periodo_convenio: Optional[CampoExtraido] = None
    # Calculados por reglas de negocio
    conformidad_funcional: bool = False
    coherencia_economica: bool = False

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for k, v in self.__dict__.items():
            if isinstance(v, bool):
                result[k] = v
            elif isinstance(v, CampoExtraido):
                result[k] = v.to_dict()
            else:
                result[k] = v.to_dict() if v is not None and hasattr(v, "to_dict") else None
        return result

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "DocumentosConvenio":
        if not data:
            return cls()
        campo_fields = [
            "convenio_vigente",
            "documento_cobranza",
            "detalle_consumo",
            "informe_tecnico",
            "certificacion_presupuestal",
            "derivacion_sinad",
            "entidad_contraparte",
            "periodo_convenio",
        ]
        kwargs = {}
        for f in campo_fields:
            kwargs[f] = CampoExtraido.from_dict(data[f]) if data.get(f) else None
        kwargs["conformidad_funcional"] = data.get("conformidad_funcional", False)
        kwargs["coherencia_economica"] = data.get("coherencia_economica", False)
        return cls(**kwargs)

    def documentos_minimos_presentes(self) -> bool:
        """Verifica los 6 documentos mínimos exigibles (Sección IV)."""
        return all(
            [
                self.convenio_vigente is not None,
                self.documento_cobranza is not None,
                self.detalle_consumo is not None,
                self.informe_tecnico is not None,
                self.certificacion_presupuestal is not None,
                self.derivacion_sinad is not None,
            ]
        )

    def apto_para_devengado(self) -> bool:
        """
        Determina si el expediente es apto para devengado.
        Requiere: 6 documentos mínimos + coherencia económica.
        """
        return self.documentos_minimos_presentes() and self.coherencia_economica


# ==============================================================================
# ARCHIVO FUENTE (con hash para cadena de custodia)
# ==============================================================================


@dataclass
class ArchivoFuente:
    """Un PDF fuente procesado con su hash SHA-256."""

    nombre: str = ""
    ruta_relativa: str = ""
    hash_sha256: str = ""
    tamaño_bytes: int = 0
    total_paginas: int = 0
    fecha_procesamiento: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "ruta_relativa": self.ruta_relativa,
            "hash_sha256": self.hash_sha256,
            "tamaño_bytes": self.tamaño_bytes,
            "total_paginas": self.total_paginas,
            "fecha_procesamiento": self.fecha_procesamiento,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ArchivoFuente":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==============================================================================
# RESUMEN DE EXTRACCIÓN
# ==============================================================================


@dataclass
class ResumenExtraccion:
    """Estadísticas de la extracción."""

    total_campos: int = 0
    campos_ok: int = 0
    campos_abstencion: int = 0
    campos_incompletos: int = 0
    tasa_extraccion: float = 0.0
    comprobantes_procesados: int = 0
    gastos_dj: int = 0
    boletos: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_campos": self.total_campos,
            "campos_ok": self.campos_ok,
            "campos_abstencion": self.campos_abstencion,
            "campos_incompletos": self.campos_incompletos,
            "tasa_extraccion": self.tasa_extraccion,
            "comprobantes_procesados": self.comprobantes_procesados,
            "gastos_dj": self.gastos_dj,
            "boletos": self.boletos,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "ResumenExtraccion":
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ==============================================================================
# INTEGRIDAD DEL EXPEDIENTE
# ==============================================================================


@dataclass
class IntegridadExpediente:
    """Estado de integridad del expediente procesado."""

    status: str = "OK"  # OK, WARNING, CRITICAL
    hash_expediente: str = ""  # SHA-256 del JSON serializado
    cadena_custodia_verificada: bool = False
    alertas: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "hash_expediente": self.hash_expediente,
            "cadena_custodia_verificada": self.cadena_custodia_verificada,
            "alertas": self.alertas,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "IntegridadExpediente":
        if not data:
            return cls()
        return cls(
            status=data.get("status", "OK"),
            hash_expediente=data.get("hash_expediente", ""),
            cadena_custodia_verificada=data.get("cadena_custodia_verificada", False),
            alertas=data.get("alertas", []),
        )


# ==============================================================================
# EXPEDIENTE JSON — Contrato completo
# ==============================================================================


@dataclass
class ExpedienteJSON:
    """
    Contrato de datos completo de un expediente.

    Este es el artefacto central del sistema — el JSON intermedio tipado
    entre extracción y consumo. Implementa Regla 4 de Gobernanza Técnica.

    Unicidad: Un ExpedienteJSON se identifica por su SINAD. No deben
    existir dos ExpedienteJSON con el mismo SINAD en el sistema.
    """

    # Identificadores
    sinad: str = ""
    naturaleza: str = ""  # NaturalezaExpediente.value
    categoria: str = ""  # VIATICOS, CAJA_CHICA, CONVENIO_INTERINSTITUCIONAL, etc.

    # Versión del contrato
    version_contrato: str = VERSION_CONTRATO
    extraido_por: str = ""
    timestamp_generacion: str = ""

    # Archivos fuente con hash
    archivos_fuente: List[ArchivoFuente] = field(default_factory=list)

    # Datos extraídos
    anexo3: Optional[DatosAnexo3] = None
    comprobantes: List[ComprobanteExtraido] = field(default_factory=list)
    declaracion_jurada: List[GastoDeclaracionJurada] = field(default_factory=list)
    boletos: List[BoletoTransporte] = field(default_factory=list)
    documentos_convenio: Optional[DocumentosConvenio] = None

    # Estadísticas y verificación
    resumen_extraccion: ResumenExtraccion = field(default_factory=ResumenExtraccion)
    integridad: IntegridadExpediente = field(default_factory=IntegridadExpediente)

    # ------------------------------------------------------------------
    # SERIALIZACIÓN
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para JSON."""
        return {
            "sinad": self.sinad,
            "naturaleza": self.naturaleza,
            "categoria": self.categoria,
            "version_contrato": self.version_contrato,
            "extraido_por": self.extraido_por,
            "timestamp_generacion": self.timestamp_generacion,
            "archivos_fuente": [a.to_dict() for a in self.archivos_fuente],
            "anexo3": self.anexo3.to_dict() if self.anexo3 else None,
            "comprobantes": [c.to_dict() for c in self.comprobantes],
            "declaracion_jurada": [dj.to_dict() for dj in self.declaracion_jurada],
            "boletos": [b.to_dict() for b in self.boletos],
            "documentos_convenio": self.documentos_convenio.to_dict()
            if self.documentos_convenio
            else None,
            "resumen_extraccion": self.resumen_extraccion.to_dict(),
            "integridad": self.integridad.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializa a JSON string con indentación y UTF-8."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpedienteJSON":
        """Reconstruye desde diccionario con validación."""
        return cls(
            sinad=data.get("sinad", ""),
            naturaleza=data.get("naturaleza", ""),
            categoria=data.get("categoria", ""),
            version_contrato=data.get("version_contrato", VERSION_CONTRATO),
            extraido_por=data.get("extraido_por", ""),
            timestamp_generacion=data.get("timestamp_generacion", ""),
            archivos_fuente=[ArchivoFuente.from_dict(a) for a in data.get("archivos_fuente", [])],
            anexo3=DatosAnexo3.from_dict(data.get("anexo3")) if data.get("anexo3") else None,
            comprobantes=[ComprobanteExtraido.from_dict(c) for c in data.get("comprobantes", [])],
            declaracion_jurada=[
                GastoDeclaracionJurada.from_dict(dj) for dj in data.get("declaracion_jurada", [])
            ],
            boletos=[BoletoTransporte.from_dict(b) for b in data.get("boletos", [])],
            documentos_convenio=DocumentosConvenio.from_dict(data.get("documentos_convenio"))
            if data.get("documentos_convenio")
            else None,
            resumen_extraccion=ResumenExtraccion.from_dict(data.get("resumen_extraccion")),
            integridad=IntegridadExpediente.from_dict(data.get("integridad")),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExpedienteJSON":
        """Reconstruye desde JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # VALIDACIÓN Y ESTADÍSTICAS
    # ------------------------------------------------------------------

    def generar_resumen(self) -> ResumenExtraccion:
        """Calcula estadísticas de extracción y actualiza resumen."""
        todos_los_campos = self._recolectar_todos_campos()

        total = len(todos_los_campos)
        ok = sum(1 for c in todos_los_campos if c.clasificar_status() == EvidenceStatus.LEGIBLE)
        abstencion = sum(1 for c in todos_los_campos if c.es_abstencion())
        incompletos = sum(
            1 for c in todos_los_campos if c.clasificar_status() == EvidenceStatus.INCOMPLETO
        )

        self.resumen_extraccion = ResumenExtraccion(
            total_campos=total,
            campos_ok=ok,
            campos_abstencion=abstencion,
            campos_incompletos=incompletos,
            tasa_extraccion=round(ok / total, 4) if total > 0 else 0.0,
            comprobantes_procesados=len(self.comprobantes),
            gastos_dj=len(self.declaracion_jurada),
            boletos=len(self.boletos),
        )
        return self.resumen_extraccion

    def generar_hash(self) -> str:
        """
        Genera hash SHA-256 del contenido del expediente.
        Excluye el campo hash_expediente para evitar recursión.
        """
        data = self.to_dict()
        data["integridad"]["hash_expediente"] = ""  # Excluir para cálculo
        contenido = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash_value = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        self.integridad.hash_expediente = hash_value
        return hash_value

    def validar_completitud(self) -> List[str]:
        """
        Verifica campos obligatorios vs encontrados.
        Retorna lista de problemas encontrados.
        """
        problemas = []

        if not self.sinad:
            problemas.append("SINAD vacío")
        if not self.naturaleza:
            problemas.append("Naturaleza no determinada")
        if not self.archivos_fuente:
            problemas.append("Sin archivos fuente registrados")
        if not self.comprobantes and not self.declaracion_jurada and not self.boletos:
            problemas.append("Sin datos extraídos (0 comprobantes, 0 DJ, 0 boletos)")

        # Verificar cada comprobante tiene mínimo serie/número
        for i, comp in enumerate(self.comprobantes):
            if not comp.grupo_b.serie and not comp.grupo_b.numero:
                problemas.append(f"Comprobante #{i + 1}: sin serie ni número")

        return problemas

    def get_campos_abstencion(self) -> List[CampoExtraido]:
        """Retorna todos los campos en abstención formal."""
        return [c for c in self._recolectar_todos_campos() if c.es_abstencion()]

    def get_campos_por_confianza(self, umbral: float) -> List[CampoExtraido]:
        """Filtra campos cuya confianza está bajo un umbral."""
        return [
            c
            for c in self._recolectar_todos_campos()
            if c.confianza < umbral and not c.es_abstencion()
        ]

    def verificar_unicidad_comprobantes(self) -> List[str]:
        """
        Verifica que no haya comprobantes duplicados.
        Clave de unicidad: serie-número.
        Retorna lista de duplicados encontrados.
        """
        vistos = {}
        duplicados = []
        for i, comp in enumerate(self.comprobantes):
            clave = comp.get_serie_numero()
            if clave in vistos and clave != "SIN_IDENTIFICAR":
                duplicados.append(
                    f"Comprobante duplicado: {clave} (posiciones {vistos[clave] + 1} y {i + 1})"
                )
            else:
                vistos[clave] = i
        return duplicados

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------

    def _recolectar_todos_campos(self) -> List[CampoExtraido]:
        """Recolecta todos los CampoExtraido del expediente."""
        campos = []

        # Comprobantes
        for comp in self.comprobantes:
            campos.extend(comp.todos_los_campos())

        # DJ
        for dj in self.declaracion_jurada:
            campos.extend(dj.campos_list())

        # Boletos
        for boleto in self.boletos:
            campos.extend(boleto.campos_list())

        return campos

    # ------------------------------------------------------------------
    # REPRESENTACIÓN
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ExpedienteJSON("
            f"sinad='{self.sinad}', "
            f"comprobantes={len(self.comprobantes)}, "
            f"dj={len(self.declaracion_jurada)}, "
            f"boletos={len(self.boletos)}, "
            f"version='{self.version_contrato}')"
        )
