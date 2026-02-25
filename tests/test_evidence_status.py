# -*- coding: utf-8 -*-
"""
Tests para EvidenceStatus y extension de CampoExtraido
=======================================================
Verifica:
  - Backward compatibility: CampoExtraido sin nuevos campos funciona igual
  - EvidenceStatus enum: LEGIBLE, INCOMPLETO, ILEGIBLE
  - clasificar_status(): logica determinista de clasificacion
  - es_probatorio(): solo True si LEGIBLE
  - to_dict() / from_dict() con nuevos campos opcionales
  - bbox y motor_ocr como campos opcionales
"""

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion
from src.extraction.abstencion import (
    CampoExtraido,
    EvidenceStatus,
)


# ==============================================================================
# BACKWARD COMPATIBILITY
# ==============================================================================
class TestBackwardCompatibility:
    """CampoExtraido sin nuevos campos debe funcionar exactamente como antes."""

    def test_creacion_sin_nuevos_campos(self):
        """CampoExtraido se crea sin status, bbox ni motor_ocr."""
        campo = CampoExtraido(
            nombre_campo="ruc_proveedor",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
        )
        assert campo.nombre_campo == "ruc_proveedor"
        assert campo.valor == "20100039207"
        assert campo.status is None
        assert campo.bbox is None
        assert campo.motor_ocr == ""

    def test_es_abstencion_no_cambia(self):
        """es_abstencion() sigue funcionando igual."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor=None,
            archivo="test.pdf",
            pagina=0,
            confianza=0.0,
            metodo=MetodoExtraccion.OCR,
        )
        assert campo.es_abstencion() is True

    def test_es_abstencion_false_no_cambia(self):
        """Campo con valor no es abstencion."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
        )
        assert campo.es_abstencion() is False

    def test_to_dict_sin_nuevos_campos(self):
        """to_dict() sin nuevos campos no incluye status/bbox/motor_ocr."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
        )
        d = campo.to_dict()
        assert "status" not in d
        assert "bbox" not in d
        assert "motor_ocr" not in d
        assert d["nombre_campo"] == "ruc"
        assert d["es_abstencion"] is False

    def test_from_dict_sin_nuevos_campos(self):
        """from_dict() sin nuevos campos reconstruye correctamente."""
        data = {
            "nombre_campo": "monto",
            "valor": "250.00",
            "archivo": "test.pdf",
            "pagina": 5,
            "confianza": 0.88,
            "metodo": "OCR",
        }
        campo = CampoExtraido.from_dict(data)
        assert campo.nombre_campo == "monto"
        assert campo.status is None
        assert campo.bbox is None


# ==============================================================================
# EVIDENCE STATUS
# ==============================================================================
class TestEvidenceStatus:
    """Tests del enum EvidenceStatus."""

    def test_valores_enum(self):
        assert EvidenceStatus.LEGIBLE.value == "LEGIBLE"
        assert EvidenceStatus.INCOMPLETO.value == "INCOMPLETO"
        assert EvidenceStatus.ILEGIBLE.value == "ILEGIBLE"

    def test_from_string(self):
        assert EvidenceStatus("LEGIBLE") == EvidenceStatus.LEGIBLE
        assert EvidenceStatus("ILEGIBLE") == EvidenceStatus.ILEGIBLE

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            EvidenceStatus("INVENTADO")


# ==============================================================================
# CLASIFICAR STATUS
# ==============================================================================
class TestClasificarStatus:
    """Tests de clasificar_status() — logica determinista."""

    def test_valor_none_es_ilegible(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor=None,
            archivo="test.pdf",
            pagina=0,
            confianza=0.0,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.clasificar_status() == EvidenceStatus.ILEGIBLE

    def test_confianza_cero_es_ilegible(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.0,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.clasificar_status() == EvidenceStatus.ILEGIBLE

    def test_confianza_alta_ruc_es_legible(self):
        """RUC con confianza >= 0.90 es LEGIBLE."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.clasificar_status() == EvidenceStatus.LEGIBLE

    def test_confianza_media_ruc_es_incompleto(self):
        """RUC con confianza < 0.90 (umbral RUC) es INCOMPLETO."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.75,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.clasificar_status() == EvidenceStatus.INCOMPLETO

    def test_confianza_alta_texto_general_es_legible(self):
        """Texto general con confianza >= 0.70 es LEGIBLE."""
        campo = CampoExtraido(
            nombre_campo="descripcion",
            valor="COMPRA DE MATERIALES",
            archivo="test.pdf",
            pagina=1,
            confianza=0.75,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="texto_general",
        )
        assert campo.clasificar_status() == EvidenceStatus.LEGIBLE

    def test_confianza_baja_texto_general_es_incompleto(self):
        """Texto general con confianza < 0.70 es INCOMPLETO."""
        campo = CampoExtraido(
            nombre_campo="descripcion",
            valor="C0MPR4 D3...",
            archivo="test.pdf",
            pagina=1,
            confianza=0.55,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="texto_general",
        )
        assert campo.clasificar_status() == EvidenceStatus.INCOMPLETO

    def test_tipo_desconocido_usa_default(self):
        """Tipo de campo desconocido usa umbral default (0.75)."""
        campo = CampoExtraido(
            nombre_campo="campo_raro",
            valor="algo",
            archivo="test.pdf",
            pagina=1,
            confianza=0.80,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="desconocido",
        )
        assert campo.clasificar_status() == EvidenceStatus.LEGIBLE

    def test_en_el_umbral_exacto_es_legible(self):
        """Confianza exactamente en el umbral es LEGIBLE."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.90,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.clasificar_status() == EvidenceStatus.LEGIBLE


# ==============================================================================
# ES PROBATORIO
# ==============================================================================
class TestEsProbatorio:
    """Tests de es_probatorio() — solo LEGIBLE es probatorio."""

    def test_legible_es_probatorio(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.es_probatorio() is True

    def test_incompleto_no_es_probatorio(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.75,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.es_probatorio() is False

    def test_ilegible_no_es_probatorio(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor=None,
            archivo="test.pdf",
            pagina=0,
            confianza=0.0,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
        )
        assert campo.es_probatorio() is False

    def test_con_status_explicito_legible(self):
        """Si status ya esta asignado, usa ese directamente."""
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.50,  # Baja, pero status forzado
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
            status=EvidenceStatus.LEGIBLE,
        )
        assert campo.es_probatorio() is True

    def test_con_status_explicito_ilegible(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.99,
            metodo=MetodoExtraccion.OCR,
            tipo_campo="ruc",
            status=EvidenceStatus.ILEGIBLE,
        )
        assert campo.es_probatorio() is False


# ==============================================================================
# TO_DICT / FROM_DICT CON NUEVOS CAMPOS
# ==============================================================================
class TestSerializacionNuevosCampos:
    """Tests de to_dict/from_dict con status, bbox, motor_ocr."""

    def test_to_dict_con_status(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            status=EvidenceStatus.LEGIBLE,
        )
        d = campo.to_dict()
        assert d["status"] == "LEGIBLE"

    def test_to_dict_con_bbox(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            bbox=(10.0, 20.0, 300.0, 50.0),
        )
        d = campo.to_dict()
        assert d["bbox"] == [10.0, 20.0, 300.0, 50.0]

    def test_to_dict_con_motor_ocr(self):
        campo = CampoExtraido(
            nombre_campo="ruc",
            valor="20100039207",
            archivo="test.pdf",
            pagina=1,
            confianza=0.95,
            metodo=MetodoExtraccion.OCR,
            motor_ocr="paddleocr",
        )
        d = campo.to_dict()
        assert d["motor_ocr"] == "paddleocr"

    def test_from_dict_con_status(self):
        data = {
            "nombre_campo": "ruc",
            "valor": "20100039207",
            "archivo": "test.pdf",
            "pagina": 1,
            "confianza": 0.95,
            "metodo": "OCR",
            "status": "LEGIBLE",
        }
        campo = CampoExtraido.from_dict(data)
        assert campo.status == EvidenceStatus.LEGIBLE

    def test_from_dict_con_bbox_list(self):
        data = {
            "nombre_campo": "ruc",
            "valor": "20100039207",
            "archivo": "test.pdf",
            "pagina": 1,
            "confianza": 0.95,
            "metodo": "OCR",
            "bbox": [10.0, 20.0, 300.0, 50.0],
        }
        campo = CampoExtraido.from_dict(data)
        assert campo.bbox == (10.0, 20.0, 300.0, 50.0)
        assert isinstance(campo.bbox, tuple)

    def test_from_dict_status_invalido_es_none(self):
        data = {
            "nombre_campo": "ruc",
            "valor": "20100039207",
            "archivo": "test.pdf",
            "pagina": 1,
            "confianza": 0.95,
            "metodo": "OCR",
            "status": "INVENTADO",
        }
        campo = CampoExtraido.from_dict(data)
        assert campo.status is None

    def test_roundtrip_completo(self):
        """to_dict -> from_dict produce campo equivalente."""
        original = CampoExtraido(
            nombre_campo="monto",
            valor="250.00",
            archivo="factura.pdf",
            pagina=3,
            confianza=0.92,
            metodo=MetodoExtraccion.OCR,
            status=EvidenceStatus.LEGIBLE,
            bbox=(100.0, 200.0, 400.0, 220.0),
            motor_ocr="tesseract",
            snippet="Total: S/ 250.00",
            tipo_campo="monto",
        )
        d = original.to_dict()
        reconstruido = CampoExtraido.from_dict(d)
        assert reconstruido.nombre_campo == original.nombre_campo
        assert reconstruido.valor == original.valor
        assert reconstruido.status == original.status
        assert reconstruido.bbox == original.bbox
        assert reconstruido.motor_ocr == original.motor_ocr
