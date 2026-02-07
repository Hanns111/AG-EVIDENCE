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
from typing import List, Dict, Optional
from enum import Enum

# ==============================================================================
# RUTAS DEL SISTEMA
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_DIR = os.path.dirname(BASE_DIR)  # C:\Users\hanns\Downloads
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Carpeta de directivas vigentes
DIRECTIVAS_DIR = os.path.join(DOWNLOADS_DIR, "DIRECITVAS VIGENTES AL 26.11.2025")
DIRECTIVA_CAJA_CHICA = os.path.join(DIRECTIVAS_DIR, "CAJA CHICA")
DIRECTIVA_ENCARGO = os.path.join(DIRECTIVAS_DIR, "ENCARGO")
DIRECTIVA_VIATICOS = os.path.join(DIRECTIVAS_DIR, "VIÁTICO")
DIRECTIVA_PAUTAS = os.path.join(DIRECTIVAS_DIR, "PAUTAS")


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
    CRITICA = "CRÍTICA"           # Bloquea el pago
    MAYOR = "MAYOR"               # Subsanable antes de devengar
    MENOR = "MENOR"               # Mejoras documentales
    INFORMATIVA = "INFORMATIVA"   # Solo para conocimiento
    INCIERTO = "INCIERTO"         # Hallazgo sin evidencia suficiente


class MetodoExtraccion(Enum):
    """Método usado para extraer la evidencia"""
    PDF_TEXT = "PDF_TEXT"         # Texto directo del PDF
    OCR = "OCR"                   # Reconocimiento óptico
    REGEX = "REGEX"               # Expresión regular
    HEURISTICA = "HEURISTICA"     # Regla heurística
    METADATA = "METADATA"         # Metadatos del PDF
    MANUAL = "MANUAL"             # Requiere verificación manual


class NivelConfianza(Enum):
    """Nivel de confianza en la extracción"""
    HIGH = "HIGH"                 # >= 0.9
    MEDIUM = "MEDIUM"             # 0.7 - 0.9
    LOW = "LOW"                   # < 0.7


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
    archivo: str                              # Nombre exacto del archivo
    pagina: int                               # Número de página (1-indexed)
    valor_detectado: str                      # Valor encontrado
    valor_esperado: str = ""                  # Valor esperado (si aplica)
    snippet: str = ""                         # Texto exacto extraído (contexto)
    metodo_extraccion: MetodoExtraccion = MetodoExtraccion.PDF_TEXT
    confianza: float = 1.0                    # 0.0 a 1.0
    regla_aplicada: str = ""                  # ID o descripción de la regla
    
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
            self.archivo and 
            self.pagina > 0 and 
            self.valor_detectado and
            self.snippet and
            self.regla_aplicada
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
            "regla_aplicada": self.regla_aplicada
        }
    
    def formato_txt(self) -> str:
        """Formato legible para TXT"""
        return f'{self.archivo} pág. {self.pagina} -> "{self.snippet[:100]}..."'


@dataclass 
class OcurrenciaValor:
    """Una ocurrencia de un valor detectado en un documento"""
    archivo: str
    pagina: int
    valor_original: str          # Valor tal como aparece
    valor_normalizado: str       # Valor normalizado (sin ceros, espacios, etc.)
    snippet: str                 # Contexto del texto
    posicion_inicio: int = 0     # Posición en el texto
    confianza: float = 1.0
    metodo: MetodoExtraccion = MetodoExtraccion.PDF_TEXT


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
    
    # Campo legacy para compatibilidad
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
    
    def validar_y_degradar(self) -> 'Observacion':
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
            lineas.append(f'   📎 {ev.formato_txt()}')
            lineas.append(f'      Método: {ev.metodo_extraccion.value} | Confianza: {ev.nivel_confianza.value}')
        
        if len(self.evidencias) > 3:
            lineas.append(f'   ... y {len(self.evidencias) - 3} evidencias más')
        
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
# CONFIGURACIÓN DE APIS SUNAT (PÚBLICAS / GRATUITAS)
# ==============================================================================
SUNAT_CONFIG = {
    # API pública de consulta RUC (terceros gratuitos)
    "apis_ruc": [
        {
            "nombre": "API Peru",
            "url": "https://api.apis.net.pe/v1/ruc",
            "token": None,  # Algunas tienen planes gratuitos limitados
            "activa": True
        },
        {
            "nombre": "Consulta RUC PE", 
            "url": "https://www.consultaruc.pe/api/",
            "token": None,
            "activa": True
        }
    ],
    # Fallback: web scraping de página pública SUNAT
    "sunat_web_publica": "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias",
    
    # IMPORTANTE: SIRE está DESHABILITADO (requiere SOL)
    "sire_habilitado": False,
    "sol_habilitado": False,
    
    # Timeouts
    "timeout_segundos": 10,
    "reintentos": 2
}


# ==============================================================================
# KEYWORDS PARA DETECCIÓN DE NATURALEZA
# ==============================================================================
KEYWORDS_NATURALEZA = {
    NaturalezaExpediente.VIATICOS: [
        "viático", "viáticos", "planilla de viáticos", "comisión de servicio",
        "pasajes", "hospedaje", "movilidad local", "declaración jurada de gastos",
        "anexo 3", "rendición de viáticos"
    ],
    NaturalezaExpediente.CAJA_CHICA: [
        "caja chica", "fondo fijo", "reembolso", "gastos menores",
        "apertura de caja chica", "rendición de caja chica"
    ],
    NaturalezaExpediente.ENCARGO: [
        "encargo", "encargo interno", "rendición de encargo",
        "fondo en encargo"
    ],
    NaturalezaExpediente.PAGO_PROVEEDOR: [
        "proveedor", "contratista", "factura", "orden de servicio",
        "orden de compra", "conformidad", "devengado", "armada"
    ],
    NaturalezaExpediente.CONTRATO: [
        "contrato", "licitación", "concurso público", "adjudicación",
        "buena pro", "bases integradas"
    ],
    NaturalezaExpediente.SUBVENCIONES: [
        "subvención", "subvenciones", "transferencia", "donación",
        "aporte", "financiamiento", "subsidio"
    ]
}


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
    "timeout_segundos": 120,      # Timeout por PDF
    "max_paginas_ocr": 200,       # Límite de seguridad
    "directorio_temporal": "output/ocr_temp",
    "ocrmypdf_flags": [
        "--skip-text",             # No toca PDFs nativos
        "--deskew",                # Corrige rotación leve
        "--clean",                 # Limpia imagen
        "--output-type", "pdf",    # Salida PDF estándar
    ],
}


# ==============================================================================
# CONFIGURACIÓN DE LOGGING
# ==============================================================================
LOG_CONFIG = {
    "nivel": "INFO",
    "formato": "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    "archivo": os.path.join(OUTPUT_DIR, "control_previo.log")
}


if __name__ == "__main__":
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"DOWNLOADS_DIR: {DOWNLOADS_DIR}")
    print(f"DIRECTIVAS_DIR: {DIRECTIVAS_DIR}")
    print(f"UIT 2025: S/ {LIMITES_NORMATIVOS['UIT_2025']:,.2f}")
    print(f"Límite 8 UIT: S/ {LIMITES_NORMATIVOS['limite_8_uit']:,.2f}")

