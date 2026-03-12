# -*- coding: utf-8 -*-
"""
Política de Conflicto OCR vs VLM
==================================
Tarea #24 del Plan de Desarrollo (Fase 3: Parseo Profundo)

Resuelve conflictos cuando OCR (PaddleOCR/Tesseract) y VLM (Qwen3-VL)
extraen el mismo campo con valores distintos.

Estrategia principal (ADR-009, Viáticos AI):
  PyMuPDF (texto digital) → PaddleOCR (escaneado) → Qwen-VL (fallback imagen)

Reglas de resolución:
  1. Si solo un motor extrajo → usar ese valor
  2. Si ambos coinciden → usar cualquiera (preferir mayor confianza)
  3. Si difieren → aplicar política por tipo de campo:
     - Campos numéricos (RUC, montos, serie): preferir OCR (más preciso en dígitos)
     - Campos de texto (razón social, dirección): preferir VLM (mejor comprensión)
     - Fechas: preferir OCR si formato estándar, VLM si texto libre
     - En caso de duda: marcar INCOMPLETO y sugerir revisión humana

Principios:
  - Nunca inventar un valor combinado (Art. 3: anti-alucinación)
  - Siempre registrar el conflicto para trazabilidad
  - El campo ganador conserva su confianza original, NO se infla
  - Los campos descartados se registran como alternativas

Uso:
    from src.extraction.conflict_policy import ConflictResolver

    resolver = ConflictResolver()
    ganador = resolver.resolver(campo_ocr, campo_vlm)

Versión: 1.0.0
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.extraction.abstencion import CampoExtraido, EvidenceStatus

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_CONFLICT_POLICY = "1.0.0"

# Motores OCR (deterministas, buenos con dígitos)
MOTORES_OCR = {"paddleocr_gpu", "paddleocr_cpu", "tesseract", "OCR", "PDF_TEXT", "pymupdf"}

# Motores VLM (heurísticos, buenos con contexto visual)
MOTORES_VLM = {"qwen_vl", "qwen3-vl:8b", "qwen2.5vl:7b", "HEURISTICA"}

# Campos donde OCR es preferido (dígitos, códigos, montos)
CAMPOS_PREFER_OCR = {
    "ruc",
    "ruc_emisor",
    "ruc_adquirente",
    "ruc_proveedor",
    "monto",
    "subtotal",
    "igv_monto",
    "importe_total",
    "total",
    "importe",
    "valor_unitario",
    "otros_cargos",
    "descuentos",
    "total_gravado",
    "total_exonerado",
    "total_inafecto",
    "serie",
    "numero",
    "serie_numero",
    "cantidad",
    "igv_tasa",
    "numero_noches",
}

# Campos donde VLM es preferido (texto, contexto visual)
CAMPOS_PREFER_VLM = {
    "razon_social",
    "nombre_comercial",
    "razon_social_adquirente",
    "direccion_emisor",
    "direccion_adquirente",
    "ubigeo_emisor",
    "descripcion",
    "observaciones",
    "nombre_huesped",
    "nombre_pasajero",
    "condicion_pago",
    "forma_pago",
    "categoria_gasto",
    "subcategoria",
    "origen",
    "destino",
    "monto_letras",
}


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class ConflictRecord:
    """Registro de un conflicto detectado entre motores."""

    nombre_campo: str
    valor_ocr: Optional[str]
    valor_vlm: Optional[str]
    confianza_ocr: float
    confianza_vlm: float
    motor_ocr: str
    motor_vlm: str
    ganador: str  # "ocr", "vlm", "ninguno"
    razon: str
    requiere_revision: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nombre_campo": self.nombre_campo,
            "valor_ocr": self.valor_ocr,
            "valor_vlm": self.valor_vlm,
            "confianza_ocr": self.confianza_ocr,
            "confianza_vlm": self.confianza_vlm,
            "motor_ocr": self.motor_ocr,
            "motor_vlm": self.motor_vlm,
            "ganador": self.ganador,
            "razon": self.razon,
            "requiere_revision": self.requiere_revision,
        }


@dataclass
class ResultadoResolucion:
    """Resultado de resolver un conflicto."""

    campo_ganador: Optional[CampoExtraido]
    campo_descartado: Optional[CampoExtraido] = None
    hubo_conflicto: bool = False
    registro: Optional[ConflictRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campo_ganador": self.campo_ganador.to_dict() if self.campo_ganador else None,
            "hubo_conflicto": self.hubo_conflicto,
            "registro": self.registro.to_dict() if self.registro else None,
        }


@dataclass
class ResumenConflictos:
    """Resumen de todos los conflictos en un expediente."""

    total_campos: int = 0
    conflictos: int = 0
    resueltos_ocr: int = 0
    resueltos_vlm: int = 0
    sin_resolver: int = 0
    registros: List[ConflictRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_campos": self.total_campos,
            "conflictos": self.conflictos,
            "resueltos_ocr": self.resueltos_ocr,
            "resueltos_vlm": self.resueltos_vlm,
            "sin_resolver": self.sin_resolver,
            "registros": [r.to_dict() for r in self.registros],
        }


# ==============================================================================
# RESOLVER DE CONFLICTOS
# ==============================================================================


class ConflictResolver:
    """
    Resuelve conflictos entre campos extraídos por OCR y VLM.

    Aplica reglas deterministas basadas en tipo de campo y confianza.
    Nunca inventa valores combinados.
    """

    def __init__(self, trace_logger: Any = None):
        self.trace_logger = trace_logger

    def _es_motor_ocr(self, campo: CampoExtraido) -> bool:
        """Determina si el campo fue extraído por un motor OCR."""
        motor = campo.motor_ocr.lower() if campo.motor_ocr else ""
        metodo = (
            campo.metodo.value.upper()
            if hasattr(campo.metodo, "value")
            else str(campo.metodo).upper()
        )
        return motor in MOTORES_OCR or metodo in {"OCR", "PDF_TEXT", "REGEX"}

    def _es_motor_vlm(self, campo: CampoExtraido) -> bool:
        """Determina si el campo fue extraído por un motor VLM."""
        motor = campo.motor_ocr.lower() if campo.motor_ocr else ""
        metodo = (
            campo.metodo.value.upper()
            if hasattr(campo.metodo, "value")
            else str(campo.metodo).upper()
        )
        return motor in MOTORES_VLM or metodo == "HEURISTICA" or "qwen" in motor

    def _valores_equivalentes(self, val1: Optional[str], val2: Optional[str]) -> bool:
        """Compara valores normalizados (ignora espacios extra, case)."""
        if val1 is None or val2 is None:
            return val1 is None and val2 is None
        v1 = " ".join(val1.strip().split()).upper()
        v2 = " ".join(val2.strip().split()).upper()
        return v1 == v2

    def resolver(
        self,
        campo_a: Optional[CampoExtraido],
        campo_b: Optional[CampoExtraido],
    ) -> ResultadoResolucion:
        """
        Resuelve el conflicto entre dos campos del mismo nombre.

        Args:
            campo_a: Primer campo (puede ser OCR o VLM).
            campo_b: Segundo campo (puede ser OCR o VLM).

        Returns:
            ResultadoResolucion con el campo ganador y registro del conflicto.
        """
        # Caso 1: Solo uno existe
        if campo_a is None and campo_b is None:
            return ResultadoResolucion(campo_ganador=None)
        if campo_a is None:
            return ResultadoResolucion(campo_ganador=campo_b)
        if campo_b is None:
            return ResultadoResolucion(campo_ganador=campo_a)

        # Caso 2: Ambos existen pero uno tiene valor None
        if campo_a.valor is None and campo_b.valor is not None:
            return ResultadoResolucion(campo_ganador=campo_b, campo_descartado=campo_a)
        if campo_b.valor is None and campo_a.valor is not None:
            return ResultadoResolucion(campo_ganador=campo_a, campo_descartado=campo_b)
        if campo_a.valor is None and campo_b.valor is None:
            # Ambos sin valor — preferir mayor confianza
            ganador = campo_a if campo_a.confianza >= campo_b.confianza else campo_b
            return ResultadoResolucion(campo_ganador=ganador)

        # Identificar quién es OCR y quién VLM
        a_es_ocr = self._es_motor_ocr(campo_a)
        b_es_ocr = self._es_motor_ocr(campo_b)
        a_es_vlm = self._es_motor_vlm(campo_a)
        b_es_vlm = self._es_motor_vlm(campo_b)

        campo_ocr = campo_a if a_es_ocr else (campo_b if b_es_ocr else None)
        campo_vlm = campo_a if a_es_vlm else (campo_b if b_es_vlm else None)

        # Si no podemos distinguir motores, usar confianza
        if campo_ocr is None and campo_vlm is None:
            ganador = campo_a if campo_a.confianza >= campo_b.confianza else campo_b
            descartado = campo_b if ganador is campo_a else campo_a
            return ResultadoResolucion(campo_ganador=ganador, campo_descartado=descartado)

        # Caso 3: Valores equivalentes — sin conflicto
        if self._valores_equivalentes(campo_a.valor, campo_b.valor):
            ganador = campo_a if campo_a.confianza >= campo_b.confianza else campo_b
            return ResultadoResolucion(campo_ganador=ganador)

        # Caso 4: Valores distintos — CONFLICTO
        nombre = campo_a.nombre_campo
        return self._resolver_conflicto(nombre, campo_ocr, campo_vlm, campo_a, campo_b)

    def _resolver_conflicto(
        self,
        nombre: str,
        campo_ocr: Optional[CampoExtraido],
        campo_vlm: Optional[CampoExtraido],
        campo_a: CampoExtraido,
        campo_b: CampoExtraido,
    ) -> ResultadoResolucion:
        """Aplica la política de resolución para un conflicto real."""
        nombre_lower = nombre.lower().strip()

        # Si no tenemos ambos motores diferenciados, usar confianza pura
        if campo_ocr is None or campo_vlm is None:
            ganador = campo_a if campo_a.confianza >= campo_b.confianza else campo_b
            descartado = campo_b if ganador is campo_a else campo_a
            record = ConflictRecord(
                nombre_campo=nombre,
                valor_ocr=campo_a.valor,
                valor_vlm=campo_b.valor,
                confianza_ocr=campo_a.confianza,
                confianza_vlm=campo_b.confianza,
                motor_ocr=campo_a.motor_ocr or "desconocido",
                motor_vlm=campo_b.motor_ocr or "desconocido",
                ganador="a" if ganador is campo_a else "b",
                razon="confianza_mayor (motores no diferenciados)",
            )
            self._log_conflicto(record)
            return ResultadoResolucion(
                campo_ganador=ganador,
                campo_descartado=descartado,
                hubo_conflicto=True,
                registro=record,
            )

        # Regla por tipo de campo
        if nombre_lower in CAMPOS_PREFER_OCR:
            ganador, descartado = campo_ocr, campo_vlm
            razon = "campo_numerico_prefer_ocr"
        elif nombre_lower in CAMPOS_PREFER_VLM:
            ganador, descartado = campo_vlm, campo_ocr
            razon = "campo_texto_prefer_vlm"
        else:
            # Campo no clasificado — usar confianza, con tie-break OCR
            if campo_ocr.confianza > campo_vlm.confianza:
                ganador, descartado = campo_ocr, campo_vlm
                razon = "confianza_mayor_ocr"
            elif campo_vlm.confianza > campo_ocr.confianza:
                ganador, descartado = campo_vlm, campo_ocr
                razon = "confianza_mayor_vlm"
            else:
                ganador, descartado = campo_ocr, campo_vlm
                razon = "empate_tiebreak_ocr"

        # Si la diferencia de confianza es muy grande a favor del descartado,
        # marcar como requiere revisión (el preferido tiene baja confianza)
        requiere_revision = descartado.confianza - ganador.confianza > 0.3

        record = ConflictRecord(
            nombre_campo=nombre,
            valor_ocr=campo_ocr.valor,
            valor_vlm=campo_vlm.valor,
            confianza_ocr=campo_ocr.confianza,
            confianza_vlm=campo_vlm.confianza,
            motor_ocr=campo_ocr.motor_ocr or "ocr",
            motor_vlm=campo_vlm.motor_ocr or "vlm",
            ganador="ocr" if ganador is campo_ocr else "vlm",
            razon=razon,
            requiere_revision=requiere_revision,
        )

        self._log_conflicto(record)

        return ResultadoResolucion(
            campo_ganador=ganador,
            campo_descartado=descartado,
            hubo_conflicto=True,
            registro=record,
        )

    def resolver_lote(
        self,
        campos_ocr: List[CampoExtraido],
        campos_vlm: List[CampoExtraido],
    ) -> tuple[List[CampoExtraido], ResumenConflictos]:
        """
        Resuelve conflictos para un lote de campos.

        Empareja por nombre_campo y resuelve cada par.

        Args:
            campos_ocr: Campos extraídos por OCR.
            campos_vlm: Campos extraídos por VLM.

        Returns:
            Tupla (campos_resueltos, resumen).
        """
        resumen = ResumenConflictos()

        # Indexar por nombre
        ocr_idx: Dict[str, CampoExtraido] = {c.nombre_campo: c for c in campos_ocr}
        vlm_idx: Dict[str, CampoExtraido] = {c.nombre_campo: c for c in campos_vlm}

        todos_nombres = set(ocr_idx.keys()) | set(vlm_idx.keys())
        resumen.total_campos = len(todos_nombres)

        campos_resueltos: List[CampoExtraido] = []

        for nombre in sorted(todos_nombres):
            campo_ocr = ocr_idx.get(nombre)
            campo_vlm = vlm_idx.get(nombre)

            resultado = self.resolver(campo_ocr, campo_vlm)

            if resultado.campo_ganador is not None:
                campos_resueltos.append(resultado.campo_ganador)

            if resultado.hubo_conflicto:
                resumen.conflictos += 1
                if resultado.registro:
                    resumen.registros.append(resultado.registro)
                    if resultado.registro.ganador == "ocr":
                        resumen.resueltos_ocr += 1
                    elif resultado.registro.ganador == "vlm":
                        resumen.resueltos_vlm += 1
                    else:
                        resumen.sin_resolver += 1

        return campos_resueltos, resumen

    def _log_conflicto(self, record: ConflictRecord) -> None:
        """Registra un conflicto para trazabilidad."""
        msg = (
            f"Conflicto {record.nombre_campo}: "
            f"OCR={record.valor_ocr!r} (conf={record.confianza_ocr:.2f}) vs "
            f"VLM={record.valor_vlm!r} (conf={record.confianza_vlm:.2f}) → "
            f"ganador={record.ganador} ({record.razon})"
        )
        logger.info(msg)
        if self.trace_logger:
            try:
                self.trace_logger.info(
                    msg, agent_id="CONFLICT_RESOLVER", operation="resolver_conflicto"
                )
            except Exception:
                pass
