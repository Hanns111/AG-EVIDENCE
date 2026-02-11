# -*- coding: utf-8 -*-
"""
Política Formal de Abstención Operativa
========================================
Tarea #12 del Plan de Desarrollo (Fase 1: Trazabilidad + OCR)

Implementa la regla cardinal del sistema (Artículo 3 de Gobernanza):
"Prefiere vacío honesto a dato inventado"

Cuando un campo no puede extraerse con suficiente confianza,
el sistema DEBE abstenerse formalmente en vez de inventar datos:
  - valor = None
  - confianza = 0.0
  - fuente = "ABSTENCION"
  - Genera hallazgo automático nivel INFORMATIVA
  - Excel: celda vacía + fondo ROJO + comentario

Mientras el TraceLogger (Tarea #11) registra qué pasó durante el
procesamiento, la Política de Abstención define qué hacer cuando
la extracción NO es confiable: parar y declararlo honestamente.

Principios:
  - Anti-alucinación: jamás inventar datos (Art. 3)
  - Trazabilidad: toda abstención genera hallazgo auditado
  - Configurabilidad: umbrales distintos por tipo de campo
  - Auditabilidad: registro completo en TraceLogger

Uso:
    from src.extraction.abstencion import AbstencionPolicy, CampoExtraido
    from config.settings import MetodoExtraccion

    policy = AbstencionPolicy()

    campo = CampoExtraido(
        nombre_campo="ruc_proveedor",
        valor="20123456789",
        archivo="expediente.pdf",
        pagina=3,
        confianza=0.55,
        metodo=MetodoExtraccion.OCR,
        snippet="RUC: 20123456789",
        tipo_campo="ruc",
    )

    resultado = policy.evaluar_campo(campo)
    if resultado.debe_abstenerse:
        print(f"Abstención: {resultado.razon_abstencion}")
        campo_final = policy.generar_campo_abstencion(
            nombre_campo="ruc_proveedor",
            razon=resultado.razon_abstencion,
        )
"""

import sys
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple

# Asegurar que el directorio raíz del proyecto esté en el path
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import (
    MetodoExtraccion,
    NivelObservacion,
    EvidenciaProbatoria,
    Observacion,
)


# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

# Fuente especial para campos en abstención
FUENTE_ABSTENCION = "ABSTENCION"

# Frase estándar de abstención según Artículo 12.1 de Gobernanza
FRASE_ABSTENCION_ESTANDAR = (
    "No consta información suficiente en los documentos revisados."
)


# ==============================================================================
# ENUMERACIONES
# ==============================================================================
class RazonAbstencion(Enum):
    """
    Razones formales por las cuales un campo entra en abstención.

    Cada razón tiene un código único que permite clasificar y
    analizar estadísticamente los patrones de abstención.
    """
    CONFIANZA_BAJA = "confianza_baja"
    VALOR_AUSENTE = "valor_ausente"
    SNIPPET_VACIO = "snippet_vacio"
    PAGINA_INVALIDA = "pagina_invalida"
    MULTIPLE_CONTRADICTORIO = "multiple_contradictorio"


# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class CampoExtraido:
    """
    Campo extraído de un documento con metadata completa.

    Este es el contrato fundamental para TODOS los módulos de extracción
    del sistema. Define qué información debe acompañar cada dato extraído
    para cumplir con el estándar probatorio (Art. 4 de Gobernanza).

    Un CampoExtraido puede estar en dos estados:
      - Extraído: valor no-None, confianza > 0
      - Abstención: valor=None, confianza=0.0, regla_aplicada="ABSTENCION"

    Attributes:
        nombre_campo: Identificador del campo (ej: "ruc_proveedor").
        valor: Valor extraído. None si abstención.
        archivo: Nombre del archivo fuente.
        pagina: Número de página (1-indexed). 0 si abstención.
        confianza: Nivel de confianza 0.0-1.0.
        metodo: Método de extracción usado.
        snippet: Contexto textual del documento (max 200 chars).
        regla_aplicada: ID de la regla que extrajo el campo.
        valor_normalizado: Valor procesado/limpio.
        tipo_campo: Categoría del campo ("ruc", "monto", "fecha", etc.).
    """
    # Identificación
    nombre_campo: str
    valor: Optional[str]

    # Ubicación en documento
    archivo: str
    pagina: int

    # Calidad de extracción
    confianza: float
    metodo: MetodoExtraccion

    # Evidencia
    snippet: str = ""
    regla_aplicada: str = ""

    # Procesamiento
    valor_normalizado: str = ""
    tipo_campo: str = ""

    def es_abstencion(self) -> bool:
        """
        Indica si este campo representa una abstención formal.

        Returns:
            True si valor es None Y confianza es 0.0.
        """
        return self.valor is None and self.confianza == 0.0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializa a diccionario para JSON/JSONL.

        Returns:
            Dict con todos los campos, incluyendo es_abstencion.
        """
        return {
            "nombre_campo": self.nombre_campo,
            "valor": self.valor,
            "archivo": self.archivo,
            "pagina": self.pagina,
            "confianza": self.confianza,
            "metodo": (
                self.metodo.value
                if isinstance(self.metodo, MetodoExtraccion)
                else str(self.metodo)
            ),
            "snippet": self.snippet[:200] if self.snippet else "",
            "regla_aplicada": self.regla_aplicada,
            "valor_normalizado": self.valor_normalizado,
            "tipo_campo": self.tipo_campo,
            "es_abstencion": self.es_abstencion(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampoExtraido":
        """
        Reconstruye desde diccionario.

        Convierte automáticamente el campo 'metodo' de string a enum.

        Args:
            data: Diccionario con los campos del CampoExtraido.

        Returns:
            Instancia de CampoExtraido.
        """
        data = dict(data)  # Copia para no mutar el original
        # Convertir string a enum si es necesario
        if "metodo" in data and isinstance(data["metodo"], str):
            try:
                data["metodo"] = MetodoExtraccion(data["metodo"])
            except ValueError:
                data["metodo"] = MetodoExtraccion.MANUAL
        # Filtrar campos que no son del dataclass
        valid_fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


@dataclass
class UmbralesAbstencion:
    """
    Umbrales de confianza por tipo de campo.

    Diferentes tipos de campo requieren diferentes niveles de certeza.
    Campos financieros (RUC, montos) tienen umbrales más altos porque
    un error ahí tiene consecuencias legales graves.

    Los umbrales se consultan con get_umbral(tipo_campo).
    Si el tipo no está definido, se usa el default.

    Attributes:
        ruc: Umbral para RUC (0.90 — muy estricto).
        monto: Umbral para montos monetarios (0.90).
        fecha: Umbral para fechas (0.85).
        numero_documento: Umbral para números de documento (0.85).
        nombre_persona: Umbral para nombres de persona (0.80).
        nombre_entidad: Umbral para nombres de entidad (0.80).
        texto_general: Umbral para texto descriptivo (0.70).
        descripcion: Umbral para descripciones (0.70).
        default: Umbral por defecto para campos no especificados (0.75).
    """
    # Campos críticos (consecuencias legales directas)
    ruc: float = 0.90
    monto: float = 0.90

    # Campos importantes (afectan validez)
    fecha: float = 0.85
    numero_documento: float = 0.85

    # Campos estándar (afectan completitud)
    nombre_persona: float = 0.80
    nombre_entidad: float = 0.80

    # Campos descriptivos (menor impacto)
    texto_general: float = 0.70
    descripcion: float = 0.70

    # Fallback
    default: float = 0.75

    def get_umbral(self, tipo_campo: str) -> float:
        """
        Obtiene el umbral de confianza para un tipo de campo.

        La búsqueda es case-insensitive y con strip.

        Args:
            tipo_campo: Tipo del campo (ej: "ruc", "Monto", " FECHA ").

        Returns:
            Umbral de confianza 0.0-1.0.
        """
        tipo_normalizado = tipo_campo.lower().strip()
        return getattr(self, tipo_normalizado, self.default)

    def to_dict(self) -> Dict[str, float]:
        """Serializa a diccionario."""
        return asdict(self)


@dataclass
class ResultadoAbstencion:
    """
    Resultado de evaluar si un campo debe abstenerse.

    Contiene la decisión, la razón detallada, y el hallazgo
    automático generado (si corresponde).

    Attributes:
        campo: El CampoExtraido evaluado.
        debe_abstenerse: True si el campo no cumple los umbrales.
        razon_abstencion: Descripción textual de la razón.
        razon_codigo: Código enum de la razón.
        hallazgo: Observacion generada automáticamente (si abstención).
        umbral_aplicado: El umbral que se usó para la evaluación.
    """
    campo: CampoExtraido
    debe_abstenerse: bool
    razon_abstencion: str = ""
    razon_codigo: Optional[RazonAbstencion] = None
    hallazgo: Optional[Observacion] = None
    umbral_aplicado: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para JSON."""
        d: Dict[str, Any] = {
            "campo_nombre": self.campo.nombre_campo,
            "debe_abstenerse": self.debe_abstenerse,
            "confianza": self.campo.confianza,
            "umbral_aplicado": self.umbral_aplicado,
            "razon_abstencion": self.razon_abstencion,
            "razon_codigo": (
                self.razon_codigo.value if self.razon_codigo else None
            ),
        }
        if self.hallazgo:
            d["hallazgo"] = {
                "nivel": self.hallazgo.nivel.value,
                "descripcion": self.hallazgo.descripcion,
                "agente": self.hallazgo.agente,
                "requiere_revision_humana": self.hallazgo.requiere_revision_humana,
            }
        return d

    def get_excel_format_spec(self) -> Dict[str, Any]:
        """
        Retorna especificación de formato para celda Excel.

        Cuando hay abstención:
          - bg_color: "FF0000" (rojo)
          - font_color: "FFFFFF" (blanco)
          - comment: razón de la abstención
          - border: True

        Returns:
            Dict vacío si no hay abstención, o con specs si hay.
        """
        if not self.debe_abstenerse:
            return {}

        return {
            "bg_color": "FF0000",
            "font_color": "FFFFFF",
            "comment": self.razon_abstencion,
            "border": True,
        }


# ==============================================================================
# CLASE PRINCIPAL: AbstencionPolicy
# ==============================================================================
class AbstencionPolicy:
    """
    Motor de política de abstención formal.

    Evalúa campos extraídos y determina si el sistema debe
    abstenerse de reportar un valor por falta de confianza.

    Implementa Artículo 3 (Anti-alucinación) de Gobernanza:
      "El sistema tiene prohibido generar, inferir, suponer o
       inventar información que no esté explícitamente contenida
       en los documentos del expediente."

    Flujo de evaluación:
      1. Verificar si campo ya es abstención explícita (valor=None)
      2. Comparar confianza vs umbral del tipo de campo
      3. Validar metadata mínima (snippet, página)
      4. Generar hallazgo automático si abstención
      5. Registrar en TraceLogger (si disponible)

    Ejemplo:
        policy = AbstencionPolicy()
        resultado = policy.evaluar_campo(campo, tipo_campo="ruc")

        if resultado.debe_abstenerse:
            campo_final = policy.generar_campo_abstencion(
                nombre_campo=campo.nombre_campo,
                razon=resultado.razon_abstencion,
            )

    Attributes:
        umbrales: Configuración de umbrales por tipo de campo.
        agente_id: ID del agente que usa esta política.
        logger: TraceLogger para trazabilidad (opcional).
    """

    def __init__(
        self,
        umbrales: Optional[UmbralesAbstencion] = None,
        agente_id: str = "AG02",
        trace_logger: Optional[Any] = None,
    ):
        """
        Inicializa la política de abstención.

        Args:
            umbrales: Umbrales de confianza por tipo de campo.
                      Por defecto usa UmbralesAbstencion().
            agente_id: ID del agente que usa la política (ej: "AG02").
            trace_logger: Instancia de TraceLogger para registro (opcional).
        """
        self.umbrales = umbrales or UmbralesAbstencion()
        self.agente_id = agente_id
        self.logger = trace_logger

        # Estadísticas de uso
        self._stats: Dict[str, Any] = {
            "total_evaluados": 0,
            "total_abstenciones": 0,
            "por_razon": {},
        }

    # ------------------------------------------------------------------
    # EVALUACIÓN DE CAMPOS
    # ------------------------------------------------------------------
    def evaluar_campo(
        self,
        campo: CampoExtraido,
        tipo_campo: Optional[str] = None,
    ) -> ResultadoAbstencion:
        """
        Evalúa si un campo debe abstenerse.

        Decisión basada en:
          1. Valor presente/ausente
          2. Nivel de confianza vs umbral del tipo
          3. Metadata completa (snippet, página)

        Args:
            campo: Campo extraído a evaluar.
            tipo_campo: Tipo explícito (sobreescribe campo.tipo_campo).

        Returns:
            ResultadoAbstencion con decisión, razón, y hallazgo.
        """
        self._stats["total_evaluados"] += 1

        tipo = tipo_campo or campo.tipo_campo or "default"
        umbral = self.umbrales.get_umbral(tipo)

        # Evaluar condiciones de abstención
        debe_abstenerse, razon_codigo = self._debe_abstenerse(campo, umbral)

        if debe_abstenerse:
            self._stats["total_abstenciones"] += 1
            if razon_codigo:
                key = razon_codigo.value
                self._stats["por_razon"][key] = (
                    self._stats["por_razon"].get(key, 0) + 1
                )

        # Generar descripción textual de la razón
        razon_texto = self._generar_razon_texto(campo, razon_codigo, umbral)

        # Generar hallazgo automático si hay abstención
        hallazgo = None
        if debe_abstenerse:
            hallazgo = self._generar_hallazgo_abstencion(campo, razon_texto)

        # Registrar en TraceLogger
        self._log_evaluacion(campo, debe_abstenerse, razon_codigo, umbral)

        return ResultadoAbstencion(
            campo=campo,
            debe_abstenerse=debe_abstenerse,
            razon_abstencion=razon_texto,
            razon_codigo=razon_codigo,
            hallazgo=hallazgo,
            umbral_aplicado=umbral,
        )

    def evaluar_lote(
        self,
        campos: List[CampoExtraido],
    ) -> List[ResultadoAbstencion]:
        """
        Evalúa múltiples campos en lote.

        Cada campo se evalúa independientemente con su propio
        tipo de campo y umbral correspondiente.

        Args:
            campos: Lista de campos a evaluar.

        Returns:
            Lista de ResultadoAbstencion en el mismo orden.
        """
        return [self.evaluar_campo(c) for c in campos]

    # ------------------------------------------------------------------
    # GENERACIÓN DE CAMPOS EN ABSTENCIÓN
    # ------------------------------------------------------------------
    def generar_campo_abstencion(
        self,
        nombre_campo: str,
        razon: str,
        tipo_campo: str = "",
    ) -> CampoExtraido:
        """
        Genera un CampoExtraido en estado de abstención formal.

        Cumple con los criterios de aceptación de la Tarea #12:
          - valor = None
          - confianza = 0.0
          - regla_aplicada = "ABSTENCION"

        Args:
            nombre_campo: Nombre del campo.
            razon: Razón de la abstención.
            tipo_campo: Tipo del campo.

        Returns:
            CampoExtraido en estado de abstención.
        """
        return CampoExtraido(
            nombre_campo=nombre_campo,
            valor=None,
            archivo="",
            pagina=0,
            confianza=0.0,
            metodo=MetodoExtraccion.MANUAL,
            snippet="",
            regla_aplicada=FUENTE_ABSTENCION,
            tipo_campo=tipo_campo,
            valor_normalizado="",
        )

    # ------------------------------------------------------------------
    # ESTADÍSTICAS
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas de uso de la política.

        Returns:
            Dict con total_evaluados, total_abstenciones,
            tasa_abstencion, por_razon.
        """
        total = self._stats["total_evaluados"]
        return {
            **self._stats,
            "tasa_abstencion": (
                round(self._stats["total_abstenciones"] / total, 4)
                if total > 0
                else 0.0
            ),
        }

    def reset_stats(self) -> None:
        """Reinicia las estadísticas a cero."""
        self._stats = {
            "total_evaluados": 0,
            "total_abstenciones": 0,
            "por_razon": {},
        }

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------
    def _debe_abstenerse(
        self,
        campo: CampoExtraido,
        umbral: float,
    ) -> Tuple[bool, Optional[RazonAbstencion]]:
        """
        Determina si un campo debe abstenerse.

        Evalúa en orden de prioridad:
          1. Valor ausente (None)
          2. Confianza por debajo del umbral
          3. Sin evidencia textual (snippet vacío)
          4. Página inválida (<=0)

        Returns:
            Tupla (debe_abstenerse, razon_codigo).
        """
        # 1. Valor ausente desde origen
        if campo.valor is None:
            return True, RazonAbstencion.VALOR_AUSENTE

        # 2. Confianza por debajo del umbral
        if campo.confianza < umbral:
            return True, RazonAbstencion.CONFIANZA_BAJA

        # 3. Sin evidencia textual
        if not campo.snippet or not campo.snippet.strip():
            return True, RazonAbstencion.SNIPPET_VACIO

        # 4. Página inválida
        if campo.pagina <= 0:
            return True, RazonAbstencion.PAGINA_INVALIDA

        # No hay razón para abstención
        return False, None

    def _generar_razon_texto(
        self,
        campo: CampoExtraido,
        razon_codigo: Optional[RazonAbstencion],
        umbral: float,
    ) -> str:
        """
        Genera descripción textual de la razón de abstención.

        Usa las frases estándar del Artículo 12.1 de Gobernanza.

        Returns:
            String vacío si no hay abstención, descripción si hay.
        """
        if not razon_codigo:
            return ""

        tipo_display = campo.tipo_campo or "default"

        razones = {
            RazonAbstencion.VALOR_AUSENTE: (
                f"Campo '{campo.nombre_campo}': "
                f"{FRASE_ABSTENCION_ESTANDAR}"
            ),
            RazonAbstencion.CONFIANZA_BAJA: (
                f"Campo '{campo.nombre_campo}': confianza "
                f"{campo.confianza:.2f} por debajo del umbral "
                f"{umbral:.2f} para tipo '{tipo_display}'. "
                f"{FRASE_ABSTENCION_ESTANDAR}"
            ),
            RazonAbstencion.SNIPPET_VACIO: (
                f"Campo '{campo.nombre_campo}': sin contexto textual "
                f"verificable en el documento. "
                f"{FRASE_ABSTENCION_ESTANDAR}"
            ),
            RazonAbstencion.PAGINA_INVALIDA: (
                f"Campo '{campo.nombre_campo}': sin ubicación de "
                f"página válida en el documento. "
                f"{FRASE_ABSTENCION_ESTANDAR}"
            ),
            RazonAbstencion.MULTIPLE_CONTRADICTORIO: (
                f"Campo '{campo.nombre_campo}': múltiples valores "
                f"contradictorios detectados. "
                f"{FRASE_ABSTENCION_ESTANDAR}"
            ),
        }

        return razones.get(razon_codigo, FRASE_ABSTENCION_ESTANDAR)

    def _generar_hallazgo_abstencion(
        self,
        campo: CampoExtraido,
        razon: str,
    ) -> Observacion:
        """
        Genera un hallazgo automático por abstención.

        El hallazgo es nivel INFORMATIVA (no bloquea el pago)
        pero marca requiere_revision_humana=True para que el
        analista lo verifique manualmente.

        Args:
            campo: El campo que se abstiene.
            razon: Descripción de la razón.

        Returns:
            Observacion con nivel INFORMATIVA y marca de revisión.
        """
        return Observacion(
            nivel=NivelObservacion.INFORMATIVA,
            agente=self.agente_id,
            descripcion=razon,
            accion_requerida=(
                f"Verificar manualmente el campo "
                f"'{campo.nombre_campo}' en el documento fuente."
            ),
            area_responsable="Usuario Analista",
            requiere_revision_humana=True,
            regla_aplicada=FUENTE_ABSTENCION,
        )

    def _log_evaluacion(
        self,
        campo: CampoExtraido,
        debe_abstenerse: bool,
        razon_codigo: Optional[RazonAbstencion],
        umbral: float,
    ) -> None:
        """
        Registra la evaluación en el TraceLogger.

        No hace nada si no hay logger configurado.
        """
        if not self.logger:
            return

        try:
            level = "WARNING" if debe_abstenerse else "INFO"
            message = (
                f"Campo '{campo.nombre_campo}' evaluado: "
                f"abstención={debe_abstenerse} "
                f"(conf={campo.confianza:.2f}, umbral={umbral:.2f})"
            )
            context = {
                "campo": campo.nombre_campo,
                "valor_presente": campo.valor is not None,
                "confianza": campo.confianza,
                "umbral": umbral,
                "debe_abstenerse": debe_abstenerse,
                "razon": razon_codigo.value if razon_codigo else None,
            }

            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method(
                message,
                agent_id=self.agente_id,
                operation="evaluar_abstencion",
                context=context,
            )
        except Exception:
            # Logger no debe romper la evaluación
            pass

    # ------------------------------------------------------------------
    # REPRESENTACIÓN
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"AbstencionPolicy("
            f"evaluados={stats['total_evaluados']}, "
            f"abstenciones={stats['total_abstenciones']}, "
            f"tasa={stats['tasa_abstencion']:.1%})"
        )
