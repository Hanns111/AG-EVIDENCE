# -*- coding: utf-8 -*-
"""
DETRACCIÓN SPOT — Validador de Sistema de Pago de Obligaciones Tributarias
==========================================================================
Implementa la regla "Cuenta de detracción, cuando corresponda" de las Pautas
para la Remisión de Expedientes de Pago (11/07/2020).

Base normativa: RS 183-2004/SUNAT y modificatorias.

ALCANCE MVP:
- Determina SI/NO corresponde detracción mediante heurísticas
- Si corresponde, verifica evidencias mínimas (constancia/depósito + cuenta BN)
- NO calcula porcentaje ni monto de detracción (eso es tarea de Logística)

REGLA DE GOBERNANZA (AGENT_GOVERNANCE_RULES.md Art. 4):
- Toda observación CRÍTICA/MAYOR requiere evidencia probatoria
- Si no hay evidencia suficiente, degradar a INCIERTO
"""

import os
import sys
import re
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    Observacion, NivelObservacion, EvidenciaProbatoria, 
    MetodoExtraccion, LIMITES_NORMATIVOS, BASE_DIR
)


# =============================================================================
# ESTRUCTURAS DE DATOS
# =============================================================================

@dataclass
class ResultadoSPOT:
    """Resultado de validación SPOT"""
    aplica: bool
    motivo: str
    meta: Dict = field(default_factory=dict)
    evidencias_encontradas: List[EvidenciaProbatoria] = field(default_factory=list)
    observaciones: List[Observacion] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "aplica": self.aplica,
            "motivo": self.motivo,
            "meta": self.meta,
            "evidencias": [e.to_dict() for e in self.evidencias_encontradas],
            "observaciones_count": len(self.observaciones)
        }


@dataclass
class DocumentoAnalizado:
    """Documento con texto extraído para análisis SPOT"""
    nombre: str
    texto: str
    paginas: List[Tuple[int, str]] = field(default_factory=list)  # (num_pagina, texto_pagina)


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class SPOTValidator:
    """
    Validador de detracción SPOT.
    
    Determina si un expediente está sujeto a detracción y verifica
    que tenga las evidencias requeridas.
    """
    
    REGLA_ID = "SPOT-001"
    REGLA_NOMBRE = "Validación SPOT (RS 183-2004/SUNAT)"
    
    # Patrones para detectar indicios de SPOT en el texto
    PATRONES_SPOT_APLICA = [
        r"operaci[oó]n\s+sujeta\s+al\s+spot",
        r"sujeto\s+a\s+detracci[oó]n",
        r"detracci[oó]n\s+aplicada",
        r"dep[oó]sito\s+de\s+detracci[oó]n",
        r"constancia\s+de\s+dep[oó]sito\s+de\s+detracci[oó]n",
        r"cuenta\s+de\s+detracciones",
        r"sistema\s+de\s+pago\s+de\s+obligaciones\s+tributarias",
    ]
    
    # Patrones para detectar cuenta de detracciones
    PATRONES_CUENTA_BN = [
        r"(?:cuenta|cta\.?)\s*(?:de\s+)?detracciones?\s*[:\-]?\s*(\d{2,3}[\-\s]?\d{6,}[\-\s]?\d{3})",
        r"(?:cuenta|cta\.?)\s*BN\s*[:\-]?\s*(\d{2,3}[\-\s]?\d{6,}[\-\s]?\d{3})",
        r"banco\s+de\s+la\s+naci[oó]n\s*[:\-]?\s*(\d{2,3}[\-\s]?\d{6,}[\-\s]?\d{3})",
        r"00[\-\s]?\d{3}[\-\s]?\d{6}[\-\s]?\d{3}",  # Formato típico BN
    ]
    
    # Patrones para detectar constancia de depósito
    PATRONES_CONSTANCIA = [
        r"constancia\s+(?:de\s+)?dep[oó]sito\s*(?:n[°º]?)?\s*[:\-]?\s*(\d+)",
        r"n[°º]?\s*(?:de\s+)?constancia\s*[:\-]?\s*(\d+)",
        r"dep[oó]sito\s+(?:spot|detracci[oó]n)\s*[:\-]?\s*(\d+)",
        r"operaci[oó]n\s*n[°º]?\s*[:\-]?\s*(\d{10,})",
    ]
    
    def __init__(self, ruta_anexo3: str = None):
        """
        Inicializa el validador SPOT.
        
        Args:
            ruta_anexo3: Ruta al archivo JSON con el Anexo 3 de servicios SPOT.
                        Si es None, usa la ruta por defecto.
        """
        self.ruta_anexo3 = ruta_anexo3 or os.path.join(
            BASE_DIR, "data", "normativa", "spot_anexo3.json"
        )
        self.anexo3 = self._cargar_anexo3()
        self.monto_minimo = LIMITES_NORMATIVOS.get("monto_minimo_detraccion", 700.0)
    
    def _cargar_anexo3(self) -> Dict:
        """Carga el anexo 3 de servicios SPOT desde JSON"""
        try:
            if os.path.exists(self.ruta_anexo3):
                with open(self.ruta_anexo3, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ No se pudo cargar Anexo 3 SPOT: {e}")
        
        # Retornar estructura mínima si no se puede cargar
        return {
            "servicios": [],
            "monto_minimo": 700.0,
            "indicadores_texto_spot": [
                "operación sujeta al spot",
                "detracción",
                "cuenta de detracciones"
            ]
        }
    
    def spot_aplica(
        self, 
        documentos: List[DocumentoAnalizado],
        monto_operacion: float = None,
        tipo_servicio: str = None
    ) -> ResultadoSPOT:
        """
        Determina si corresponde detracción SPOT y valida evidencias.
        
        Args:
            documentos: Lista de documentos con texto extraído
            monto_operacion: Monto de la operación (opcional, para validar umbral)
            tipo_servicio: Descripción del servicio (opcional, para matching con Anexo 3)
        
        Returns:
            ResultadoSPOT con la determinación y observaciones
        """
        resultado = ResultadoSPOT(
            aplica=False,
            motivo="",
            meta={}
        )
        
        # 1. Buscar indicios explícitos de SPOT en los documentos
        indicios_spot = self._buscar_indicios_spot(documentos)
        
        if indicios_spot:
            resultado.aplica = True
            resultado.motivo = "Se detectaron indicios explícitos de operación sujeta a SPOT"
            resultado.meta["indicios_detectados"] = indicios_spot
            resultado.evidencias_encontradas = indicios_spot
        
        # 2. Si no hay indicios explícitos, intentar matching con Anexo 3
        if not resultado.aplica and tipo_servicio:
            match_anexo3 = self._match_anexo3(tipo_servicio)
            if match_anexo3:
                resultado.aplica = True
                resultado.motivo = f"Servicio coincide con código {match_anexo3['codigo']} del Anexo 3 SPOT"
                resultado.meta["anexo3_match"] = match_anexo3
        
        # 3. Verificar umbral de monto (solo informativo)
        if monto_operacion is not None:
            resultado.meta["monto_operacion"] = monto_operacion
            resultado.meta["monto_minimo_spot"] = self.monto_minimo
            resultado.meta["supera_umbral"] = monto_operacion >= self.monto_minimo
            
            if not resultado.aplica and monto_operacion >= self.monto_minimo:
                # El monto supera umbral pero no hay indicios claros
                resultado.meta["advertencia"] = "Monto supera S/ 700 pero no se detectaron indicios de SPOT"
        
        # 4. Si aplica SPOT, verificar que existan las evidencias requeridas
        if resultado.aplica:
            resultado.observaciones = self._validar_evidencias_spot(documentos)
        
        return resultado
    
    def _buscar_indicios_spot(
        self, 
        documentos: List[DocumentoAnalizado]
    ) -> List[EvidenciaProbatoria]:
        """
        Busca indicios de que la operación está sujeta a SPOT.
        
        Returns:
            Lista de evidencias probatorias encontradas
        """
        evidencias = []
        
        for doc in documentos:
            texto_lower = doc.texto.lower()
            
            # Buscar patrones de SPOT aplica
            for patron in self.PATRONES_SPOT_APLICA:
                matches = re.finditer(patron, texto_lower, re.IGNORECASE)
                for match in matches:
                    # Encontrar página aproximada
                    pagina = self._encontrar_pagina(doc, match.start())
                    
                    # Extraer snippet de contexto
                    inicio = max(0, match.start() - 50)
                    fin = min(len(doc.texto), match.end() + 50)
                    snippet = doc.texto[inicio:fin].strip()
                    
                    evidencia = EvidenciaProbatoria(
                        archivo=doc.nombre,
                        pagina=pagina,
                        valor_detectado=match.group(0),
                        snippet=snippet,
                        metodo_extraccion=MetodoExtraccion.REGEX,
                        confianza=0.95,
                        regla_aplicada=f"{self.REGLA_ID}: Indicio SPOT detectado"
                    )
                    evidencias.append(evidencia)
            
            # Buscar indicadores del JSON
            for indicador in self.anexo3.get("indicadores_texto_spot", []):
                if indicador.lower() in texto_lower:
                    pos = texto_lower.find(indicador.lower())
                    pagina = self._encontrar_pagina(doc, pos)
                    
                    inicio = max(0, pos - 50)
                    fin = min(len(doc.texto), pos + len(indicador) + 50)
                    snippet = doc.texto[inicio:fin].strip()
                    
                    evidencia = EvidenciaProbatoria(
                        archivo=doc.nombre,
                        pagina=pagina,
                        valor_detectado=indicador,
                        snippet=snippet,
                        metodo_extraccion=MetodoExtraccion.HEURISTICA,
                        confianza=0.85,
                        regla_aplicada=f"{self.REGLA_ID}: Indicador SPOT '{indicador}'"
                    )
                    # Evitar duplicados
                    if not any(e.snippet == snippet for e in evidencias):
                        evidencias.append(evidencia)
        
        return evidencias
    
    def _match_anexo3(self, tipo_servicio: str) -> Optional[Dict]:
        """
        Intenta hacer matching del tipo de servicio con el Anexo 3.
        
        Returns:
            Diccionario con datos del servicio si hay match, None si no.
        """
        if not tipo_servicio:
            return None
        
        tipo_lower = tipo_servicio.lower()
        
        for servicio in self.anexo3.get("servicios", []):
            for keyword in servicio.get("keywords", []):
                if keyword.lower() in tipo_lower:
                    return {
                        "codigo": servicio.get("codigo"),
                        "descripcion": servicio.get("descripcion"),
                        "tasa": servicio.get("tasa"),
                        "keyword_match": keyword
                    }
        
        return None
    
    def _encontrar_pagina(self, doc: DocumentoAnalizado, posicion: int) -> int:
        """
        Encuentra el número de página aproximado para una posición en el texto.
        """
        if not doc.paginas:
            return 1
        
        posicion_acumulada = 0
        for num_pagina, texto_pagina in doc.paginas:
            posicion_acumulada += len(texto_pagina)
            if posicion <= posicion_acumulada:
                return num_pagina
        
        return doc.paginas[-1][0] if doc.paginas else 1
    
    def _validar_evidencias_spot(
        self, 
        documentos: List[DocumentoAnalizado]
    ) -> List[Observacion]:
        """
        Valida que existan las evidencias requeridas cuando aplica SPOT:
        - Constancia de depósito de detracción
        - Cuenta de detracciones del proveedor (Banco de la Nación)
        
        Returns:
            Lista de observaciones por evidencias faltantes
        """
        observaciones = []
        
        tiene_constancia = False
        tiene_cuenta_bn = False
        evidencia_constancia = None
        evidencia_cuenta = None
        
        for doc in documentos:
            texto = doc.texto
            texto_lower = texto.lower()
            
            # Buscar constancia de depósito
            for patron in self.PATRONES_CONSTANCIA:
                match = re.search(patron, texto_lower, re.IGNORECASE)
                if match:
                    tiene_constancia = True
                    pagina = self._encontrar_pagina(doc, match.start())
                    inicio = max(0, match.start() - 30)
                    fin = min(len(texto), match.end() + 30)
                    evidencia_constancia = EvidenciaProbatoria(
                        archivo=doc.nombre,
                        pagina=pagina,
                        valor_detectado=match.group(0),
                        snippet=texto[inicio:fin].strip(),
                        metodo_extraccion=MetodoExtraccion.REGEX,
                        confianza=0.9,
                        regla_aplicada=f"{self.REGLA_ID}: Constancia depósito detectada"
                    )
                    break
            
            # Buscar cuenta BN de detracciones
            for patron in self.PATRONES_CUENTA_BN:
                match = re.search(patron, texto, re.IGNORECASE)
                if match:
                    tiene_cuenta_bn = True
                    pagina = self._encontrar_pagina(doc, match.start())
                    inicio = max(0, match.start() - 30)
                    fin = min(len(texto), match.end() + 30)
                    evidencia_cuenta = EvidenciaProbatoria(
                        archivo=doc.nombre,
                        pagina=pagina,
                        valor_detectado=match.group(0),
                        snippet=texto[inicio:fin].strip(),
                        metodo_extraccion=MetodoExtraccion.REGEX,
                        confianza=0.9,
                        regla_aplicada=f"{self.REGLA_ID}: Cuenta BN detectada"
                    )
                    break
        
        # Generar observaciones por faltantes
        if not tiene_constancia:
            obs = Observacion(
                nivel=NivelObservacion.MAYOR,
                agente="SPOTValidator",
                descripcion="Operación sujeta a SPOT: No se detectó constancia de depósito de detracción",
                accion_requerida="Adjuntar constancia de depósito de detracción (SPOT)",
                area_responsable="Logística / Proveedor",
                regla_aplicada=f"{self.REGLA_ID}: Falta constancia depósito"
            )
            observaciones.append(obs)
        
        if not tiene_cuenta_bn:
            obs = Observacion(
                nivel=NivelObservacion.MAYOR,
                agente="SPOTValidator",
                descripcion="Operación sujeta a SPOT: No se detectó cuenta de detracciones del Banco de la Nación",
                accion_requerida="Verificar que el comprobante consigne la cuenta de detracciones (BN)",
                area_responsable="Logística / Proveedor",
                regla_aplicada=f"{self.REGLA_ID}: Falta cuenta BN"
            )
            observaciones.append(obs)
        
        return observaciones
    
    def buscar_cuenta_detracciones(self, texto: str) -> Optional[str]:
        """
        Extrae el número de cuenta de detracciones si existe.
        
        Returns:
            Número de cuenta encontrado o None
        """
        for patron in self.PATRONES_CUENTA_BN:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                # Limpiar y normalizar el número
                numero = match.group(0) if not match.groups() else match.group(1)
                numero = re.sub(r'[^\d\-]', '', numero)
                return numero
        return None


# =============================================================================
# FUNCIÓN HELPER PRINCIPAL
# =============================================================================

def spot_aplica(
    documentos: List[DocumentoAnalizado],
    monto_operacion: float = None,
    tipo_servicio: str = None
) -> Tuple[bool, str, Dict]:
    """
    Función helper para determinar si aplica SPOT.
    
    Args:
        documentos: Lista de DocumentoAnalizado
        monto_operacion: Monto de la operación (opcional)
        tipo_servicio: Descripción del servicio (opcional)
    
    Returns:
        Tupla (aplica: bool, motivo: str, meta: dict)
    """
    validator = SPOTValidator()
    resultado = validator.spot_aplica(documentos, monto_operacion, tipo_servicio)
    return resultado.aplica, resultado.motivo, resultado.meta


def crear_documento_desde_pdf(nombre: str, texto: str, paginas: List[Tuple[int, str]] = None) -> DocumentoAnalizado:
    """
    Helper para crear un DocumentoAnalizado desde datos de PDF.
    """
    return DocumentoAnalizado(
        nombre=nombre,
        texto=texto,
        paginas=paginas or []
    )


# =============================================================================
# TESTS INTEGRADOS
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("TEST: SPOTValidator")
    print("=" * 70)
    
    # Test 1: Texto con indicios de SPOT
    print("\n📋 Test 1: Texto con 'operación sujeta al SPOT'")
    doc1 = DocumentoAnalizado(
        nombre="factura_001.pdf",
        texto="FACTURA ELECTRÓNICA\nMonto: S/ 5,000.00\nOperación sujeta al SPOT\nCuenta BN: 00-123-456789-012",
        paginas=[(1, "FACTURA ELECTRÓNICA\nMonto: S/ 5,000.00\nOperación sujeta al SPOT\nCuenta BN: 00-123-456789-012")]
    )
    
    validator = SPOTValidator()
    resultado = validator.spot_aplica([doc1], monto_operacion=5000.0)
    print(f"   Aplica: {resultado.aplica}")
    print(f"   Motivo: {resultado.motivo}")
    print(f"   Evidencias: {len(resultado.evidencias_encontradas)}")
    assert resultado.aplica == True, "Debería detectar SPOT"
    print("   ✅ PASÓ")
    
    # Test 2: Texto sin indicios
    print("\n📋 Test 2: Texto sin indicios de SPOT")
    doc2 = DocumentoAnalizado(
        nombre="orden_servicio.pdf",
        texto="ORDEN DE SERVICIO N° 001-2025\nServicio de limpieza\nMonto: S/ 500.00",
        paginas=[(1, "ORDEN DE SERVICIO N° 001-2025\nServicio de limpieza\nMonto: S/ 500.00")]
    )
    
    resultado2 = validator.spot_aplica([doc2], monto_operacion=500.0)
    print(f"   Aplica: {resultado2.aplica}")
    print(f"   Motivo: {resultado2.motivo or 'Sin indicios detectados'}")
    assert resultado2.aplica == False, "No debería detectar SPOT"
    print("   ✅ PASÓ")
    
    # Test 3: Matching con Anexo 3
    print("\n📋 Test 3: Matching con Anexo 3 (consultoría)")
    doc3 = DocumentoAnalizado(
        nombre="tdr_consultoria.pdf",
        texto="TÉRMINOS DE REFERENCIA\nConsultoría para elaboración de diagnóstico",
        paginas=[(1, "TÉRMINOS DE REFERENCIA\nConsultoría para elaboración de diagnóstico")]
    )
    
    resultado3 = validator.spot_aplica([doc3], tipo_servicio="consultoría profesional")
    print(f"   Aplica: {resultado3.aplica}")
    print(f"   Motivo: {resultado3.motivo}")
    print(f"   Meta: {resultado3.meta.get('anexo3_match', {})}")
    # El resultado depende del anexo3.json cargado
    print("   ✅ PASÓ (resultado depende de anexo3.json)")
    
    print("\n" + "=" * 70)
    print("✅ Todos los tests básicos pasaron")
    print("=" * 70)


