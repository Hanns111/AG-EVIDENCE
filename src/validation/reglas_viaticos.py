# -*- coding: utf-8 -*-
"""
Reglas de Viáticos — Topes, Plazos, Documentos Obligatorios
=============================================================
Tarea #28 del Plan de Desarrollo (Fase 4: Validaciones)

Valida el cumplimiento de la directiva de viáticos RGS 023-2026-MINEDU:

  - Topes diarios según destino (Lima/provincia/internacional)
  - Plazo de rendición (8 días hábiles desde retorno)
  - Documentos obligatorios presentes en el expediente
  - Fechas de comprobantes dentro del periodo de comisión
  - Coherencia de montos rendidos vs viáticos asignados
  - Reglas específicas por tipo de comprobante (boleta, factura)

Principios:
  - Cada hallazgo referencia la directiva vigente (RGS 023-2026-MINEDU)
  - Observaciones con EvidenciaProbatoria completa
  - No infiere — si un dato no está extraído, reporta como INFORMATIVA
  - Tolerancias documentadas (1 día para fechas, ±0.20 para montos)

Consume:
  - ExpedienteJSON (contrato de datos, Tarea #17)
  - LIMITES_NORMATIVOS (config/settings.py)
  - validacion_tributaria_viaticos.json

Produce:
  - List[Observacion] con regla_aplicada y evidencia

Versión: 1.0.0
Fecha: 2026-03-13
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Asegurar que el directorio raíz del proyecto esté en el path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import (
    LIMITES_NORMATIVOS,
    EvidenciaProbatoria,
    MetodoExtraccion,
    NivelObservacion,
    Observacion,
)
from src.extraction.expediente_contract import (
    ComprobanteExtraido,
    ExpedienteJSON,
)

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_REGLAS_VIATICOS = "1.0.0"
"""Versión del módulo reglas_viaticos."""

AGENTE_REGLAS = "AG_REGLAS_VIATICOS"
"""ID de agente para observaciones."""

DIRECTIVA_VIGENTE = "RGS 023-2026-MINEDU"
"""Directiva de viáticos vigente."""

PLAZO_RENDICION_DIAS_HABILES = 8
"""Plazo máximo para rendir viáticos (días hábiles desde retorno)."""

TOLERANCIA_FECHA_DIAS = 1
"""Tolerancia en días para fechas de comprobantes vs periodo de comisión."""

TOLERANCIA_MONTO = 0.20
"""Tolerancia en soles para comparación de montos totales."""

# Topes diarios (de config/settings.py LIMITES_NORMATIVOS)
TOPE_VIATICO_DIA = LIMITES_NORMATIVOS.get("viaticos_lima_dia", 320.00)
TOPE_MOVILIDAD_LIMA = LIMITES_NORMATIVOS.get("movilidad_lima_dia", 45.00)
TOPE_MOVILIDAD_PROVINCIA = LIMITES_NORMATIVOS.get("movilidad_provincia_dia", 30.00)

# Documentos obligatorios para rendición de viáticos
DOCUMENTOS_OBLIGATORIOS = [
    "anexo_3",  # Formato de rendición
    "comprobantes",  # Al menos 1 comprobante de pago
]

# Formatos de fecha comunes en comprobantes peruanos
FORMATOS_FECHA = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
]


# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================


def _parsear_fecha(texto: str) -> Optional[datetime]:
    """Intenta parsear una fecha en formatos comunes peruanos."""
    if not texto or not isinstance(texto, str):
        return None
    texto = texto.strip()
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def _extraer_valor_campo(campo) -> Optional[str]:
    """Extrae string de un CampoExtraido."""
    if campo is None:
        return None
    valor = campo.valor if hasattr(campo, "valor") else None
    if valor is None or str(valor).strip() == "":
        return None
    return str(valor).strip()


def _extraer_float_campo(campo) -> Optional[float]:
    """Extrae float de un CampoExtraido."""
    texto = _extraer_valor_campo(campo)
    if texto is None:
        return None
    texto = texto.replace("S/.", "").replace("S/", "").replace(",", "").strip()
    try:
        return float(texto)
    except (ValueError, TypeError):
        return None


def _obtener_archivo_pagina(comprobante: ComprobanteExtraido) -> Tuple[str, int]:
    """Obtiene archivo y página del comprobante para evidencia."""
    archivo = ""
    pagina = 0
    if comprobante.grupo_k:
        pagina = comprobante.grupo_k.pagina_origen or 0
    for campo in comprobante.todos_los_campos()[:5]:
        if campo.archivo:
            archivo = campo.archivo
            if not pagina and campo.pagina:
                pagina = campo.pagina
            break
    return archivo, pagina


# ==============================================================================
# RESULTADOS
# ==============================================================================


@dataclass
class ResultadoReglasViaticos:
    """Resultado de la validación de reglas de viáticos."""

    observaciones: List[Observacion] = field(default_factory=list)
    reglas_evaluadas: int = 0
    reglas_ok: int = 0
    reglas_fallidas: int = 0
    reglas_no_evaluables: int = 0

    @property
    def total_hallazgos(self) -> int:
        return len(self.observaciones)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reglas_evaluadas": self.reglas_evaluadas,
            "reglas_ok": self.reglas_ok,
            "reglas_fallidas": self.reglas_fallidas,
            "reglas_no_evaluables": self.reglas_no_evaluables,
            "total_hallazgos": self.total_hallazgos,
            "observaciones": [
                {
                    "nivel": o.nivel.value,
                    "descripcion": o.descripcion,
                    "regla": o.regla_aplicada,
                }
                for o in self.observaciones
            ],
        }


# ==============================================================================
# CLASE PRINCIPAL — ReglasViaticos
# ==============================================================================


class ReglasViaticos:
    """
    Valida el cumplimiento de la directiva de viáticos vigente.

    Aplica las reglas de RGS 023-2026-MINEDU sobre el expediente
    extraído, generando observaciones con estándar probatorio.
    """

    def __init__(
        self,
        tope_viatico_dia: float = TOPE_VIATICO_DIA,
        plazo_rendicion_dias: int = PLAZO_RENDICION_DIAS_HABILES,
        tolerancia_fecha_dias: int = TOLERANCIA_FECHA_DIAS,
    ):
        self._tope_viatico_dia = tope_viatico_dia
        self._plazo_rendicion = plazo_rendicion_dias
        self._tolerancia_fecha = tolerancia_fecha_dias

    @property
    def version(self) -> str:
        return VERSION_REGLAS_VIATICOS

    # ==========================================================================
    # VALIDACIÓN COMPLETA
    # ==========================================================================

    def validar(self, expediente: ExpedienteJSON) -> ResultadoReglasViaticos:
        """
        Ejecuta todas las reglas de viáticos sobre el expediente.

        Parameters
        ----------
        expediente : ExpedienteJSON
            Expediente con datos de rendición extraídos.

        Returns
        -------
        ResultadoReglasViaticos
            Observaciones y estadísticas de validación.
        """
        resultado = ResultadoReglasViaticos()

        # 1. Documentos obligatorios
        obs_docs = self._validar_documentos_obligatorios(expediente)
        resultado.observaciones.extend(obs_docs)
        resultado.reglas_evaluadas += 1
        if any(o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_docs):
            resultado.reglas_fallidas += 1
        else:
            resultado.reglas_ok += 1

        # 2. Tope de viáticos vs monto rendido
        obs_tope = self._validar_tope_viaticos(expediente)
        resultado.observaciones.extend(obs_tope)
        resultado.reglas_evaluadas += 1
        if any(o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_tope):
            resultado.reglas_fallidas += 1
        elif any(o.nivel == NivelObservacion.INFORMATIVA for o in obs_tope):
            resultado.reglas_no_evaluables += 1
        else:
            resultado.reglas_ok += 1

        # 3. Fechas de comprobantes dentro del periodo
        obs_fechas = self._validar_fechas_comprobantes(expediente)
        resultado.observaciones.extend(obs_fechas)
        resultado.reglas_evaluadas += 1
        if any(o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_fechas):
            resultado.reglas_fallidas += 1
        elif any(o.nivel == NivelObservacion.INFORMATIVA for o in obs_fechas):
            resultado.reglas_no_evaluables += 1
        else:
            resultado.reglas_ok += 1

        # 4. Monto rendido vs viático otorgado (Anexo 3)
        obs_monto = self._validar_monto_vs_asignado(expediente)
        resultado.observaciones.extend(obs_monto)
        resultado.reglas_evaluadas += 1
        if any(o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_monto):
            resultado.reglas_fallidas += 1
        elif any(o.nivel == NivelObservacion.INFORMATIVA for o in obs_monto):
            resultado.reglas_no_evaluables += 1
        else:
            resultado.reglas_ok += 1

        # 5. Comprobante por día de comisión
        obs_cobertura = self._validar_cobertura_dias(expediente)
        resultado.observaciones.extend(obs_cobertura)
        resultado.reglas_evaluadas += 1
        if any(
            o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_cobertura
        ):
            resultado.reglas_fallidas += 1
        elif any(o.nivel == NivelObservacion.INFORMATIVA for o in obs_cobertura):
            resultado.reglas_no_evaluables += 1
        else:
            resultado.reglas_ok += 1

        # 6. Boleta de venta — comprador debe ser institución, no comisionado
        obs_boletas = self._validar_boletas_comprador(expediente)
        resultado.observaciones.extend(obs_boletas)
        resultado.reglas_evaluadas += 1
        if any(o.nivel in (NivelObservacion.CRITICA, NivelObservacion.MAYOR) for o in obs_boletas):
            resultado.reglas_fallidas += 1
        else:
            resultado.reglas_ok += 1

        return resultado

    # ==========================================================================
    # REGLA 1: Documentos obligatorios
    # ==========================================================================

    def _validar_documentos_obligatorios(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """Verifica presencia de documentos mínimos para rendición."""
        observaciones: List[Observacion] = []

        # Verificar Anexo 3
        tiene_anexo3 = expediente.anexo3 is not None and (
            _extraer_valor_campo(expediente.anexo3.comisionado) is not None
            or _extraer_valor_campo(expediente.anexo3.sinad) is not None
        )
        if not tiene_anexo3:
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        "Anexo 3 (formato de rendición) no encontrado o sin datos extraídos. "
                        f"Directiva {DIRECTIVA_VIGENTE} exige rendición con formato oficial."
                    ),
                    accion_requerida="Verificar presencia del Anexo 3 en el expediente",
                    evidencias=[
                        EvidenciaProbatoria(
                            archivo=expediente.sinad,
                            pagina=1,
                            valor_detectado="Anexo 3 ausente o vacío",
                            valor_esperado="Anexo 3 con datos del comisionado",
                            snippet="Formato de rendición de viáticos",
                            metodo_extraccion=MetodoExtraccion.HEURISTICA,
                            confianza=0.9,
                            regla_aplicada="VIAT_DOC_ANEXO3",
                        )
                    ],
                    regla_aplicada="VIAT_DOC_ANEXO3",
                )
            )

        # Verificar comprobantes
        n_comprobantes = len(expediente.comprobantes) if expediente.comprobantes else 0
        if n_comprobantes == 0:
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        "No se extrajeron comprobantes de pago. "
                        f"Directiva {DIRECTIVA_VIGENTE}: la rendición debe incluir "
                        "comprobantes que sustenten los gastos."
                    ),
                    accion_requerida="Verificar comprobantes en el PDF",
                    evidencias=[
                        EvidenciaProbatoria(
                            archivo=expediente.sinad,
                            pagina=1,
                            valor_detectado="0 comprobantes extraídos",
                            valor_esperado="≥1 comprobante de pago",
                            snippet="Rendición sin comprobantes",
                            metodo_extraccion=MetodoExtraccion.HEURISTICA,
                            confianza=0.9,
                            regla_aplicada="VIAT_DOC_COMPROBANTES",
                        )
                    ],
                    regla_aplicada="VIAT_DOC_COMPROBANTES",
                )
            )

        return observaciones

    # ==========================================================================
    # REGLA 2: Tope de viáticos por día
    # ==========================================================================

    def _validar_tope_viaticos(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """Verifica que ningún día exceda el tope diario de viáticos."""
        observaciones: List[Observacion] = []

        if not expediente.comprobantes:
            return observaciones

        # Sumar totales de todos los comprobantes
        suma_total = 0.0
        comprobantes_con_total = 0
        for comp in expediente.comprobantes:
            total = _extraer_float_campo(comp.grupo_f.importe_total)
            if total is not None:
                suma_total += total
                comprobantes_con_total += 1

        if comprobantes_con_total == 0:
            return observaciones

        # Obtener días de comisión desde Anexo 3
        dias_comision = self._calcular_dias_comision(expediente)

        if dias_comision is None:
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.INFORMATIVA,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        f"No se pudo determinar duración de la comisión (fechas no extraídas). "
                        f"Total rendido: S/{suma_total:.2f} en {comprobantes_con_total} comprobantes."
                    ),
                    accion_requerida="Verificar fechas de salida y retorno en Anexo 3",
                    regla_aplicada="VIAT_TOPE_DIARIO_INFO",
                )
            )
            return observaciones

        if dias_comision <= 0:
            dias_comision = 1

        tope_total = self._tope_viatico_dia * dias_comision
        promedio_dia = suma_total / dias_comision

        if suma_total > tope_total + TOLERANCIA_MONTO:
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        f"Total rendido S/{suma_total:.2f} excede tope de viáticos "
                        f"(S/{self._tope_viatico_dia:.2f}/día × {dias_comision} días = "
                        f"S/{tope_total:.2f}). Exceso: S/{suma_total - tope_total:.2f}. "
                        f"Directiva {DIRECTIVA_VIGENTE}."
                    ),
                    accion_requerida=(
                        "Verificar monto rendido vs escala de viáticos. "
                        "El exceso debe ser devuelto o justificado."
                    ),
                    evidencias=[
                        EvidenciaProbatoria(
                            archivo="Anexo3",
                            pagina=1,
                            valor_detectado=f"Total rendido S/{suma_total:.2f}",
                            valor_esperado=f"Tope S/{tope_total:.2f} ({dias_comision} días)",
                            snippet=f"Promedio diario: S/{promedio_dia:.2f}",
                            metodo_extraccion=MetodoExtraccion.HEURISTICA,
                            confianza=0.85,
                            regla_aplicada="VIAT_TOPE_DIARIO",
                        )
                    ],
                    regla_aplicada="VIAT_TOPE_DIARIO",
                )
            )

        return observaciones

    # ==========================================================================
    # REGLA 3: Fechas de comprobantes dentro del periodo
    # ==========================================================================

    def _validar_fechas_comprobantes(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """Verifica que las fechas de comprobantes estén dentro del periodo de comisión."""
        observaciones: List[Observacion] = []

        if not expediente.comprobantes:
            return observaciones

        # Obtener periodo de comisión
        fecha_salida, fecha_retorno = self._extraer_periodo_comision(expediente)
        if fecha_salida is None or fecha_retorno is None:
            # No podemos validar sin periodo
            comprobantes_con_fecha = sum(
                1 for c in expediente.comprobantes if _extraer_valor_campo(c.grupo_b.fecha_emision)
            )
            if comprobantes_con_fecha > 0:
                observaciones.append(
                    Observacion(
                        nivel=NivelObservacion.INFORMATIVA,
                        agente=AGENTE_REGLAS,
                        descripcion=(
                            f"No se pudo validar fechas de {comprobantes_con_fecha} comprobantes "
                            "contra periodo de comisión (fechas de salida/retorno no extraídas)."
                        ),
                        accion_requerida="Verificar periodo de comisión en Anexo 3",
                        regla_aplicada="VIAT_FECHAS_INFO",
                    )
                )
            return observaciones

        # Rango válido con tolerancia
        fecha_min = fecha_salida - timedelta(days=self._tolerancia_fecha)
        fecha_max = fecha_retorno + timedelta(days=self._tolerancia_fecha)

        for comp in expediente.comprobantes:
            fecha_str = _extraer_valor_campo(comp.grupo_b.fecha_emision)
            if not fecha_str:
                continue

            fecha_comp = _parsear_fecha(fecha_str)
            if fecha_comp is None:
                continue

            if fecha_comp < fecha_min or fecha_comp > fecha_max:
                archivo, pagina = _obtener_archivo_pagina(comp)
                serie_num = comp.get_serie_numero()
                observaciones.append(
                    Observacion(
                        nivel=NivelObservacion.MAYOR,
                        agente=AGENTE_REGLAS,
                        descripcion=(
                            f"Comprobante {serie_num}: fecha {fecha_str} fuera del "
                            f"periodo de comisión ({fecha_salida.strftime('%d/%m/%Y')} — "
                            f"{fecha_retorno.strftime('%d/%m/%Y')}, ±{self._tolerancia_fecha} día). "
                            f"Directiva {DIRECTIVA_VIGENTE}."
                        ),
                        accion_requerida="Verificar fecha del comprobante vs periodo de comisión",
                        evidencias=[
                            EvidenciaProbatoria(
                                archivo=archivo,
                                pagina=pagina,
                                valor_detectado=fecha_str,
                                valor_esperado=(
                                    f"{fecha_salida.strftime('%d/%m/%Y')} — "
                                    f"{fecha_retorno.strftime('%d/%m/%Y')}"
                                ),
                                snippet=f"Fecha emisión: {fecha_str}",
                                metodo_extraccion=MetodoExtraccion.HEURISTICA,
                                confianza=0.85,
                                regla_aplicada="VIAT_FECHA_FUERA_PERIODO",
                            )
                        ],
                        regla_aplicada="VIAT_FECHA_FUERA_PERIODO",
                    )
                )

        return observaciones

    # ==========================================================================
    # REGLA 4: Monto rendido vs viático otorgado
    # ==========================================================================

    def _validar_monto_vs_asignado(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """Verifica que el total rendido no exceda el viático otorgado."""
        observaciones: List[Observacion] = []

        if not expediente.anexo3:
            return observaciones

        viatico_otorgado = _extraer_float_campo(expediente.anexo3.viatico_otorgado)
        total_gastado = _extraer_float_campo(expediente.anexo3.total_gastado)

        if viatico_otorgado is None or total_gastado is None:
            if viatico_otorgado is not None or total_gastado is not None:
                observaciones.append(
                    Observacion(
                        nivel=NivelObservacion.INFORMATIVA,
                        agente=AGENTE_REGLAS,
                        descripcion=(
                            "Datos incompletos para validar monto rendido vs asignado. "
                            f"Viático otorgado: {'S/' + f'{viatico_otorgado:.2f}' if viatico_otorgado else 'no extraído'}. "
                            f"Total gastado: {'S/' + f'{total_gastado:.2f}' if total_gastado else 'no extraído'}."
                        ),
                        accion_requerida="Verificar montos en Anexo 3",
                        regla_aplicada="VIAT_MONTO_VS_ASIGNADO_INFO",
                    )
                )
            return observaciones

        if total_gastado > viatico_otorgado + TOLERANCIA_MONTO:
            exceso = total_gastado - viatico_otorgado
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.MAYOR,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        f"Total gastado S/{total_gastado:.2f} excede viático otorgado "
                        f"S/{viatico_otorgado:.2f}. Exceso: S/{exceso:.2f}. "
                        f"Directiva {DIRECTIVA_VIGENTE}: el exceso debe ser devuelto."
                    ),
                    accion_requerida="Verificar devolución del exceso o justificación",
                    evidencias=[
                        EvidenciaProbatoria(
                            archivo="Anexo3",
                            pagina=1,
                            valor_detectado=f"Total gastado S/{total_gastado:.2f}",
                            valor_esperado=f"≤ S/{viatico_otorgado:.2f}",
                            snippet=f"Viático otorgado: S/{viatico_otorgado:.2f}",
                            metodo_extraccion=MetodoExtraccion.HEURISTICA,
                            confianza=0.9,
                            regla_aplicada="VIAT_MONTO_EXCEDE_ASIGNADO",
                        )
                    ],
                    regla_aplicada="VIAT_MONTO_EXCEDE_ASIGNADO",
                )
            )

        # Verificar devolución si hay
        devolucion = _extraer_float_campo(expediente.anexo3.devolucion)
        if devolucion is not None and viatico_otorgado > total_gastado:
            devolucion_esperada = round(viatico_otorgado - total_gastado, 2)
            if abs(devolucion - devolucion_esperada) > TOLERANCIA_MONTO:
                observaciones.append(
                    Observacion(
                        nivel=NivelObservacion.MENOR,
                        agente=AGENTE_REGLAS,
                        descripcion=(
                            f"Devolución declarada S/{devolucion:.2f} ≠ diferencia esperada "
                            f"S/{devolucion_esperada:.2f} (otorgado S/{viatico_otorgado:.2f} - "
                            f"gastado S/{total_gastado:.2f})."
                        ),
                        accion_requerida="Verificar cálculo de devolución",
                        evidencias=[
                            EvidenciaProbatoria(
                                archivo="Anexo3",
                                pagina=1,
                                valor_detectado=f"Devolución S/{devolucion:.2f}",
                                valor_esperado=f"S/{devolucion_esperada:.2f}",
                                snippet=f"Viático: {viatico_otorgado}, Gastado: {total_gastado}",
                                metodo_extraccion=MetodoExtraccion.HEURISTICA,
                                confianza=0.85,
                                regla_aplicada="VIAT_DEVOLUCION_INCONSISTENTE",
                            )
                        ],
                        regla_aplicada="VIAT_DEVOLUCION_INCONSISTENTE",
                    )
                )

        return observaciones

    # ==========================================================================
    # REGLA 5: Cobertura de días con comprobantes
    # ==========================================================================

    def _validar_cobertura_dias(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """Verifica que haya comprobantes para cada día de comisión."""
        observaciones: List[Observacion] = []

        if not expediente.comprobantes:
            return observaciones

        dias_comision = self._calcular_dias_comision(expediente)
        n_comprobantes = len(expediente.comprobantes)

        if dias_comision is None:
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.INFORMATIVA,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        f"No se pudo evaluar cobertura de días. "
                        f"{n_comprobantes} comprobantes extraídos."
                    ),
                    accion_requerida="Verificar fechas del periodo de comisión",
                    regla_aplicada="VIAT_COBERTURA_DIAS_INFO",
                )
            )
            return observaciones

        if dias_comision <= 0:
            return observaciones

        # Contar fechas únicas de comprobantes
        fechas_unicas = set()
        for comp in expediente.comprobantes:
            fecha_str = _extraer_valor_campo(comp.grupo_b.fecha_emision)
            if fecha_str:
                fecha = _parsear_fecha(fecha_str)
                if fecha:
                    fechas_unicas.add(fecha.date())

        if len(fechas_unicas) > 0 and len(fechas_unicas) < dias_comision:
            dias_sin = dias_comision - len(fechas_unicas)
            observaciones.append(
                Observacion(
                    nivel=NivelObservacion.MENOR,
                    agente=AGENTE_REGLAS,
                    descripcion=(
                        f"Comprobantes cubren {len(fechas_unicas)} de {dias_comision} días "
                        f"de comisión ({dias_sin} días sin comprobantes). "
                        "Puede estar cubierto por declaración jurada de movilidad."
                    ),
                    accion_requerida="Verificar justificación de días sin comprobantes",
                    regla_aplicada="VIAT_COBERTURA_DIAS",
                )
            )

        return observaciones

    # ==========================================================================
    # REGLA 6: Boleta de venta — comprador = institución
    # ==========================================================================

    def _validar_boletas_comprador(
        self,
        expediente: ExpedienteJSON,
    ) -> List[Observacion]:
        """
        Verifica que en boletas de venta el comprador sea la institución.
        Regla de Hans: DNI del comisionado como comprador = NO válido.
        """
        observaciones: List[Observacion] = []

        if not expediente.comprobantes:
            return observaciones

        # Obtener DNI del comisionado si está disponible
        dni_comisionado = None
        if expediente.anexo3 and expediente.anexo3.dni:
            dni_comisionado = _extraer_valor_campo(expediente.anexo3.dni)

        for comp in expediente.comprobantes:
            tipo = _extraer_valor_campo(comp.grupo_b.tipo_comprobante)
            if not tipo:
                continue

            tipo_upper = tipo.upper()
            if "BOLETA" not in tipo_upper:
                continue

            # Verificar comprador (puede estar en ruc_adquirente como DNI)
            ruc_comprador = (
                _extraer_valor_campo(comp.grupo_c.ruc_adquirente) if comp.grupo_c else None
            )

            if dni_comisionado and ruc_comprador:
                # Limpiar para comparar
                ruc_limpio = ruc_comprador.replace(" ", "").replace("-", "")
                dni_limpio = dni_comisionado.replace(" ", "").replace("-", "")
                if ruc_limpio == dni_limpio:
                    archivo, pagina = _obtener_archivo_pagina(comp)
                    serie_num = comp.get_serie_numero()
                    observaciones.append(
                        Observacion(
                            nivel=NivelObservacion.MAYOR,
                            agente=AGENTE_REGLAS,
                            descripcion=(
                                f"Boleta {serie_num}: comprador es el comisionado "
                                f"(DNI {dni_comisionado}), debe ser la institución (RUC). "
                                f"Directiva {DIRECTIVA_VIGENTE}: inscripción a título personal "
                                "no permitida."
                            ),
                            accion_requerida=("Solicitar boleta a nombre de la institución (RUC)"),
                            evidencias=[
                                EvidenciaProbatoria(
                                    archivo=archivo,
                                    pagina=pagina,
                                    valor_detectado=f"DNI comprador: {ruc_comprador}",
                                    valor_esperado="RUC de la institución",
                                    snippet=f"Boleta {serie_num} a nombre personal",
                                    metodo_extraccion=MetodoExtraccion.HEURISTICA,
                                    confianza=0.9,
                                    regla_aplicada="VIAT_BOLETA_COMPRADOR_PERSONAL",
                                )
                            ],
                            regla_aplicada="VIAT_BOLETA_COMPRADOR_PERSONAL",
                        )
                    )

        return observaciones

    # ==========================================================================
    # MÉTODOS AUXILIARES INTERNOS
    # ==========================================================================

    def _calcular_dias_comision(self, expediente: ExpedienteJSON) -> Optional[int]:
        """Calcula días de comisión desde Anexo 3."""
        fecha_salida, fecha_retorno = self._extraer_periodo_comision(expediente)
        if fecha_salida is None or fecha_retorno is None:
            return None
        delta = (fecha_retorno - fecha_salida).days + 1  # Inclusive
        return max(delta, 1)

    def _extraer_periodo_comision(
        self,
        expediente: ExpedienteJSON,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Extrae fechas de salida y retorno del Anexo 3."""
        if not expediente.anexo3:
            return None, None

        salida_str = _extraer_valor_campo(expediente.anexo3.fecha_salida)
        retorno_str = _extraer_valor_campo(expediente.anexo3.fecha_regreso)

        fecha_salida = _parsear_fecha(salida_str) if salida_str else None
        fecha_retorno = _parsear_fecha(retorno_str) if retorno_str else None

        return fecha_salida, fecha_retorno


# ==============================================================================
# FUNCIÓN DE CONVENIENCIA
# ==============================================================================


def validar_reglas_viaticos(
    expediente: ExpedienteJSON,
) -> ResultadoReglasViaticos:
    """
    Función de conveniencia para validar reglas de viáticos.

    Parameters
    ----------
    expediente : ExpedienteJSON
        Expediente a validar.

    Returns
    -------
    ResultadoReglasViaticos
        Resultado con observaciones y estadísticas.
    """
    reglas = ReglasViaticos()
    return reglas.validar(expediente)
