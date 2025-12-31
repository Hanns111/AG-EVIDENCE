# -*- coding: utf-8 -*-
"""
VALIDADOR DE EVIDENCIA PROBATORIA
=================================
Valida que los hallazgos CRÍTICOS y MAYORES cumplan el estándar probatorio.
Degrada automáticamente los que no cumplan.
"""

import os
import sys
from typing import List, Tuple
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict

from config.settings import (
    Observacion, NivelObservacion, EvidenciaProbatoria,
    ResultadoAgente, InformeControlPrevio, MetodoExtraccion
)


@dataclass
class ResultadoValidacion:
    """Resultado de validación de evidencia"""
    observacion: Observacion
    es_valida: bool
    campos_faltantes: List[str]
    mensaje: str


class ValidadorEvidencia:
    """
    Valida que las observaciones cumplan el estándar probatorio
    """
    
    # Campos obligatorios para CRITICA y MAYOR
    CAMPOS_OBLIGATORIOS = [
        "archivo",
        "pagina", 
        "snippet",
        "metodo_extraccion",
        "confianza",
        "regla_aplicada"
    ]
    
    def validar_observacion(self, obs: Observacion) -> ResultadoValidacion:
        """
        Valida una observación individual
        
        Returns:
            ResultadoValidacion con el resultado
        """
        # Solo validar CRITICA y MAYOR
        if obs.nivel not in [NivelObservacion.CRITICA, NivelObservacion.MAYOR]:
            return ResultadoValidacion(
                observacion=obs,
                es_valida=True,
                campos_faltantes=[],
                mensaje="Nivel no requiere validación probatoria"
            )
        
        # Verificar que tenga evidencias
        if not obs.evidencias:
            return ResultadoValidacion(
                observacion=obs,
                es_valida=False,
                campos_faltantes=["evidencias"],
                mensaje="Observación sin evidencias probatorias"
            )
        
        # Verificar campos obligatorios en cada evidencia
        campos_faltantes = []
        for ev in obs.evidencias:
            if not ev.archivo:
                campos_faltantes.append("archivo")
            if not ev.pagina or ev.pagina < 1:
                campos_faltantes.append("pagina")
            if not ev.snippet:
                campos_faltantes.append("snippet")
            if not ev.regla_aplicada:
                campos_faltantes.append("regla_aplicada")
        
        # Verificar regla_aplicada en la observación
        if not obs.regla_aplicada:
            campos_faltantes.append("regla_aplicada (observacion)")
        
        campos_faltantes = list(set(campos_faltantes))
        
        if campos_faltantes:
            return ResultadoValidacion(
                observacion=obs,
                es_valida=False,
                campos_faltantes=campos_faltantes,
                mensaje=f"Campos faltantes: {', '.join(campos_faltantes)}"
            )
        
        return ResultadoValidacion(
            observacion=obs,
            es_valida=True,
            campos_faltantes=[],
            mensaje="Evidencia probatoria completa"
        )
    
    def validar_y_degradar(self, obs: Observacion) -> Observacion:
        """
        Valida y degrada la observación si no cumple estándar
        
        Returns:
            Observación (posiblemente degradada a INCIERTO)
        """
        resultado = self.validar_observacion(obs)
        
        if not resultado.es_valida and obs.nivel in [NivelObservacion.CRITICA, NivelObservacion.MAYOR]:
            # Degradar a INCIERTO
            obs.nivel = NivelObservacion.INCIERTO
            obs.requiere_revision_humana = True
            obs.descripcion = f"[EVIDENCIA INCOMPLETA] {obs.descripcion}"
        
        return obs
    
    def validar_resultado_agente(self, resultado: ResultadoAgente) -> Tuple[int, int]:
        """
        Valida todas las observaciones de un agente
        
        Returns:
            Tuple (validas, degradadas)
        """
        validas = 0
        degradadas = 0
        
        for obs in resultado.observaciones:
            resultado_val = self.validar_observacion(obs)
            if resultado_val.es_valida:
                validas += 1
            else:
                self.validar_y_degradar(obs)
                degradadas += 1
        
        return validas, degradadas
    
    def validar_informe(self, informe: InformeControlPrevio) -> Dict:
        """
        Valida todo el informe y retorna estadísticas
        """
        stats = {
            "total_observaciones": 0,
            "validas": 0,
            "degradadas": 0,
            "por_nivel": {}
        }
        
        todas = (
            informe.observaciones_criticas +
            informe.observaciones_mayores +
            informe.observaciones_menores
        )
        
        stats["total_observaciones"] = len(todas)
        
        for obs in todas:
            resultado = self.validar_observacion(obs)
            if resultado.es_valida:
                stats["validas"] += 1
            else:
                self.validar_y_degradar(obs)
                stats["degradadas"] += 1
        
        return stats


def validar_evidencia_completa(obs: Observacion) -> bool:
    """
    Función helper para verificar si una observación tiene evidencia completa
    
    Returns:
        True si tiene todos los campos requeridos
    """
    if obs.nivel not in [NivelObservacion.CRITICA, NivelObservacion.MAYOR]:
        return True  # Otros niveles no requieren validación
    
    if not obs.evidencias:
        return False
    
    for ev in obs.evidencias:
        if not all([
            ev.archivo,
            ev.pagina > 0,
            ev.snippet,
            ev.regla_aplicada
        ]):
            return False
    
    return bool(obs.regla_aplicada)


# ============================================================================
# TESTS DE VALIDACIÓN
# ============================================================================
def test_hallazgo_critico_con_evidencia():
    """Test: Hallazgo CRÍTICO con evidencia completa debe pasar"""
    evidencia = EvidenciaProbatoria(
        archivo="documento_test.pdf",
        pagina=1,
        valor_detectado="12345",
        snippet="Texto de contexto del valor 12345 detectado",
        metodo_extraccion=MetodoExtraccion.REGEX,
        confianza=0.95,
        regla_aplicada="R001"
    )
    
    obs = Observacion(
        nivel=NivelObservacion.CRITICA,
        agente="Test",
        descripcion="Test crítico",
        accion_requerida="Acción test",
        evidencias=[evidencia],
        regla_aplicada="R001"
    )
    
    validador = ValidadorEvidencia()
    resultado = validador.validar_observacion(obs)
    
    assert resultado.es_valida, f"Debería ser válida: {resultado.mensaje}"
    print("✅ test_hallazgo_critico_con_evidencia PASÓ")


def test_hallazgo_critico_sin_evidencia_degrada():
    """Test: Hallazgo CRÍTICO sin evidencia debe degradarse a INCIERTO"""
    obs = Observacion(
        nivel=NivelObservacion.CRITICA,
        agente="Test",
        descripcion="Test crítico sin evidencia",
        accion_requerida="Acción test",
        evidencias=[],  # Sin evidencias
        regla_aplicada=""
    )
    
    validador = ValidadorEvidencia()
    obs = validador.validar_y_degradar(obs)
    
    assert obs.nivel == NivelObservacion.INCIERTO, "Debería degradarse a INCIERTO"
    assert obs.requiere_revision_humana, "Debería requerir revisión humana"
    print("✅ test_hallazgo_critico_sin_evidencia_degrada PASÓ")


def test_hallazgo_mayor_sin_snippet_degrada():
    """Test: Hallazgo MAYOR sin snippet debe degradarse"""
    evidencia = EvidenciaProbatoria(
        archivo="documento.pdf",
        pagina=1,
        valor_detectado="123",
        snippet="",  # Sin snippet
        metodo_extraccion=MetodoExtraccion.REGEX,
        confianza=0.8,
        regla_aplicada="R002"
    )
    
    obs = Observacion(
        nivel=NivelObservacion.MAYOR,
        agente="Test",
        descripcion="Test mayor sin snippet",
        accion_requerida="Acción test",
        evidencias=[evidencia],
        regla_aplicada="R002"
    )
    
    validador = ValidadorEvidencia()
    resultado = validador.validar_observacion(obs)
    
    assert not resultado.es_valida, "No debería ser válida sin snippet"
    assert "snippet" in resultado.campos_faltantes, "Debería indicar snippet faltante"
    print("✅ test_hallazgo_mayor_sin_snippet_degrada PASÓ")


def test_hallazgo_menor_no_requiere_validacion():
    """Test: Hallazgo MENOR no requiere validación probatoria"""
    obs = Observacion(
        nivel=NivelObservacion.MENOR,
        agente="Test",
        descripcion="Test menor",
        accion_requerida="Acción test",
        evidencias=[],  # Sin evidencias está OK para MENOR
        regla_aplicada=""
    )
    
    validador = ValidadorEvidencia()
    resultado = validador.validar_observacion(obs)
    
    assert resultado.es_valida, "MENOR no debería requerir validación"
    print("✅ test_hallazgo_menor_no_requiere_validacion PASÓ")


def ejecutar_tests():
    """Ejecuta todos los tests de validación"""
    print("=" * 60)
    print("TESTS DE VALIDACIÓN DE EVIDENCIA PROBATORIA")
    print("=" * 60)
    
    try:
        from config.settings import MetodoExtraccion
    except ImportError:
        print("Importando MetodoExtraccion...")
    
    tests = [
        test_hallazgo_critico_con_evidencia,
        test_hallazgo_critico_sin_evidencia_degrada,
        test_hallazgo_mayor_sin_snippet_degrada,
        test_hallazgo_menor_no_requiere_validacion,
    ]
    
    pasados = 0
    fallidos = 0
    
    for test in tests:
        try:
            test()
            pasados += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FALLÓ: {e}")
            fallidos += 1
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}")
            fallidos += 1
    
    print("=" * 60)
    print(f"RESULTADOS: {pasados} pasados, {fallidos} fallidos")
    print("=" * 60)
    
    return fallidos == 0


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.settings import MetodoExtraccion
    
    exito = ejecutar_tests()
    sys.exit(0 if exito else 1)

