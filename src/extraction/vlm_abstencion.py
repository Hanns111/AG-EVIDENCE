# -*- coding: utf-8 -*-
"""
Abstención Automática para Fallos VLM
=======================================
Tarea #25 del Plan de Desarrollo (Fase 3: Parseo Profundo)

Cuando Qwen3-VL falla (JSON corrupto tras retries, timeout, conexión),
el sistema DEBE abstenerse formalmente en vez de silenciar el error.

Dato Viáticos AI: 10-30% de respuestas VLM tienen JSON corrupto.
Con retry max 2, la tasa baja a ~5%. El resto → abstención formal.

Estrategia:
  1. QwenFallbackClient intenta extraer (retry max 2 + fallback model)
  2. Si falla → VLMAbstencionHandler genera abstención formal:
     - ComprobanteExtraido esqueleto con campos ILEGIBLE
     - Hallazgo automático para audit trail
     - Estadísticas de fallo por tipo
  3. El pipeline NUNCA pierde una página silenciosamente

Principios:
  - Art. 3 (Anti-alucinación): prefiere vacío honesto a dato inventado
  - Toda abstención genera hallazgo auditado con razón específica
  - Trazabilidad: TraceLogger recibe cada evento de fallo VLM

Uso:
    from src.extraction.vlm_abstencion import VLMAbstencionHandler

    handler = VLMAbstencionHandler()

    # Opción A: wrapper que intenta VLM y abstiene si falla
    comprobante = handler.extraer_o_abstener(
        client=qwen_client,
        image_b64="base64...",
        archivo="expediente.pdf",
        pagina=5,
    )
    # comprobante SIEMPRE tiene valor (nunca None)

    # Opción B: generar abstención directa
    comprobante = handler.generar_abstencion_vlm(
        archivo="expediente.pdf",
        pagina=5,
        razon="JSON corrupto tras 2 intentos",
    )

Versión: 1.0.0
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import MetodoExtraccion, NivelObservacion, Observacion
from src.extraction.abstencion import (
    AbstencionPolicy,
    CampoExtraido,
    EvidenceStatus,
)
from src.extraction.expediente_contract import (
    ClasificacionGasto,
    ComprobanteExtraido,
    CondicionesComerciales,
    DatosAdquirente,
    DatosComprobante,
    DatosEmisor,
    MetadatosExtraccion,
    TotalesTributos,
    ValidacionesAritmeticas,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_VLM_ABSTENCION = "1.0.0"

# Agente ID para trazabilidad
AGENTE_VLM_ABSTENCION = "VLM_ABSTENCION"


# ==============================================================================
# ENUMERACIONES
# ==============================================================================


class RazonFalloVLM(Enum):
    """Razones específicas por las que el VLM falló."""

    JSON_CORRUPTO = "json_corrupto"
    TIMEOUT = "timeout"
    CONEXION = "conexion"
    RESPUESTA_VACIA = "respuesta_vacia"
    MODELO_NO_DISPONIBLE = "modelo_no_disponible"
    ERROR_INESPERADO = "error_inesperado"
    IMAGEN_INVALIDA = "imagen_invalida"

    @classmethod
    def desde_error(cls, error_msg: str) -> "RazonFalloVLM":
        """Clasifica un mensaje de error en una razón tipada."""
        msg = error_msg.lower()
        if "json corrupto" in msg or "json" in msg:
            return cls.JSON_CORRUPTO
        if "timeout" in msg or "timed out" in msg:
            return cls.TIMEOUT
        if "connection" in msg or "conexion" in msg or "urlopen" in msg:
            return cls.CONEXION
        if "empty" in msg or "vacía" in msg or "vacia" in msg:
            return cls.RESPUESTA_VACIA
        if "not found" in msg or "no disponible" in msg:
            return cls.MODELO_NO_DISPONIBLE
        return cls.ERROR_INESPERADO


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class RegistroAbstencionVLM:
    """Registro de una abstención VLM para auditoría."""

    archivo: str
    pagina: int
    razon: RazonFalloVLM
    detalle_error: str
    timestamp: str = ""
    modelo_intentado: str = ""
    intentos_realizados: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archivo": self.archivo,
            "pagina": self.pagina,
            "razon": self.razon.value,
            "detalle_error": self.detalle_error,
            "timestamp": self.timestamp,
            "modelo_intentado": self.modelo_intentado,
            "intentos_realizados": self.intentos_realizados,
        }


@dataclass
class EstadisticasAbstencion:
    """Estadísticas agregadas de abstenciones VLM."""

    total_intentos: int = 0
    total_exitos: int = 0
    total_abstenciones: int = 0
    por_razon: Dict[str, int] = field(default_factory=dict)
    registros: List[RegistroAbstencionVLM] = field(default_factory=list)

    @property
    def tasa_fallo(self) -> float:
        """Porcentaje de fallos sobre total de intentos."""
        if self.total_intentos == 0:
            return 0.0
        return self.total_abstenciones / self.total_intentos

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_intentos": self.total_intentos,
            "total_exitos": self.total_exitos,
            "total_abstenciones": self.total_abstenciones,
            "tasa_fallo": round(self.tasa_fallo, 4),
            "por_razon": dict(self.por_razon),
            "registros": [r.to_dict() for r in self.registros],
        }


# ==============================================================================
# HANDLER PRINCIPAL
# ==============================================================================


class VLMAbstencionHandler:
    """
    Maneja abstenciones formales cuando el VLM falla.

    Principio: toda página enviada al VLM DEBE tener un resultado
    (ComprobanteExtraido con datos O ComprobanteExtraido con abstención).
    Nunca se pierde una página silenciosamente.
    """

    def __init__(self, trace_logger: Any = None):
        self.trace_logger = trace_logger
        self.stats = EstadisticasAbstencion()

    def extraer_o_abstener(
        self,
        client: Any,
        image_b64: str,
        archivo: str = "",
        pagina: int = 0,
    ) -> ComprobanteExtraido:
        """
        Intenta extraer un comprobante con el VLM.
        Si falla, genera abstención formal en vez de None.

        Args:
            client: QwenFallbackClient (duck typing).
            image_b64: Imagen en base64.
            archivo: Nombre del archivo fuente.
            pagina: Número de página (1-indexed).

        Returns:
            ComprobanteExtraido — siempre tiene valor, nunca None.
        """
        self.stats.total_intentos += 1

        try:
            resultado = client.extraer_comprobante(
                image_b64=image_b64,
                archivo=archivo,
                pagina=pagina,
            )
        except Exception as e:
            resultado = None
            error_msg = f"error_inesperado: {e}"
            self._log_warning(f"Excepción en VLM {archivo} pág {pagina}: {e}")
            return self._registrar_y_abstener(
                archivo=archivo,
                pagina=pagina,
                error_msg=error_msg,
                modelo=getattr(client, "model", "desconocido"),
            )

        if resultado is not None:
            self.stats.total_exitos += 1
            return resultado

        # VLM falló — abstención formal
        return self._registrar_y_abstener(
            archivo=archivo,
            pagina=pagina,
            error_msg="extraccion fallida tras retries y fallback",
            modelo=getattr(client, "model", "desconocido"),
        )

    def extraer_lote_o_abstener(
        self,
        client: Any,
        imagenes_b64: List[str],
        archivo: str = "",
        paginas: Optional[List[int]] = None,
    ) -> List[ComprobanteExtraido]:
        """
        Extrae comprobantes de un lote de imágenes.
        Cada página fallida genera abstención formal.

        Args:
            client: QwenFallbackClient.
            imagenes_b64: Lista de imágenes en base64.
            archivo: Nombre del archivo fuente.
            paginas: Números de página (1-indexed).

        Returns:
            Lista de ComprobanteExtraido (uno por página, nunca None).
        """
        if paginas is None:
            paginas = list(range(1, len(imagenes_b64) + 1))

        resultados = []
        for idx, img_b64 in enumerate(imagenes_b64):
            pag = paginas[idx] if idx < len(paginas) else idx + 1
            comp = self.extraer_o_abstener(
                client=client,
                image_b64=img_b64,
                archivo=archivo,
                pagina=pag,
            )
            resultados.append(comp)

        return resultados

    def generar_abstencion_vlm(
        self,
        archivo: str,
        pagina: int,
        razon: str,
        modelo: str = "",
    ) -> ComprobanteExtraido:
        """
        Genera un ComprobanteExtraido esqueleto con todos los campos en ILEGIBLE.

        Este es el "vacío honesto" — el comprobante existe pero no se pudo leer.

        Args:
            archivo: Nombre del archivo fuente.
            pagina: Número de página.
            razon: Razón textual del fallo.
            modelo: Modelo VLM que se intentó usar.

        Returns:
            ComprobanteExtraido con campos en abstención formal.
        """
        razon_tipada = RazonFalloVLM.desde_error(razon)

        def _campo_ilegible(nombre: str, tipo: str = "") -> CampoExtraido:
            return CampoExtraido(
                nombre_campo=nombre,
                valor=None,
                archivo=archivo,
                pagina=pagina,
                confianza=0.0,
                metodo=MetodoExtraccion.HEURISTICA,
                snippet=f"ABSTENCION VLM: {razon}",
                regla_aplicada="ABSTENCION",
                tipo_campo=tipo,
                status=EvidenceStatus.ILEGIBLE,
                motor_ocr=modelo or "vlm_fallido",
            )

        # Construir ComprobanteExtraido esqueleto con todos los campos en ILEGIBLE
        grupo_a = DatosEmisor(
            ruc_emisor=_campo_ilegible("ruc_emisor", "ruc"),
            razon_social=_campo_ilegible("razon_social", "texto"),
            nombre_comercial=_campo_ilegible("nombre_comercial", "texto"),
            direccion_emisor=_campo_ilegible("direccion_emisor", "texto"),
            ubigeo_emisor=_campo_ilegible("ubigeo_emisor", "texto"),
        )

        grupo_b = DatosComprobante(
            tipo_comprobante=_campo_ilegible("tipo_comprobante", "tipo"),
            serie=_campo_ilegible("serie", "serie"),
            numero=_campo_ilegible("numero", "numero"),
            fecha_emision=_campo_ilegible("fecha_emision", "fecha"),
            fecha_vencimiento=None,
            moneda=_campo_ilegible("moneda", "moneda"),
            forma_pago=None,
            es_electronico=None,
        )

        grupo_c = DatosAdquirente(
            ruc_adquirente=_campo_ilegible("ruc_adquirente", "ruc"),
            razon_social_adquirente=_campo_ilegible("razon_social_adquirente", "texto"),
            direccion_adquirente=None,
        )

        grupo_d = CondicionesComerciales(
            condicion_pago=None,
            guia_remision=None,
            orden_compra=None,
            observaciones=None,
        )

        grupo_f = TotalesTributos(
            subtotal=_campo_ilegible("subtotal", "monto"),
            igv_tasa=None,
            igv_monto=_campo_ilegible("igv_monto", "monto"),
            total_gravado=None,
            total_exonerado=None,
            total_inafecto=None,
            total_gratuito=None,
            otros_cargos=None,
            descuentos=None,
            importe_total=_campo_ilegible("importe_total", "monto"),
            monto_letras=None,
        )

        grupo_g = ClasificacionGasto(
            categoria_gasto=_campo_ilegible("categoria_gasto", "tipo"),
            subcategoria=None,
        )

        grupo_k = MetadatosExtraccion(
            pagina_origen=pagina,
            metodo_extraccion="vlm_abstencion",
            confianza_global="ilegible",
            campos_no_encontrados=["todos — abstención VLM"],
            timestamp_extraccion=datetime.now().isoformat(),
        )

        return ComprobanteExtraido(
            grupo_a=grupo_a,
            grupo_b=grupo_b,
            grupo_c=grupo_c,
            grupo_d=grupo_d,
            grupo_e=[],
            grupo_f=grupo_f,
            grupo_g=grupo_g,
            grupo_h=None,
            grupo_i=None,
            grupo_j=ValidacionesAritmeticas(),
            grupo_k=grupo_k,
        )

    def generar_hallazgo(
        self,
        archivo: str,
        pagina: int,
        razon: RazonFalloVLM,
        detalle: str = "",
    ) -> Observacion:
        """
        Genera un hallazgo formal de abstención VLM.

        Args:
            archivo: Nombre del archivo fuente.
            pagina: Número de página.
            razon: Razón tipada del fallo.
            detalle: Detalle adicional del error.

        Returns:
            Observacion con nivel MAYOR (fallo de extracción es significativo).
        """
        descripcion = f"Abstención VLM en {archivo} pág {pagina}: {razon.value}"
        if detalle:
            descripcion += f" — {detalle}"

        return Observacion(
            nivel=NivelObservacion.MAYOR,
            descripcion=descripcion,
            agente=AGENTE_VLM_ABSTENCION,
            accion_requerida="Revisión manual de página — VLM no pudo extraer datos",
            requiere_revision_humana=True,
            regla_aplicada=f"ABSTENCION_VLM_{razon.value.upper()}",
            evidencia=f"{archivo}:pág{pagina} — {razon.value}",
        )

    def get_estadisticas(self) -> EstadisticasAbstencion:
        """Retorna copia de las estadísticas actuales."""
        return self.stats

    def reset_estadisticas(self) -> None:
        """Reinicia las estadísticas."""
        self.stats = EstadisticasAbstencion()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _registrar_y_abstener(
        self,
        archivo: str,
        pagina: int,
        error_msg: str,
        modelo: str,
    ) -> ComprobanteExtraido:
        """Registra el fallo y genera abstención formal."""
        razon = RazonFalloVLM.desde_error(error_msg)

        # Registrar estadísticas
        self.stats.total_abstenciones += 1
        key = razon.value
        self.stats.por_razon[key] = self.stats.por_razon.get(key, 0) + 1

        # Crear registro de auditoría
        registro = RegistroAbstencionVLM(
            archivo=archivo,
            pagina=pagina,
            razon=razon,
            detalle_error=error_msg,
            modelo_intentado=modelo,
        )
        self.stats.registros.append(registro)

        # Log para trazabilidad
        self._log_abstencion(registro)

        # Generar ComprobanteExtraido en abstención
        return self.generar_abstencion_vlm(
            archivo=archivo,
            pagina=pagina,
            razon=error_msg,
            modelo=modelo,
        )

    def _log_abstencion(self, registro: RegistroAbstencionVLM) -> None:
        """Registra la abstención en logger y trace_logger."""
        msg = (
            f"Abstención VLM: {registro.archivo} pág {registro.pagina} — "
            f"{registro.razon.value}: {registro.detalle_error}"
        )
        logger.warning(msg)
        if self.trace_logger:
            try:
                self.trace_logger.warning(
                    msg,
                    agent_id=AGENTE_VLM_ABSTENCION,
                    operation="abstencion_vlm",
                )
            except Exception:
                pass

    def _log_warning(self, msg: str) -> None:
        logger.warning(msg)
        if self.trace_logger:
            try:
                self.trace_logger.warning(
                    msg,
                    agent_id=AGENTE_VLM_ABSTENCION,
                    operation="vlm_error",
                )
            except Exception:
                pass
