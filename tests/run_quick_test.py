# -*- coding: utf-8 -*-
"""Test rapido de los FIX aplicados"""
import sys
import os

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import NaturalezaExpediente, TipoProcedimiento

def test_fix1_agente_legal():
    """FIX #1: agente_04_legal.py"""
    print("\n" + "=" * 60)
    print("FIX #1: agente_04_legal.py - Requisitos por naturaleza")
    print("=" * 60)
    
    from agentes.agente_04_legal import AgenteLegal
    agente = AgenteLegal()
    
    # Test 1: OS no debe requerir Guía Remisión
    requisitos_os = agente._obtener_requisitos(
        NaturalezaExpediente.ORDEN_SERVICIO, 
        TipoProcedimiento.MENOR_8_UIT
    )
    nombres_os = [r.nombre for r in requisitos_os]
    print(f"OS requisitos: {nombres_os}")
    
    assert "Guía Remisión" not in nombres_os, "FALLO: OS no debe requerir Guía Remisión"
    assert "Conformidad Almacén" not in nombres_os, "FALLO: OS no debe requerir Conformidad Almacén"
    print("✅ OS no requiere Guía Remisión ni Conformidad Almacén")
    
    # Test 2: OC sí debe requerir Guía Remisión
    requisitos_oc = agente._obtener_requisitos(
        NaturalezaExpediente.ORDEN_COMPRA, 
        TipoProcedimiento.MENOR_8_UIT
    )
    nombres_oc = [r.nombre for r in requisitos_oc]
    print(f"OC requisitos: {nombres_oc}")
    
    assert "Guía Remisión" in nombres_oc, "FALLO: OC debe requerir Guía Remisión"
    assert "Conformidad Almacén" in nombres_oc, "FALLO: OC debe requerir Conformidad Almacén"
    print("✅ OC sí requiere Guía Remisión y Conformidad Almacén")
    
    # Test 3: OS mapea a Pautas
    directiva = agente._determinar_directiva(NaturalezaExpediente.ORDEN_SERVICIO)
    assert "Pautas" in directiva, "FALLO: OS debe mapear a Pautas"
    print(f"✅ OS mapea a: {directiva}")
    
    print("\n✅ FIX #1 COMPLETADO")


def test_fix2_agente_integridad():
    """FIX #2: agente_06_integridad.py"""
    print("\n" + "=" * 60)
    print("FIX #2: agente_06_integridad.py - Matrices OS/OC + armada")
    print("=" * 60)
    
    from agentes.agente_06_integridad import AgenteIntegridad
    agente = AgenteIntegridad()
    
    # Test 1: OS primera armada no requiere Guía
    docs_os = agente._obtener_docs_esperados(
        NaturalezaExpediente.ORDEN_SERVICIO,
        TipoProcedimiento.MENOR_8_UIT,
        es_primera_armada=True
    )
    nombres_os = [d.nombre for d in docs_os]
    print(f"OS primera armada docs: {nombres_os}")
    
    assert "Guía de Remisión" not in nombres_os, "FALLO: OS no debe requerir Guía"
    assert "Conformidad Almacén" not in nombres_os, "FALLO: OS no debe requerir Conformidad Almacén"
    print("✅ OS no requiere documentos de bienes")
    
    # Test 2: OC sí requiere Guía
    docs_oc = agente._obtener_docs_esperados(
        NaturalezaExpediente.ORDEN_COMPRA,
        TipoProcedimiento.MENOR_8_UIT,
        es_primera_armada=True
    )
    nombres_oc = [d.nombre for d in docs_oc]
    print(f"OC primera armada docs: {nombres_oc}")
    
    assert "Guía de Remisión" in nombres_oc, "FALLO: OC debe requerir Guía"
    assert "Conformidad Almacén" in nombres_oc, "FALLO: OC debe requerir Conformidad Almacén"
    print("✅ OC sí requiere documentos de bienes")
    
    print("\n✅ FIX #2 COMPLETADO")


def test_fix3_agente_penalidades():
    """FIX #3: agente_07_penalidades.py"""
    print("\n" + "=" * 60)
    print("FIX #3: agente_07_penalidades.py - Patrones de penalidad")
    print("=" * 60)
    
    from agentes.agente_07_penalidades import AgentePenalidades
    agente = AgentePenalidades()
    
    # Mock de documentos con "SE RECOMIENDA APLICAR PENALIDAD"
    class MockDoc:
        def __init__(self, nombre, texto):
            self.nombre = nombre
            self.texto_completo = texto
            self.num_paginas = 1
    
    docs = [
        MockDoc("CONFORMIDAD-00889.pdf", """
            CONFORMIDAD DE SERVICIO
            SE RECOMIENDA APLICAR PENALIDAD por entrega fuera de plazo.
            Días de atraso: 3 días calendarios
        """),
        MockDoc("INFORME_TECNICO-01680.pdf", """
            INFORME TÉCNICO
            Corresponde aplicar penalidad por mora según cláusula.
            Cálculo de penalidad: S/ 112.50
        """)
    ]
    
    # Test 1: Detecta documentación de penalidad
    documentacion_ok = agente._verificar_documentacion_penalidad(docs)
    assert documentacion_ok, "FALLO: Debe detectar documentación de penalidad"
    print("✅ Detecta 'SE RECOMIENDA APLICAR PENALIDAD'")
    
    # Test 2: Info conformidad detecta SI penalidad
    info = agente._extraer_info_conformidad(docs)
    print(f"Info conformidad: {info}")
    assert info.get("menciona_si_penalidad", False), "FALLO: Debe detectar que SÍ aplica"
    print("✅ Detecta que SÍ aplica penalidad")
    
    print("\n✅ FIX #3 COMPLETADO")


def test_fix4_deteccion_conformidad():
    """FIX #4: Detección robusta de conformidad"""
    print("\n" + "=" * 60)
    print("FIX #4: Detección robusta de Conformidad")
    print("=" * 60)
    
    from agentes.agente_06_integridad import AgenteIntegridad
    agente = AgenteIntegridad()
    
    class MockDoc:
        def __init__(self, nombre, texto):
            self.nombre = nombre
            self.texto_completo = texto
            self.num_paginas = 1
    
    # Test 1: Detecta por nombre de archivo
    docs = [MockDoc("CONFORMIDAD-00889-2025-MINEDU.pdf", "")]
    docs_esperados = agente._obtener_docs_esperados(
        NaturalezaExpediente.ORDEN_SERVICIO,
        TipoProcedimiento.MENOR_8_UIT,
        es_primera_armada=True
    )
    
    verificacion = agente._verificar_documentos(docs, docs_esperados)
    encontrado = verificacion.get("Conformidad", {}).get("encontrado", False)
    assert encontrado, "FALLO: Debe detectar Conformidad por nombre"
    print("✅ Detecta Conformidad por nombre de archivo")
    
    # Test 2: Detecta por texto
    docs2 = [MockDoc("documento.pdf", "Se otorga la CONFORMIDAD del servicio")]
    verificacion2 = agente._verificar_documentos(docs2, docs_esperados)
    encontrado2 = verificacion2.get("Conformidad", {}).get("encontrado", False)
    assert encontrado2, "FALLO: Debe detectar Conformidad por texto"
    print("✅ Detecta Conformidad por texto")
    
    print("\n✅ FIX #4 COMPLETADO")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("TESTS RÁPIDOS DE LOS 4 FIX APLICADOS")
    print("=" * 70)
    
    try:
        test_fix1_agente_legal()
        test_fix2_agente_integridad()
        test_fix3_agente_penalidades()
        test_fix4_deteccion_conformidad()
        
        print("\n" + "=" * 70)
        print("✅✅✅ TODOS LOS FIX FUNCIONAN CORRECTAMENTE ✅✅✅")
        print("=" * 70)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ EXCEPCIÓN: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

