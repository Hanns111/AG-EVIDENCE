# -*- coding: utf-8 -*-
"""
INTEGRADOR DE REGLAS — Conexión con el Sistema AG-EVIDENCE
===========================================================
Proporciona funciones para ejecutar las reglas SPOT y TDR
sobre documentos de un expediente administrativo.

Uso:
    from src.rules.integrador import ejecutar_validacion_spot_tdr

    resultado = ejecutar_validacion_spot_tdr(documentos, es_primera_armada=True)
"""

import os
import sys
import re
from typing import List, Dict, Tuple, Optional, Set, Protocol, runtime_checkable
from dataclasses import dataclass, field

# Agregar paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    Observacion, NivelObservacion, EvidenciaProbatoria,
    MetodoExtraccion, ResultadoAgente, NaturalezaExpediente
)


# =============================================================================
# PROTOCOLO DE DOCUMENTO PDF
# =============================================================================

@runtime_checkable
class PaginaPDF(Protocol):
    """Protocolo mínimo para una página de documento PDF."""
    numero: int
    texto: str


@runtime_checkable
class DocumentoPDF(Protocol):
    """
    Protocolo mínimo que debe cumplir cualquier objeto documento PDF
    pasado al integrador. Cualquier clase con estos atributos es compatible.
    """
    nombre: str
    texto_completo: str
    paginas: List

# Importar módulos de reglas
from src.rules.detraccion_spot import (
    SPOTValidator, DocumentoAnalizado, ResultadoSPOT
)
from src.rules.tdr_requirements import (
    TDRRequirementExtractor, validar_requisitos_tdr, RequisitoTDR
)


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class ResultadoReglasAdicionales:
    """Resultado consolidado de reglas SPOT y TDR"""
    # SPOT
    spot_aplica: bool = False
    spot_motivo: str = ""
    spot_observaciones: List[Observacion] = field(default_factory=list)
    spot_evidencias: List[EvidenciaProbatoria] = field(default_factory=list)
    
    # TDR
    tdr_requisitos: List[RequisitoTDR] = field(default_factory=list)
    tdr_observaciones: List[Observacion] = field(default_factory=list)
    tdr_archivo: str = ""
    
    # Consolidado
    todas_observaciones: List[Observacion] = field(default_factory=list)
    
    def to_resultado_agente(self) -> ResultadoAgente:
        """Convierte a ResultadoAgente para integración con orquestador"""
        self.todas_observaciones = self.spot_observaciones + self.tdr_observaciones
        
        return ResultadoAgente(
            agente_id="RULES",
            agente_nombre="Validador de Reglas Adicionales (SPOT/TDR)",
            exito=len([o for o in self.todas_observaciones 
                       if o.nivel == NivelObservacion.CRITICA]) == 0,
            observaciones=self.todas_observaciones,
            datos_extraidos={
                "spot": {
                    "aplica": self.spot_aplica,
                    "motivo": self.spot_motivo,
                    "evidencias_count": len(self.spot_evidencias)
                },
                "tdr": {
                    "requisitos_count": len(self.tdr_requisitos),
                    "archivo": self.tdr_archivo,
                    "requisitos": [r.to_dict() for r in self.tdr_requisitos[:5]]
                }
            }
        )


# =============================================================================
# FUNCIONES DE CONVERSIÓN
# =============================================================================

def convertir_documento_pdf_a_analizado(doc: DocumentoPDF) -> DocumentoAnalizado:
    """
    Convierte un DocumentoPDF del sistema a DocumentoAnalizado de las reglas.
    """
    paginas = []
    for pag in doc.paginas:
        paginas.append((pag.numero, pag.texto))
    
    return DocumentoAnalizado(
        nombre=doc.nombre,
        texto=doc.texto_completo,
        paginas=paginas
    )


def detectar_tipos_documento_presentes(documentos: List[DocumentoPDF]) -> Set[str]:
    """
    Detecta qué tipos de documentos están presentes en el expediente.
    
    Returns:
        Conjunto de tipos detectados: {"CV", "FACTURA", "CONFORMIDAD", etc.}
    """
    tipos = set()
    
    patrones = {
        "CV": [r"curr[ií]cul", r"\bCV\b", r"hoja\s+de\s+vida"],
        "TITULO_PROFESIONAL": [r"t[ií]tulo\s+profesional", r"diploma", r"grado\s+acad[eé]mico"],
        "CONSTANCIA_COLEGIATURA": [r"colegiatura", r"habilitaci[oó]n\s+profesional"],
        "CONSTANCIA_RNP": [r"RNP", r"registro\s+nacional\s+de\s+proveedores"],
        "DECLARACION_JURADA": [r"declaraci[oó]n\s+jurada"],
        "DNI": [r"\bDNI\b", r"documento\s+de\s+identidad"],
        "FACTURA": [r"factura", r"boleta\s+de\s+venta", r"comprobante\s+de\s+pago"],
        "CONFORMIDAD": [r"conformidad", r"CONF[\.\-]?\d+"],
        "ORDEN_SERVICIO": [r"orden\s+de\s+servicio", r"O\.?S\.?"],
        "ORDEN_COMPRA": [r"orden\s+de\s+compra", r"O\.?C\.?"],
        "TDR": [r"t[eé]rminos\s+de\s+referencia", r"\bTDR\b"],
        "CONTRATO": [r"contrato\s+n[°º]?"],
        "CERTIFICADO_CAPACITACION": [r"certificado", r"capacitaci[oó]n", r"diplomado"],
    }
    
    for doc in documentos:
        texto_buscar = (doc.nombre + " " + doc.texto_completo[:5000]).lower()
        
        for tipo, lista_patrones in patrones.items():
            for patron in lista_patrones:
                if re.search(patron, texto_buscar, re.IGNORECASE):
                    tipos.add(tipo)
                    break
    
    return tipos


def encontrar_documento_tdr(documentos: List[DocumentoPDF]) -> Optional[DocumentoPDF]:
    """
    Encuentra el documento TDR en la lista de documentos.
    """
    patrones_tdr = [
        r"t[eé]rminos?\s+de\s+referencia",
        r"\bTDR\b",
        r"especificaciones?\s+t[eé]cnicas?",
        r"\bEETT\b"
    ]
    
    for doc in documentos:
        texto_buscar = (doc.nombre + " " + doc.texto_completo[:2000]).lower()
        for patron in patrones_tdr:
            if re.search(patron, texto_buscar, re.IGNORECASE):
                return doc
    
    return None


def extraer_monto_operacion(documentos: List[DocumentoPDF]) -> Optional[float]:
    """
    Extrae el monto de la operación desde los documentos.
    """
    patron_monto = r"S/?\.?\s*([\d,]+\.\d{2})"
    
    montos = []
    for doc in documentos:
        matches = re.findall(patron_monto, doc.texto_completo)
        for m in matches:
            try:
                monto = float(m.replace(',', ''))
                if 100 <= monto <= 10000000:  # Rango razonable
                    montos.append(monto)
            except:
                pass
    
    return max(montos) if montos else None


def extraer_tipo_servicio(documentos: List[DocumentoPDF]) -> Optional[str]:
    """
    Extrae descripción del servicio desde los documentos.
    """
    patrones_objeto = [
        r"(?:objeto|descripci[oó]n)\s*:\s*(.{10,200})",
        r"servicio\s+de\s+(.{5,100})",
        r"contrataci[oó]n\s+(?:del?\s+)?servicio\s+(?:de\s+)?(.{5,100})",
    ]
    
    for doc in documentos:
        for patron in patrones_objeto:
            match = re.search(patron, doc.texto_completo, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
    
    return None


# =============================================================================
# FUNCIÓN PRINCIPAL DE INTEGRACIÓN
# =============================================================================

def ejecutar_validacion_spot_tdr(
    documentos: List[DocumentoPDF],
    es_primera_armada: bool = True,
    naturaleza: NaturalezaExpediente = None,
    verbose: bool = False
) -> ResultadoReglasAdicionales:
    """
    Ejecuta las validaciones SPOT y TDR sobre los documentos del expediente.
    
    Args:
        documentos: Lista de DocumentoPDF del expediente
        es_primera_armada: Si es primera armada (para validar TDR)
        naturaleza: Naturaleza del expediente
        verbose: Si True, imprime progreso
    
    Returns:
        ResultadoReglasAdicionales con todas las validaciones
    """
    resultado = ResultadoReglasAdicionales()
    
    if verbose:
        print("\n🔍 Ejecutando reglas adicionales SPOT/TDR...")
    
    # =========================================================================
    # 1. VALIDACIÓN SPOT
    # =========================================================================
    if verbose:
        print("   📋 Validando detracción SPOT...")
    
    # Convertir documentos
    docs_analizados = [convertir_documento_pdf_a_analizado(d) for d in documentos]
    
    # Extraer datos auxiliares
    monto = extraer_monto_operacion(documentos)
    tipo_servicio = extraer_tipo_servicio(documentos)
    
    # Ejecutar validador SPOT
    validator_spot = SPOTValidator()
    resultado_spot = validator_spot.spot_aplica(
        docs_analizados, 
        monto_operacion=monto,
        tipo_servicio=tipo_servicio
    )
    
    resultado.spot_aplica = resultado_spot.aplica
    resultado.spot_motivo = resultado_spot.motivo
    resultado.spot_observaciones = resultado_spot.observaciones
    resultado.spot_evidencias = resultado_spot.evidencias_encontradas
    
    if verbose:
        estado = "✅ Aplica" if resultado.spot_aplica else "⬜ No aplica"
        print(f"      SPOT: {estado}")
        if resultado.spot_observaciones:
            print(f"      Observaciones SPOT: {len(resultado.spot_observaciones)}")
    
    # =========================================================================
    # 2. VALIDACIÓN TDR (solo en primera armada)
    # =========================================================================
    if es_primera_armada:
        if verbose:
            print("   📋 Validando requisitos del TDR...")
        
        # Buscar documento TDR
        doc_tdr = encontrar_documento_tdr(documentos)
        
        if doc_tdr:
            resultado.tdr_archivo = doc_tdr.nombre
            
            # Extraer requisitos
            extractor_tdr = TDRRequirementExtractor()
            paginas_tdr = [(p.numero, p.texto) for p in doc_tdr.paginas]
            resultado_tdr = extractor_tdr.extraer_requisitos(
                doc_tdr.texto_completo,
                doc_tdr.nombre,
                paginas_tdr
            )
            
            resultado.tdr_requisitos = resultado_tdr.requisitos
            
            if verbose:
                print(f"      TDR encontrado: {doc_tdr.nombre}")
                print(f"      Requisitos detectados: {len(resultado.tdr_requisitos)}")
            
            # Detectar documentos presentes
            docs_presentes = detectar_tipos_documento_presentes(documentos)
            
            # Validar requisitos contra documentos presentes
            resultado.tdr_observaciones = validar_requisitos_tdr(
                resultado.tdr_requisitos,
                docs_presentes,
                doc_tdr.nombre
            )
            
            if verbose and resultado.tdr_observaciones:
                print(f"      Observaciones TDR: {len(resultado.tdr_observaciones)}")
        else:
            if verbose:
                print("      ⚠️ No se encontró documento TDR")
    else:
        if verbose:
            print("   ⏭️ TDR no validado (no es primera armada)")
    
    # Consolidar observaciones
    resultado.todas_observaciones = resultado.spot_observaciones + resultado.tdr_observaciones
    
    if verbose:
        print(f"   ✅ Reglas adicionales completadas: {len(resultado.todas_observaciones)} observaciones")
    
    return resultado


# =============================================================================
# FUNCIÓN PARA INTEGRAR EN ORQUESTADOR
# =============================================================================

def crear_resultado_agente_reglas(
    documentos: List[DocumentoPDF],
    es_primera_armada: bool = True,
    naturaleza: NaturalezaExpediente = None
) -> ResultadoAgente:
    """
    Crea un ResultadoAgente compatible con el orquestador.
    
    Uso en orquestador.py:
        from src.rules.integrador import crear_resultado_agente_reglas
        
        resultado_reglas = crear_resultado_agente_reglas(
            self.documentos,
            self.es_primera_armada,
            self.naturaleza
        )
        self.resultados_agentes.append(resultado_reglas)
    """
    resultado = ejecutar_validacion_spot_tdr(
        documentos,
        es_primera_armada,
        naturaleza,
        verbose=False
    )
    
    return resultado.to_resultado_agente()


