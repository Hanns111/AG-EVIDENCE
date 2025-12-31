# -*- coding: utf-8 -*-
"""
Tests unitarios para el módulo de requisitos TDR
================================================
Verifica la extracción y validación de requisitos del proveedor según TDR.
"""

import pytest
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rules.tdr_requirements import (
    TDRRequirementExtractor,
    extraer_requisitos_tdr,
    validar_requisitos_tdr,
    tdr_requiere_cv,
    tdr_requiere_experiencia,
    RequisitoTDR
)


class TestTDRRequirementExtractor:
    """Tests para TDRRequirementExtractor"""
    
    @pytest.fixture
    def extractor(self):
        """Fixture que crea un extractor"""
        return TDRRequirementExtractor()
    
    # =========================================================================
    # TEST: Detección de CV
    # =========================================================================
    
    def test_detecta_cv_explicito(self, extractor):
        """
        CASO: TDR menciona 'presentar currículum vitae'
        ESPERADO: Requisito CV detectado
        """
        texto = """
        TÉRMINOS DE REFERENCIA
        
        PERFIL DEL CONSULTOR:
        - Presentar currículum vitae documentado
        - Experiencia en el sector
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_cv() == True
        assert any(r.tipo == "CV" for r in resultado.requisitos)
    
    def test_detecta_cv_abreviado(self, extractor):
        """
        CASO: TDR menciona 'CV'
        ESPERADO: Requisito CV detectado
        """
        texto = """
        Requisitos del postor:
        - Adjuntar CV actualizado
        - Copia de DNI
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_cv() == True
    
    def test_detecta_hoja_de_vida(self, extractor):
        """
        CASO: TDR menciona 'hoja de vida'
        ESPERADO: Requisito CV detectado
        """
        texto = """
        El consultor deberá presentar su hoja de vida documentada
        con experiencia comprobable.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_cv() == True
    
    def test_no_detecta_cv_si_no_menciona(self, extractor):
        """
        CASO: TDR NO menciona CV ni currículum
        ESPERADO: NO se detecta requisito CV
        """
        texto = """
        TÉRMINOS DE REFERENCIA
        SERVICIO DE LIMPIEZA
        
        I. OBJETO
        Contratación del servicio de limpieza.
        
        II. PLAZO
        30 días calendario.
        
        III. FORMA DE PAGO
        Pago contra conformidad.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_cv() == False
    
    # =========================================================================
    # TEST: Detección de experiencia
    # =========================================================================
    
    def test_detecta_experiencia_anios(self, extractor):
        """
        CASO: TDR menciona 'experiencia mínima de 5 años'
        ESPERADO: Requisito EXPERIENCIA detectado
        """
        texto = """
        PERFIL DEL CONSULTOR:
        - Experiencia profesional mínima de 5 años en el sector
        - Conocimiento de normativa
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_experiencia() == True
        exp = [r for r in resultado.requisitos if r.tipo == "EXPERIENCIA"]
        assert len(exp) > 0
    
    def test_detecta_acreditar_experiencia(self, extractor):
        """
        CASO: TDR menciona 'acreditar experiencia'
        ESPERADO: Requisito EXPERIENCIA detectado
        """
        texto = """
        El postor deberá acreditar experiencia en proyectos similares
        mediante contratos u órdenes de servicio.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_experiencia() == True
    
    def test_no_detecta_experiencia_si_no_menciona(self, extractor):
        """
        CASO: TDR NO menciona experiencia
        ESPERADO: NO se detecta requisito EXPERIENCIA
        """
        texto = """
        SERVICIO DE ALQUILER DE EQUIPOS
        
        Se requiere alquiler de 10 laptops por 3 meses.
        El proveedor entregará los equipos en la sede central.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_experiencia() == False
    
    # =========================================================================
    # TEST: Detección de título profesional
    # =========================================================================
    
    def test_detecta_titulo_profesional(self, extractor):
        """
        CASO: TDR menciona 'título profesional'
        ESPERADO: Requisito TITULO detectado
        """
        texto = """
        Requisitos:
        - Título profesional de Ingeniero de Sistemas o afines
        - Colegiatura vigente
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_titulo() == True
    
    def test_detecta_grado_bachiller(self, extractor):
        """
        CASO: TDR menciona 'bachiller'
        ESPERADO: Requisito TITULO detectado
        """
        texto = """
        El consultor debe contar con grado de bachiller en
        Administración, Economía o carreras afines.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert resultado.tiene_requisito_titulo() == True
    
    # =========================================================================
    # TEST: Detección de colegiatura
    # =========================================================================
    
    def test_detecta_colegiatura(self, extractor):
        """
        CASO: TDR menciona 'colegiatura vigente'
        ESPERADO: Requisito COLEGIATURA detectado
        """
        texto = """
        Perfil:
        - Ingeniero Civil colegiado y habilitado
        - Experiencia en obras públicas
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        assert any(r.tipo == "COLEGIATURA" for r in resultado.requisitos)
    
    # =========================================================================
    # TEST: Obligatoriedad
    # =========================================================================
    
    def test_detecta_requisito_obligatorio(self, extractor):
        """
        CASO: TDR usa 'deberá presentar'
        ESPERADO: Requisito marcado como obligatorio
        """
        texto = """
        El consultor deberá presentar currículum vitae documentado.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        cv_req = [r for r in resultado.requisitos if r.tipo == "CV"]
        assert len(cv_req) > 0
        assert cv_req[0].obligatorio == True
    
    def test_detecta_requisito_deseable(self, extractor):
        """
        CASO: TDR usa 'deseable'
        ESPERADO: Requisito marcado como no obligatorio
        """
        texto = """
        Es deseable que el consultor cuente con experiencia en el sector.
        """
        
        resultado = extractor.extraer_requisitos(texto)
        
        exp_req = [r for r in resultado.requisitos if r.tipo == "EXPERIENCIA"]
        if exp_req:
            assert exp_req[0].obligatorio == False


class TestValidarRequisitosTDR:
    """Tests para validar_requisitos_tdr"""
    
    def test_genera_observacion_cv_faltante(self):
        """
        CASO: TDR pide CV pero no está en documentos presentes
        ESPERADO: Observación por CV faltante
        """
        requisitos = [
            RequisitoTDR(
                tipo="CV",
                descripcion="Currículum Vitae del consultor",
                texto_fuente="Presentar currículum vitae documentado",
                obligatorio=True,
                pagina=2
            )
        ]
        
        docs_presentes = {"FACTURA", "CONFORMIDAD", "ORDEN_SERVICIO"}
        
        observaciones = validar_requisitos_tdr(requisitos, docs_presentes)
        
        assert len(observaciones) > 0
        assert any("CV" in obs.descripcion or "curr" in obs.descripcion.lower() 
                   for obs in observaciones)
    
    def test_no_genera_observacion_si_cv_presente(self):
        """
        CASO: TDR pide CV y CV está presente
        ESPERADO: Sin observación por CV
        """
        requisitos = [
            RequisitoTDR(
                tipo="CV",
                descripcion="Currículum Vitae",
                texto_fuente="Adjuntar CV",
                obligatorio=True,
                pagina=1
            )
        ]
        
        docs_presentes = {"CV", "FACTURA", "CONFORMIDAD"}
        
        observaciones = validar_requisitos_tdr(requisitos, docs_presentes)
        
        # No debería haber observación por CV
        obs_cv = [o for o in observaciones if "CV" in o.descripcion]
        assert len(obs_cv) == 0
    
    def test_no_genera_observacion_si_tdr_no_pide(self):
        """
        CASO: TDR NO pide CV (lista vacía de requisitos)
        ESPERADO: Sin observaciones
        
        PRINCIPIO CLAVE: Si TDR no pide, no se observa
        """
        requisitos = []  # TDR sin requisitos de perfil
        docs_presentes = {"FACTURA", "CONFORMIDAD"}
        
        observaciones = validar_requisitos_tdr(requisitos, docs_presentes)
        
        assert len(observaciones) == 0
    
    def test_no_observa_requisito_deseable_faltante(self):
        """
        CASO: TDR tiene requisito deseable (no obligatorio) y falta
        ESPERADO: Sin observación (no es obligatorio)
        """
        requisitos = [
            RequisitoTDR(
                tipo="EXPERIENCIA",
                descripcion="Experiencia deseable",
                texto_fuente="Es deseable experiencia en el sector",
                obligatorio=False,  # Deseable, no obligatorio
                pagina=1
            )
        ]
        
        docs_presentes = {"FACTURA"}
        
        observaciones = validar_requisitos_tdr(requisitos, docs_presentes)
        
        # No debería generar observación por requisito deseable
        assert len(observaciones) == 0


class TestFuncionesHelper:
    """Tests para funciones helper"""
    
    def test_tdr_requiere_cv_true(self):
        """
        CASO: TDR menciona CV
        ESPERADO: True
        """
        texto = "Adjuntar currículum vitae del consultor"
        
        assert tdr_requiere_cv(texto) == True
    
    def test_tdr_requiere_cv_false(self):
        """
        CASO: TDR NO menciona CV
        ESPERADO: False
        """
        texto = "Servicio de limpieza de oficinas"
        
        assert tdr_requiere_cv(texto) == False
    
    def test_tdr_requiere_experiencia_con_detalle(self):
        """
        CASO: TDR menciona experiencia con años
        ESPERADO: (True, detalle con años)
        """
        texto = "Experiencia profesional mínima de 5 años en el sector"
        
        requiere, detalle = tdr_requiere_experiencia(texto)
        
        assert requiere == True
        assert detalle is not None
    
    def test_tdr_requiere_experiencia_false(self):
        """
        CASO: TDR NO menciona experiencia
        ESPERADO: (False, None)
        """
        texto = "Servicio de alquiler de equipos informáticos"
        
        requiere, detalle = tdr_requiere_experiencia(texto)
        
        assert requiere == False
        assert detalle is None
    
    def test_extraer_requisitos_helper(self):
        """
        CASO: Usar función helper extraer_requisitos_tdr
        ESPERADO: Retorna lista de RequisitoTDR
        """
        texto = """
        PERFIL:
        - Título profesional
        - Experiencia de 3 años
        - Presentar CV documentado
        """
        
        requisitos = extraer_requisitos_tdr(texto)
        
        assert isinstance(requisitos, list)
        assert len(requisitos) > 0
        assert all(isinstance(r, RequisitoTDR) for r in requisitos)


class TestCasosBorde:
    """Tests para casos borde y situaciones especiales"""
    
    def test_tdr_vacio(self):
        """
        CASO: TDR vacío
        ESPERADO: Lista vacía de requisitos
        """
        extractor = TDRRequirementExtractor()
        resultado = extractor.extraer_requisitos("")
        
        assert len(resultado.requisitos) == 0
    
    def test_tdr_solo_espacios(self):
        """
        CASO: TDR solo con espacios
        ESPERADO: Lista vacía de requisitos
        """
        extractor = TDRRequirementExtractor()
        resultado = extractor.extraer_requisitos("   \n\n   \t   ")
        
        assert len(resultado.requisitos) == 0
    
    def test_multiples_requisitos_mismo_tipo(self):
        """
        CASO: TDR menciona experiencia múltiples veces
        ESPERADO: No duplicar requisitos
        """
        texto = """
        - Experiencia mínima de 5 años
        - Acreditar experiencia en proyectos
        - La experiencia se verificará
        """
        
        extractor = TDRRequirementExtractor()
        resultado = extractor.extraer_requisitos(texto)
        
        # No debería haber muchos duplicados
        exp_count = sum(1 for r in resultado.requisitos if r.tipo == "EXPERIENCIA")
        assert exp_count <= 3  # Puede haber algunos pero no excesivos


# =============================================================================
# Ejecución directa
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


