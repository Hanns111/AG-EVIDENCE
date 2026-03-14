# -*- coding: utf-8 -*-
"""
CONFIGURACIÓN GLOBAL DEL SISTEMA DE CONTROL PREVIO PREMIUM
===========================================================
Arquitectura Multi-Agente para revisión de expedientes administrativos
del sector público peruano.

RESTRICCIONES:
- NO usa Clave SOL
- NO integra SIRE autenticado
- NO usa servicios de pago
- Solo consultas públicas SUNAT / APIs gratuitas
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# ==============================================================================
# RUTAS DEL SISTEMA
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


# ==============================================================================
# ENUMERACIONES
# ==============================================================================
class NaturalezaExpediente(Enum):
    """Tipos de expediente que el sistema puede procesar"""

    VIATICOS = "VIÁTICOS"
    CAJA_CHICA = "CAJA CHICA"
    ENCARGO = "ENCARGO"
    PAGO_PROVEEDOR = "PAGO A PROVEEDOR"
    ORDEN_SERVICIO = "ORDEN DE SERVICIO"
    ORDEN_COMPRA = "ORDEN DE COMPRA"
    CONTRATO = "CONTRATO"
    SUBVENCIONES = "SUBVENCIONES"
    CONVENIO_INTERINSTITUCIONAL = "CONVENIO INTERINSTITUCIONAL"
    OTRO = "OTRO"
    NO_DETERMINADO = "NO DETERMINADO"


class TipoProcedimiento(Enum):
    """Tipos de procedimiento de selección"""

    LICITACION_PUBLICA = "LICITACIÓN PÚBLICA"
    CONCURSO_PUBLICO = "CONCURSO PÚBLICO"
    ADJUDICACION_SIMPLIFICADA = "ADJUDICACIÓN SIMPLIFICADA"
    SELECCION_CONSULTORES = "SELECCIÓN DE CONSULTORES INDIVIDUALES"
    SUBASTA_INVERSA = "SUBASTA INVERSA ELECTRÓNICA"
    COMPARACION_PRECIOS = "COMPARACIÓN DE PRECIOS"
    CONTRATACION_DIRECTA = "CONTRATACIÓN DIRECTA"
    ACUERDO_MARCO = "ACUERDO MARCO"
    MENOR_8_UIT = "CONTRATACIÓN MENOR A 8 UIT"
    NO_DETERMINADO = "NO DETERMINADO"


class NivelObservacion(Enum):
    """Niveles de criticidad de observaciones"""

    CRITICA = "CRÍTICA"  # Bloquea el pago
    MAYOR = "MAYOR"  # Subsanable antes de devengar
    MENOR = "MENOR"  # Mejoras documentales
    INFORMATIVA = "INFORMATIVA"  # Solo para conocimiento
    INCIERTO = "INCIERTO"  # Hallazgo sin evidencia suficiente


class MetodoExtraccion(Enum):
    """Método usado para extraer la evidencia"""

    PDF_TEXT = "PDF_TEXT"  # Texto directo del PDF
    OCR = "OCR"  # Reconocimiento óptico
    REGEX = "REGEX"  # Expresión regular
    HEURISTICA = "HEURISTICA"  # Regla heurística
    METADATA = "METADATA"  # Metadatos del PDF
    MANUAL = "MANUAL"  # Requiere verificación manual


class NivelConfianza(Enum):
    """Nivel de confianza en la extracción"""

    HIGH = "HIGH"  # >= 0.9
    MEDIUM = "MEDIUM"  # 0.7 - 0.9
    LOW = "LOW"  # < 0.7


class EstadoRUC(Enum):
    """Estados posibles de RUC en SUNAT"""

    ACTIVO = "ACTIVO"
    BAJA_PROVISIONAL = "BAJA PROVISIONAL"
    BAJA_DEFINITIVA = "BAJA DEFINITIVA"
    SUSPENSION_TEMPORAL = "SUSPENSIÓN TEMPORAL"
    NO_ENCONTRADO = "NO ENCONTRADO"
    INCERTIDUMBRE = "INCERTIDUMBRE"


class CondicionRUC(Enum):
    """Condiciones de domicilio fiscal"""

    HABIDO = "HABIDO"
    NO_HABIDO = "NO HABIDO"
    NO_HALLADO = "NO HALLADO"
    PENDIENTE = "PENDIENTE"
    INCERTIDUMBRE = "INCERTIDUMBRE"


class DecisionFinal(Enum):
    """Decisión final del Control Previo"""

    PROCEDE = "PROCEDE"
    PROCEDE_CON_OBSERVACIONES = "PROCEDE CON OBSERVACIONES"
    NO_PROCEDE = "NO PROCEDE"
    INCERTIDUMBRE = "INCERTIDUMBRE"


# ==============================================================================
# DATACLASSES PARA ESTRUCTURAS DE DATOS
# ==============================================================================
@dataclass
class EvidenciaProbatoria:
    """
    Evidencia con estándar probatorio para hallazgos CRÍTICOS y MAYORES.
    Todos los campos son obligatorios para estos niveles.
    """

    archivo: str  # Nombre exacto del archivo
    pagina: int  # Número de página (1-indexed)
    valor_detectado: str  # Valor encontrado
    valor_esperado: str = ""  # Valor esperado (si aplica)
    snippet: str = ""  # Texto exacto extraído (contexto)
    metodo_extraccion: MetodoExtraccion = MetodoExtraccion.PDF_TEXT
    confianza: float = 1.0  # 0.0 a 1.0
    regla_aplicada: str = ""  # ID o descripción de la regla

    @property
    def nivel_confianza(self) -> NivelConfianza:
        """Retorna nivel de confianza categórico"""
        if self.confianza >= 0.9:
            return NivelConfianza.HIGH
        elif self.confianza >= 0.7:
            return NivelConfianza.MEDIUM
        else:
            return NivelConfianza.LOW

    def es_completa(self) -> bool:
        """Verifica si la evidencia tiene todos los campos mínimos"""
        return bool(
            self.archivo
            and self.pagina > 0
            and self.valor_detectado
            and self.snippet
            and self.regla_aplicada
        )

    def to_dict(self) -> Dict:
        """Convierte a diccionario para exportación"""
        return {
            "archivo": self.archivo,
            "pagina": self.pagina,
            "valor_detectado": self.valor_detectado,
            "valor_esperado": self.valor_esperado,
            "snippet": self.snippet[:200] if self.snippet else "",  # Limitar snippet
            "metodo_extraccion": self.metodo_extraccion.value,
            "confianza": self.confianza,
            "nivel_confianza": self.nivel_confianza.value,
            "regla_aplicada": self.regla_aplicada,
        }

    def formato_txt(self) -> str:
        """Formato legible para TXT"""
        return f'{self.archivo} pág. {self.pagina} -> "{self.snippet[:100]}..."'


@dataclass
class Observacion:
    """Estructura para una observación detectada con estándar probatorio"""

    nivel: NivelObservacion
    agente: str
    descripcion: str
    accion_requerida: str
    area_responsable: str = ""

    # Evidencia probatoria (obligatoria para CRITICA/MAYOR)
    evidencias: List[EvidenciaProbatoria] = field(default_factory=list)

    evidencia: str = ""

    # Flags de validación
    requiere_revision_humana: bool = False
    regla_aplicada: str = ""

    def agregar_evidencia(self, evidencia: EvidenciaProbatoria):
        """Agrega una evidencia probatoria"""
        self.evidencias.append(evidencia)

    def tiene_evidencia_completa(self) -> bool:
        """Verifica si tiene evidencia probatoria completa"""
        if not self.evidencias:
            return False
        return all(e.es_completa() for e in self.evidencias)

    def validar_y_degradar(self) -> "Observacion":
        """
        Valida la evidencia. Si es CRITICA/MAYOR sin evidencia completa,
        degrada a INCIERTO y marca requiere_revision_humana.
        """
        if self.nivel in [NivelObservacion.CRITICA, NivelObservacion.MAYOR]:
            if not self.tiene_evidencia_completa():
                self.nivel = NivelObservacion.INCIERTO
                self.requiere_revision_humana = True
                self.descripcion = f"[REQUIERE VERIFICACIÓN] {self.descripcion}"
        return self

    def get_evidencia_principal(self) -> Optional[EvidenciaProbatoria]:
        """Obtiene la primera evidencia (principal)"""
        return self.evidencias[0] if self.evidencias else None

    def formato_evidencia_txt(self) -> str:
        """Formatea las evidencias para TXT"""
        if not self.evidencias:
            return self.evidencia or "Sin evidencia específica"

        lineas = []
        for ev in self.evidencias[:3]:  # Máximo 3 evidencias
            lineas.append(f"   📎 {ev.formato_txt()}")
            lineas.append(
                f"      Método: {ev.metodo_extraccion.value} | Confianza: {ev.nivel_confianza.value}"
            )

        if len(self.evidencias) > 3:
            lineas.append(f"   ... y {len(self.evidencias) - 3} evidencias más")

        return "\n".join(lineas)


@dataclass
class ResultadoAgente:
    """Resultado estandarizado de cada agente"""

    agente_id: str
    agente_nombre: str
    exito: bool
    observaciones: List[Observacion] = field(default_factory=list)
    datos_extraidos: Dict = field(default_factory=dict)
    incertidumbres: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)


@dataclass
class DatosExpediente:
    """Datos consolidados del expediente"""

    # Identificadores
    sinad: str = ""
    siaf: str = ""
    proveido: str = ""

    # Documentos
    numero_contrato: str = ""
    numero_orden: str = ""
    numero_proceso: str = ""

    # Proveedor
    ruc_proveedor: str = ""
    razon_social: str = ""

    # Montos
    monto_contractual: float = 0.0
    monto_a_pagar: float = 0.0

    # Fechas
    fecha_inicio: str = ""
    fecha_fin: str = ""
    fecha_conformidad: str = ""

    # Clasificación
    naturaleza: NaturalezaExpediente = NaturalezaExpediente.NO_DETERMINADO
    tipo_procedimiento: TipoProcedimiento = TipoProcedimiento.NO_DETERMINADO

    # Armada
    numero_armada: str = ""
    total_armadas: str = ""


@dataclass
class ResultadoSUNAT:
    """Resultado de consulta SUNAT"""

    ruc: str
    estado: EstadoRUC
    condicion: CondicionRUC
    razon_social: str = ""
    actividad_economica: str = ""
    direccion: str = ""
    es_informativo: bool = True  # Siempre True (restricción)
    mensaje_incertidumbre: str = ""


@dataclass
class InformeControlPrevio:
    """Informe final de Control Previo"""

    # Metadatos
    fecha_analisis: str = ""
    expediente_sinad: str = ""

    # Clasificación
    naturaleza: NaturalezaExpediente = NaturalezaExpediente.NO_DETERMINADO
    directiva_aplicada: str = ""

    # Resumen
    resumen_ejecutivo: str = ""

    # Observaciones clasificadas
    observaciones_criticas: List[Observacion] = field(default_factory=list)
    observaciones_mayores: List[Observacion] = field(default_factory=list)
    observaciones_menores: List[Observacion] = field(default_factory=list)

    # SUNAT
    riesgos_sunat: List[str] = field(default_factory=list)

    # Decisión
    decision: DecisionFinal = DecisionFinal.INCERTIDUMBRE
    recomendacion_final: str = ""
    accion_requerida: str = ""
    area_responsable: str = ""

    # Resultados de agentes
    resultados_agentes: List[ResultadoAgente] = field(default_factory=list)


# ==============================================================================
# TOPES Y LÍMITES NORMATIVOS
# ==============================================================================
LIMITES_NORMATIVOS = {
    # UIT 2025
    "UIT_2025": 5350.00,
    # Viáticos (según directiva)
    "viaticos_lima_dia": 320.00,
    "viaticos_provincia_dia": 320.00,
    "movilidad_lima_dia": 45.00,
    "movilidad_provincia_dia": 30.00,
    # Contrataciones
    "limite_8_uit": 5350.00 * 8,  # 42,800
    # Detracciones
    "monto_minimo_detraccion": 700.00,
    "tasa_detraccion_servicios": 0.12,  # 12%
}


# ==============================================================================
# CONFIGURACIÓN DE OCR
# ==============================================================================
OCR_CONFIG = {
    "idioma_default": "spa",
    "timeout_segundos": 120,  # Timeout por PDF
    "max_paginas_ocr": 200,  # Límite de seguridad
    "directorio_temporal": "output/ocr_temp",
    "ocrmypdf_flags": [
        "--skip-text",  # No toca PDFs nativos
        "--deskew",  # Corrige rotación leve
        "--clean",  # Limpia imagen
        "--output-type",
        "pdf",  # Salida PDF estándar
    ],
}


# ==============================================================================
# CONFIGURACIÓN DE VISIÓN (preprocesamiento de imágenes para proveedores)
# ==============================================================================
VISION_CONFIG = {
    "max_dimension_px": 2000,  # Máximo ancho o alto permitido por el proveedor
    "formato_salida": "PNG",  # Formato de la imagen redimensionada
    "calidad_jpeg": 95,  # Calidad si se usa JPEG (0-100)
    "metodo_resample": "LANCZOS",  # Método de interpolación (LANCZOS = alta calidad)
    "dpi_render_pdf": 200,  # DPI para renderizar páginas de PDF a imagen
}


# ==============================================================================
# CONFIGURACIÓN VLM — Qwen3-VL-8B via Ollama (ADR-009 actualizado)
# ==============================================================================
VLM_CONFIG = {
    "enabled": True,
    "model": "qwen2.5vl:7b",  # Primario: fiable, ~25-30s/pág, 0 fallos (2026-03-13)
    "fallback_model": None,  # Sin fallback: qwen2.5vl:7b es estable
    "ollama_url": "http://localhost:11434",
    "timeout_seconds": 60,  # Reducido: qwen2.5vl:7b no necesita thinking, responde <30s
    "max_tokens": 200,  # JSON comprobante ~150-180 tokens, sin thinking overhead
    "temperature": 0.1,
    "num_ctx": 4096,  # Comprobante prompt + imagen < 2K tokens
    "no_think": False,
    "dpi_render": 200,  # DPI para renderizar PDF a imagen para VLM
    "max_retries": 2,  # Retry en JSON corrupto
}

# ==============================================================================
# CONFIGURACION DE IA LOCAL (Capa C — Analista opcional)
# ==============================================================================
LOCAL_ANALYST_CONFIG = {
    "enabled": False,  # Feature flag: True para activar Capa C
    "model": "qwen3:32b",  # Modelo texto (distinto de VLM)
    "ollama_url": "http://localhost:11434",
    "timeout_seconds": 60,
    "max_tokens": 2048,
    "campos_probatorios_bloqueados": [  # Campos que la IA NUNCA puede escribir
        "ruc",
        "monto",
        "serie_numero",
        "fecha",
        "razon_social",
        "igv",
        "valor_venta",
        "base_imponible",
        "total",
        "subtotal",
        "numero_documento",
        "ruc_proveedor",
        "ruc_emisor",
        "monto_total",
        "monto_parcial",
        "fecha_emision",
        "fecha_pago",
        "serie",
        "numero",
    ],
}
