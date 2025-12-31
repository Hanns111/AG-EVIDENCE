# -*- coding: utf-8 -*-
"""
TESTS DE ENRUTAMIENTO OS vs OC + PAUTAS + PENALIDAD
===================================================
Tests basados en expediente real OTIC2025-INT-0984759 (SINAD 0984759)

EVIDENCIA PROBATORIA:
- Expediente: ORDEN DE SERVICIO 12640-2025
- Armada: 1 de 2 (primera armada)
- Conformidad: 00889-2025-MINEDU
- Informe Técnico: 01680-2025-MINEDU

CRITERIOS DE ACEPTACIÓN:
1. Naturaleza detectada = ORDEN_SERVICIO (servicios)
2. No debe existir observación crítica "Guía Remisión"
3. No debe existir observación crítica "Conformidad Almacén"
4. "Conformidad" debe detectarse como presente
5. Penalidad debe detectarse como documentada
6. Decisión NO debe ser "NO PROCEDE" por requisitos de bienes
"""

import os
import sys
import pytest
from dataclasses import dataclass
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    NaturalezaExpediente, TipoProcedimiento, NivelObservacion
)
from agentes.agente_04_legal import AgenteLegal, RequisitoDocumental
from agentes.agente_06_integridad import AgenteIntegridad, DocumentoEsperado
from agentes.agente_07_penalidades import AgentePenalidades
from utils.pdf_extractor import DocumentoPDF


# =============================================================================
# FIXTURES: Datos del expediente real SINAD 0984759
# =============================================================================

@dataclass
class MockDocumentoPDF:
    """Mock de DocumentoPDF para tests"""
    nombre: str
    texto_completo: str
    num_paginas: int = 1


@pytest.fixture
def documentos_expediente_os():
    """
    Mock de documentos del expediente real SINAD 0984759
    
    Evidencia:
    - CONFORMIDAD-00889-2025-MINEDU: Conformidad del servicio
    - INFORME_TECNICO-01680-2025-MINEDU: Informe técnico con análisis de penalidad
    """
    return [
        MockDocumentoPDF(
            nombre="CONFORMIDAD-00889-2025-MINEDU-SPE-OTIC-USAU.pdf",
            texto_completo="""
            CONFORMIDAD DE SERVICIO N° 00889-2025-MINEDU-SPE-OTIC-USAU
            
            Orden de Servicio N° 12640-2025
            Armada 1 de 2
            
            El suscrito, en calidad de responsable del área usuaria, otorga 
            la CONFORMIDAD al servicio prestado por el contratista.
            
            RESPECTO A PENALIDADES:
            SE RECOMIENDA APLICAR PENALIDAD por entrega fuera de plazo.
            Fecha de entrega pactada: 30/11/2025
            Fecha de entrega real: 03/12/2025
            Días de atraso: 3 días calendarios
            
            Monto del servicio: S/ 15,000.00
            CCI autorizado del proveedor registrado en el sistema.
            """
        ),
        MockDocumentoPDF(
            nombre="INFORME_TECNICO-01680-2025-MINEDU-SPE-OTIC.pdf",
            texto_completo="""
            INFORME TÉCNICO N° 01680-2025-MINEDU-SPE-OTIC
            
            ASUNTO: Evaluación del servicio OS 0012640-2025
            
            1. ANTECEDENTES
            Mediante Orden de Servicio N° 0012640-2025 se contrató el servicio
            de soporte técnico especializado.
            
            2. ANÁLISIS
            El contratista presentó el entregable el 03/12/2025, cuando el plazo
            vencía el 30/11/2025, configurándose un atraso de 3 días calendario.
            
            3. SOBRE PENALIDADES
            Corresponde aplicar penalidad por mora según cláusula contractual.
            Cálculo de penalidad: S/ 112.50
            
            4. CONCLUSIÓN
            Se recomienda aplicar penalidad y proceder con el pago descontando
            el monto correspondiente.
            
            Términos de Referencia adjuntos.
            Factura del proveedor verificada.
            """
        ),
        MockDocumentoPDF(
            nombre="OS-12640-2025.pdf",
            texto_completo="""
            ORDEN DE SERVICIO N° 12640-2025
            
            Proveedor: EMPRESA DE TECNOLOGÍA S.A.C.
            RUC: 20123456789
            
            Servicio: Soporte técnico especializado
            Monto: S/ 15,000.00 (Quince mil y 00/100 soles)
            Plazo: 30 días calendario
            
            Cuenta CCI del proveedor autorizada.
            """
        ),
        MockDocumentoPDF(
            nombre="TDR-SERVICIO-SOPORTE.pdf",
            texto_completo="""
            TÉRMINOS DE REFERENCIA
            
            Contratación del servicio de soporte técnico especializado
            para la Oficina de Tecnologías de la Información.
            
            Experiencia requerida: 3 años en servicios similares
            Perfil profesional: Ingeniero de sistemas o afín
            """
        ),
        MockDocumentoPDF(
            nombre="FACTURA-F001-00123.pdf",
            texto_completo="""
            FACTURA ELECTRÓNICA
            F001-00123
            
            RUC: 20123456789
            Razón Social: EMPRESA DE TECNOLOGÍA S.A.C.
            
            Servicio de soporte técnico
            Subtotal: S/ 12,711.86
            IGV (18%): S/ 2,288.14
            Total: S/ 15,000.00
            """
        ),
        MockDocumentoPDF(
            nombre="CCP-2025-00456.pdf",
            texto_completo="""
            CERTIFICACIÓN DE CRÉDITO PRESUPUESTARIO
            CCP N° 2025-00456
            
            Se certifica la disponibilidad presupuestal para la 
            Orden de Servicio N° 12640-2025.
            
            Monto certificado: S/ 15,000.00
            """
        ),
    ]


@pytest.fixture
def documentos_expediente_oc():
    """Mock de documentos para expediente de BIENES (OC)"""
    return [
        MockDocumentoPDF(
            nombre="OC-2025-00789.pdf",
            texto_completo="""
            ORDEN DE COMPRA N° 2025-00789
            
            Adquisición de equipos de cómputo
            Proveedor: DISTRIBUIDORA TECH S.A.C.
            Monto: S/ 50,000.00
            """
        ),
        MockDocumentoPDF(
            nombre="GUIA-REMISION-001-12345.pdf",
            texto_completo="""
            GUÍA DE REMISIÓN
            Serie: 001
            Número: 12345
            
            Destinatario: MINEDU
            Bienes: 10 laptops modelo XYZ
            """
        ),
        MockDocumentoPDF(
            nombre="CONFORMIDAD-ALMACEN-2025-00456.pdf",
            texto_completo="""
            CONFORMIDAD DE INGRESO A ALMACÉN
            N° 2025-00456
            
            Se verifica el ingreso de los bienes según PECOSA.
            """
        ),
    ]


# =============================================================================
# TESTS: FIX #1 - agente_04_legal.py
# =============================================================================

class TestAgenteLegalOSvsOC:
    """Tests para verificar que OS nunca hereda requisitos de OC"""
    
    def test_os_no_requiere_guia_remision(self, documentos_expediente_os):
        """
        CRÍTICO: ORDEN_SERVICIO no debe requerir 'Guía Remisión'
        """
        agente = AgenteLegal()
        requisitos = agente._obtener_requisitos(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        nombres_requisitos = [r.nombre for r in requisitos]
        
        assert "Guía Remisión" not in nombres_requisitos, \
            f"ORDEN_SERVICIO no debe requerir 'Guía Remisión'. Requisitos: {nombres_requisitos}"
    
    def test_os_no_requiere_conformidad_almacen(self, documentos_expediente_os):
        """
        CRÍTICO: ORDEN_SERVICIO no debe requerir 'Conformidad Almacén'
        """
        agente = AgenteLegal()
        requisitos = agente._obtener_requisitos(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        nombres_requisitos = [r.nombre for r in requisitos]
        
        assert "Conformidad Almacén" not in nombres_requisitos, \
            f"ORDEN_SERVICIO no debe requerir 'Conformidad Almacén'. Requisitos: {nombres_requisitos}"
    
    def test_os_no_requiere_contrato_menor_8uit(self, documentos_expediente_os):
        """
        CRÍTICO: ORDEN_SERVICIO menor a 8 UIT no debe requerir Contrato obligatorio
        """
        agente = AgenteLegal()
        requisitos = agente._obtener_requisitos(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        # Buscar si Contrato es obligatorio
        contrato_obligatorio = any(
            r.nombre == "Contrato" and r.obligatorio 
            for r in requisitos
        )
        
        assert not contrato_obligatorio, \
            "ORDEN_SERVICIO menor a 8 UIT no debe requerir Contrato obligatorio"
    
    def test_oc_si_requiere_guia_remision(self, documentos_expediente_oc):
        """
        VERIFICACIÓN: ORDEN_COMPRA sí debe requerir 'Guía Remisión'
        """
        agente = AgenteLegal()
        requisitos = agente._obtener_requisitos(
            NaturalezaExpediente.ORDEN_COMPRA,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        nombres_requisitos = [r.nombre for r in requisitos]
        
        assert "Guía Remisión" in nombres_requisitos, \
            f"ORDEN_COMPRA debe requerir 'Guía Remisión'. Requisitos: {nombres_requisitos}"
    
    def test_oc_si_requiere_conformidad_almacen(self, documentos_expediente_oc):
        """
        VERIFICACIÓN: ORDEN_COMPRA sí debe requerir 'Conformidad Almacén'
        """
        agente = AgenteLegal()
        requisitos = agente._obtener_requisitos(
            NaturalezaExpediente.ORDEN_COMPRA,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        nombres_requisitos = [r.nombre for r in requisitos]
        
        assert "Conformidad Almacén" in nombres_requisitos, \
            f"ORDEN_COMPRA debe requerir 'Conformidad Almacén'. Requisitos: {nombres_requisitos}"
    
    def test_os_mapea_a_pautas(self):
        """
        VERIFICACIÓN: ORDEN_SERVICIO debe mapear a 'Pautas para Remisión'
        """
        agente = AgenteLegal()
        directiva = agente._determinar_directiva(NaturalezaExpediente.ORDEN_SERVICIO)
        
        assert "Pautas" in directiva, \
            f"ORDEN_SERVICIO debe mapear a Pautas, no a '{directiva}'"


# =============================================================================
# TESTS: FIX #2 - agente_06_integridad.py
# =============================================================================

class TestAgenteIntegridadOSvsOC:
    """Tests para verificar matrices de documentos OS vs OC"""
    
    def test_os_primera_armada_no_requiere_guia(self, documentos_expediente_os):
        """
        CRÍTICO: Servicios primera armada no requiere Guía Remisión
        """
        agente = AgenteIntegridad()
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        nombres_docs = [d.nombre for d in docs_esperados]
        
        assert "Guía de Remisión" not in nombres_docs, \
            f"Servicios no debe requerir Guía. Docs: {nombres_docs}"
    
    def test_os_primera_armada_no_requiere_almacen(self, documentos_expediente_os):
        """
        CRÍTICO: Servicios primera armada no requiere Conformidad Almacén
        """
        agente = AgenteIntegridad()
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        nombres_docs = [d.nombre for d in docs_esperados]
        
        assert "Conformidad Almacén" not in nombres_docs, \
            f"Servicios no debe requerir Conformidad Almacén. Docs: {nombres_docs}"
    
    def test_os_detecta_conformidad_por_nombre(self, documentos_expediente_os):
        """
        CRÍTICO: Conformidad debe detectarse por nombre de archivo
        """
        agente = AgenteIntegridad()
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        # Convertir mocks a formato esperado
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        verificacion = agente._verificar_documentos(docs_mock, docs_esperados)
        
        # Verificar que Conformidad se detectó
        assert verificacion.get("Conformidad", {}).get("encontrado", False), \
            f"Conformidad 00889 debe detectarse. Verificación: {verificacion}"
    
    def test_oc_si_requiere_guia(self, documentos_expediente_oc):
        """
        VERIFICACIÓN: Bienes sí requiere Guía Remisión
        """
        agente = AgenteIntegridad()
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_COMPRA,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        nombres_docs = [d.nombre for d in docs_esperados]
        
        assert "Guía de Remisión" in nombres_docs, \
            f"Bienes debe requerir Guía. Docs: {nombres_docs}"


# =============================================================================
# TESTS: FIX #3 - agente_07_penalidades.py
# =============================================================================

class TestAgentePenalidadesPatrones:
    """Tests para verificar detección de penalidades"""
    
    def test_detecta_recomendacion_aplicar_penalidad(self, documentos_expediente_os):
        """
        CRÍTICO: Debe detectar 'SE RECOMIENDA APLICAR PENALIDAD'
        """
        agente = AgentePenalidades()
        
        # Convertir mocks
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        documentacion_ok = agente._verificar_documentacion_penalidad(docs_mock)
        
        assert documentacion_ok, \
            "Debe detectar que la penalidad está documentada (SE RECOMIENDA APLICAR)"
    
    def test_info_conformidad_detecta_si_penalidad(self, documentos_expediente_os):
        """
        CRÍTICO: _extraer_info_conformidad debe detectar que SÍ aplica penalidad
        """
        agente = AgentePenalidades()
        
        # Convertir mocks
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        info = agente._extraer_info_conformidad(docs_mock)
        
        assert info.get("menciona_si_penalidad", False), \
            f"Debe detectar que SÍ se recomienda aplicar penalidad. Info: {info}"
    
    def test_analisis_mora_con_penalidad_documentada(self, documentos_expediente_os):
        """
        CRÍTICO: Análisis de mora debe reconocer penalidad documentada
        """
        agente = AgentePenalidades()
        
        # Convertir mocks
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        resultado = agente.analizar(docs_mock)
        
        assert resultado.datos_extraidos.get("penalidad_documentada", False), \
            f"Penalidad debe estar documentada. Datos: {resultado.datos_extraidos}"


# =============================================================================
# TESTS: FIX #4 - Detección robusta de Conformidad
# =============================================================================

class TestDeteccionConformidadRobusta:
    """Tests para verificar detección robusta de conformidad"""
    
    def test_detecta_conformidad_por_nombre_archivo(self):
        """
        CRÍTICO: Conformidad debe detectarse por nombre 'CONFORMIDAD-00889...'
        """
        agente = AgenteIntegridad()
        
        docs = [
            type('DocumentoPDF', (), {
                'nombre': 'CONFORMIDAD-00889-2025-MINEDU.pdf',
                'texto_completo': '',  # Texto vacío para probar detección por nombre
                'num_paginas': 1
            })()
        ]
        
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        verificacion = agente._verificar_documentos(docs, docs_esperados)
        
        assert verificacion.get("Conformidad", {}).get("encontrado", False), \
            "Conformidad debe detectarse por nombre de archivo"
    
    def test_detecta_conformidad_por_texto(self):
        """
        VERIFICACIÓN: Conformidad también se detecta por contenido de texto
        """
        agente = AgenteIntegridad()
        
        docs = [
            type('DocumentoPDF', (), {
                'nombre': 'documento_generico.pdf',
                'texto_completo': 'Se otorga la CONFORMIDAD al servicio prestado',
                'num_paginas': 1
            })()
        ]
        
        docs_esperados = agente._obtener_docs_esperados(
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        verificacion = agente._verificar_documentos(docs, docs_esperados)
        
        assert verificacion.get("Conformidad", {}).get("encontrado", False), \
            "Conformidad debe detectarse por texto"


# =============================================================================
# TEST INTEGRACIÓN: Expediente completo no debe generar falsos críticos
# =============================================================================

class TestIntegracionExpedienteOS:
    """Test de integración con expediente real"""
    
    def test_expediente_os_no_genera_criticas_falsas(self, documentos_expediente_os):
        """
        TEST INTEGRACIÓN: Expediente OS no debe tener críticas por
        requisitos de bienes (Guía, Conformidad Almacén)
        """
        # Convertir mocks
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        # Ejecutar agente legal
        agente_legal = AgenteLegal()
        resultado_legal = agente_legal.analizar(
            docs_mock,
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT
        )
        
        # Verificar que no hay críticas por requisitos de bienes
        criticas_falsas = [
            obs for obs in resultado_legal.observaciones
            if obs.nivel == NivelObservacion.CRITICA and any(
                kw in obs.descripcion.lower() 
                for kw in ["guía", "guia", "almacén", "almacen"]
            )
        ]
        
        assert len(criticas_falsas) == 0, \
            f"No debe haber críticas por requisitos de bienes: {[c.descripcion for c in criticas_falsas]}"
    
    def test_expediente_os_detecta_conformidad(self, documentos_expediente_os):
        """
        TEST INTEGRACIÓN: Conformidad 00889 debe estar presente
        """
        # Convertir mocks
        docs_mock = []
        for d in documentos_expediente_os:
            doc = type('DocumentoPDF', (), {
                'nombre': d.nombre,
                'texto_completo': d.texto_completo,
                'num_paginas': d.num_paginas
            })()
            docs_mock.append(doc)
        
        # Ejecutar agente integridad
        agente = AgenteIntegridad()
        resultado = agente.analizar(
            docs_mock,
            NaturalezaExpediente.ORDEN_SERVICIO,
            TipoProcedimiento.MENOR_8_UIT,
            es_primera_armada=True
        )
        
        # Verificar que Conformidad no está en faltantes
        faltantes = resultado.datos_extraidos.get("documentos_faltantes", [])
        
        assert "Conformidad" not in faltantes, \
            f"Conformidad 00889 no debe figurar como faltante. Faltantes: {faltantes}"


# =============================================================================
# MAIN: Ejecutar tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])









