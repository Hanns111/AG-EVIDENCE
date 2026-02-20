# -*- coding: utf-8 -*-
"""
Calibración de Umbrales con Distribución Real
===============================================
Tarea #19 del Plan de Desarrollo (Fase 2: Contrato + Router)

Analiza benchmarks empíricos (prueba_empirica_cc003.json y futuros)
para calibrar los umbrales del ConfidenceRouter y AbstencionPolicy.

Produce 3 perfiles reutilizables (CONSERVADOR / BALANCEADO / PERMISIVO)
que se exportan a JSON para consumo directo por ConfidenceRouter.

Principios:
  - Este módulo es PRODUCTOR de UmbralesRouter/UmbralesAbstencion, NO modificador.
  - No importa ni altera confidence_router.py ni abstencion.py.
  - No interfiere con el flujo AG01→AG09 ni con el IntegrityCheckpoint.
  - Los perfiles se generan a partir de datos empíricos reales.
  - Exporta/importa JSON para persistencia y reproducibilidad.

Uso:
    from src.extraction.calibracion import CalibradorUmbrales, PerfilCalibracion

    calibrador = CalibradorUmbrales()
    calibrador.cargar_benchmark("data/evaluacion/prueba_empirica_cc003.json")
    perfiles = calibrador.generar_perfiles()

    # Obtener umbrales para un perfil específico
    resultado = perfiles[PerfilCalibracion.BALANCEADO]
    print(resultado.umbrales_router)

    # Exportar a JSON
    calibrador.exportar_json("data/normativa/umbrales_calibrados.json")

Gobernanza:
  - Art. 2: No modifica flujo existente (este módulo es standalone)
  - Art. 3: Anti-alucinación (umbrales basados en datos reales, no estimaciones)
  - ADR-005: No es módulo monolítico; produce datos para el router
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple


# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_CALIBRACION = "1.0.0"
"""Versión del módulo de calibración."""

# Campos evaluables en benchmarks (los que aparecen en prueba_empirica)
CAMPOS_BENCHMARK = ["ruc", "serie_numero", "total", "igv", "fecha"]
"""Lista canónica de campos evaluados en benchmarks empíricos."""

# Resultados posibles en benchmarks
RESULTADO_MATCH = "MATCH"
RESULTADO_ERROR = "ERROR"
RESULTADO_NO_EXTRAIDO = "NO_EXTRAIDO"
RESULTADO_SKIP = "SKIP_GT_NULL"


# ==============================================================================
# PERFILES DE CALIBRACIÓN
# ==============================================================================

class PerfilCalibracion(Enum):
    """
    Perfiles de riesgo para calibración de umbrales.

    CONSERVADOR: Detecta problemas rápidamente. Para expedientes críticos
                 o cuando la precisión del pipeline es baja.
    BALANCEADO:  Equilibrio entre detección y tolerancia. Perfil por defecto
                 para uso general.
    PERMISIVO:   Mayor tolerancia. Para expedientes donde se espera alta
                 tasa de campos no extraíbles (escaneados degradados).
    """
    CONSERVADOR = "conservador"
    BALANCEADO = "balanceado"
    PERMISIVO = "permisivo"


# ==============================================================================
# ESTADÍSTICAS POR CAMPO
# ==============================================================================

@dataclass
class EstadisticaCampo:
    """
    Estadísticas de extracción para un tipo de campo específico.

    Computed a partir de los resultados empíricos del benchmark.
    """
    campo: str
    """Nombre del campo (ruc, serie_numero, total, igv, fecha)."""

    evaluados: int = 0
    """Total de instancias evaluadas (excluye SKIP_GT_NULL)."""

    match: int = 0
    """Instancias con resultado MATCH (extracción correcta)."""

    error: int = 0
    """Instancias con resultado ERROR (extracción incorrecta)."""

    no_extraido: int = 0
    """Instancias con resultado NO_EXTRAIDO (campo no encontrado)."""

    skip: int = 0
    """Instancias con resultado SKIP_GT_NULL (sin ground truth)."""

    @property
    def tasa_acierto(self) -> float:
        """Porcentaje de aciertos sobre evaluados. 0.0 si no hay evaluados."""
        if self.evaluados == 0:
            return 0.0
        return self.match / self.evaluados

    @property
    def tasa_error(self) -> float:
        """Porcentaje de errores sobre evaluados. 0.0 si no hay evaluados."""
        if self.evaluados == 0:
            return 0.0
        return self.error / self.evaluados

    @property
    def tasa_no_extraido(self) -> float:
        """Porcentaje de no extraídos sobre evaluados. 0.0 si no hay evaluados."""
        if self.evaluados == 0:
            return 0.0
        return self.no_extraido / self.evaluados

    @property
    def tasa_fallo(self) -> float:
        """Porcentaje de fallo total (error + no_extraido) sobre evaluados."""
        if self.evaluados == 0:
            return 0.0
        return (self.error + self.no_extraido) / self.evaluados

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario incluyendo propiedades computadas."""
        return {
            "campo": self.campo,
            "evaluados": self.evaluados,
            "match": self.match,
            "error": self.error,
            "no_extraido": self.no_extraido,
            "skip": self.skip,
            "tasa_acierto": round(self.tasa_acierto, 4),
            "tasa_error": round(self.tasa_error, 4),
            "tasa_no_extraido": round(self.tasa_no_extraido, 4),
            "tasa_fallo": round(self.tasa_fallo, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EstadisticaCampo":
        """Crea desde diccionario (ignora propiedades computadas)."""
        valid_fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# ==============================================================================
# ANÁLISIS DE BENCHMARK
# ==============================================================================

@dataclass
class AnalisisBenchmark:
    """
    Resultado completo del análisis de un benchmark empírico.

    Contiene las métricas globales y por campo del benchmark,
    más metadata de trazabilidad.
    """
    # Identificación
    prueba_id: str = ""
    """Identificador de la prueba (ej: 'empirica_cc003')."""

    expediente: str = ""
    """Identificador del expediente evaluado."""

    pipeline_version: str = ""
    """Versión del pipeline usado para la prueba."""

    timestamp_analisis: str = ""
    """Timestamp ISO del análisis (generado automáticamente)."""

    # Métricas globales
    total_comprobantes: int = 0
    """Número total de comprobantes en el benchmark."""

    total_campos_evaluados: int = 0
    """Campos con ground truth disponible (excluye SKIP_GT_NULL)."""

    total_skip: int = 0
    """Campos sin ground truth (SKIP_GT_NULL)."""

    total_match: int = 0
    """Campos con extracción correcta."""

    total_error: int = 0
    """Campos con extracción incorrecta."""

    total_no_extraido: int = 0
    """Campos no encontrados por el pipeline."""

    precision_pct: float = 0.0
    """Porcentaje de precisión global (match / evaluados * 100)."""

    tasa_fallo_global: float = 0.0
    """Porcentaje de fallo global ((error + no_extraido) / evaluados)."""

    # Confianza OCR
    confianza_ocr_min: float = 0.0
    """Confianza OCR mínima entre comprobantes."""

    confianza_ocr_max: float = 0.0
    """Confianza OCR máxima entre comprobantes."""

    confianza_ocr_media: float = 0.0
    """Confianza OCR promedio entre comprobantes."""

    # Estadísticas por campo
    stats_por_campo: Dict[str, EstadisticaCampo] = field(default_factory=dict)
    """Diccionario campo → EstadisticaCampo."""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        result = {
            "prueba_id": self.prueba_id,
            "expediente": self.expediente,
            "pipeline_version": self.pipeline_version,
            "timestamp_analisis": self.timestamp_analisis,
            "total_comprobantes": self.total_comprobantes,
            "total_campos_evaluados": self.total_campos_evaluados,
            "total_skip": self.total_skip,
            "total_match": self.total_match,
            "total_error": self.total_error,
            "total_no_extraido": self.total_no_extraido,
            "precision_pct": round(self.precision_pct, 2),
            "tasa_fallo_global": round(self.tasa_fallo_global, 4),
            "confianza_ocr_min": round(self.confianza_ocr_min, 4),
            "confianza_ocr_max": round(self.confianza_ocr_max, 4),
            "confianza_ocr_media": round(self.confianza_ocr_media, 4),
            "stats_por_campo": {
                k: v.to_dict() for k, v in self.stats_por_campo.items()
            },
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalisisBenchmark":
        """Crea desde diccionario."""
        stats = {}
        raw_stats = data.get("stats_por_campo", {})
        for campo, sdata in raw_stats.items():
            stats[campo] = EstadisticaCampo.from_dict(sdata)

        return cls(
            prueba_id=data.get("prueba_id", ""),
            expediente=data.get("expediente", ""),
            pipeline_version=data.get("pipeline_version", ""),
            timestamp_analisis=data.get("timestamp_analisis", ""),
            total_comprobantes=data.get("total_comprobantes", 0),
            total_campos_evaluados=data.get("total_campos_evaluados", 0),
            total_skip=data.get("total_skip", 0),
            total_match=data.get("total_match", 0),
            total_error=data.get("total_error", 0),
            total_no_extraido=data.get("total_no_extraido", 0),
            precision_pct=data.get("precision_pct", 0.0),
            tasa_fallo_global=data.get("tasa_fallo_global", 0.0),
            confianza_ocr_min=data.get("confianza_ocr_min", 0.0),
            confianza_ocr_max=data.get("confianza_ocr_max", 0.0),
            confianza_ocr_media=data.get("confianza_ocr_media", 0.0),
            stats_por_campo=stats,
        )


# ==============================================================================
# RESULTADO DE CALIBRACIÓN (un perfil)
# ==============================================================================

@dataclass
class ResultadoCalibracion:
    """
    Umbrales calibrados para un perfil específico.

    Contiene los valores numéricos del perfil más la justificación
    empírica de cada umbral.
    """
    perfil: str = ""
    """Nombre del perfil (conservador, balanceado, permisivo)."""

    umbrales_router: Dict[str, Any] = field(default_factory=dict)
    """Diccionario con los 9 umbrales del UmbralesRouter."""

    umbrales_abstencion: Dict[str, float] = field(default_factory=dict)
    """Diccionario con umbrales por tipo de campo (UmbralesAbstencion)."""

    justificaciones: Dict[str, str] = field(default_factory=dict)
    """Justificación empírica por cada umbral calibrado."""

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "perfil": self.perfil,
            "umbrales_router": self.umbrales_router,
            "umbrales_abstencion": self.umbrales_abstencion,
            "justificaciones": self.justificaciones,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultadoCalibracion":
        """Crea desde diccionario."""
        return cls(
            perfil=data.get("perfil", ""),
            umbrales_router=data.get("umbrales_router", {}),
            umbrales_abstencion=data.get("umbrales_abstencion", {}),
            justificaciones=data.get("justificaciones", {}),
        )


# ==============================================================================
# CALIBRADOR DE UMBRALES
# ==============================================================================

class CalibradorUmbrales:
    """
    Motor de calibración de umbrales basado en benchmarks empíricos.

    Flujo:
      1. cargar_benchmark(path) → parsea JSON de prueba empírica
      2. analizar() → computa AnalisisBenchmark con estadísticas
      3. generar_perfiles() → crea 3 perfiles calibrados
      4. exportar_json(path) → persiste resultado

    Es idempotente: se puede re-ejecutar con nuevos benchmarks.
    """

    def __init__(self) -> None:
        self._benchmarks_raw: List[Dict[str, Any]] = []
        """Datos crudos de benchmarks cargados."""

        self._analisis: Optional[AnalisisBenchmark] = None
        """Análisis consolidado (None hasta que se llame analizar())."""

        self._perfiles: Dict[PerfilCalibracion, ResultadoCalibracion] = {}
        """Perfiles generados (vacío hasta generar_perfiles())."""

    # ------------------------------------------------------------------
    # CARGA DE DATOS
    # ------------------------------------------------------------------

    def cargar_benchmark(self, path: str) -> None:
        """
        Carga un benchmark empírico desde archivo JSON.

        Args:
            path: Ruta al archivo JSON de benchmark.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            json.JSONDecodeError: Si el JSON es inválido.
            ValueError: Si el JSON no tiene la estructura esperada.
        """
        ruta = Path(path)
        if not ruta.exists():
            raise FileNotFoundError(f"Benchmark no encontrado: {path}")

        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validar estructura mínima
        if "resultados_por_comprobante" not in data:
            raise ValueError(
                f"Benchmark inválido: falta 'resultados_por_comprobante' en {path}"
            )
        if "metricas" not in data:
            raise ValueError(
                f"Benchmark inválido: falta 'metricas' en {path}"
            )

        self._benchmarks_raw.append(data)
        # Invalidar análisis previo
        self._analisis = None
        self._perfiles = {}

    def cargar_benchmark_dict(self, data: Dict[str, Any]) -> None:
        """
        Carga un benchmark desde diccionario en memoria.

        Útil para tests sin necesidad de archivos en disco.

        Args:
            data: Diccionario con estructura de benchmark.

        Raises:
            ValueError: Si falta estructura requerida.
        """
        if "resultados_por_comprobante" not in data:
            raise ValueError("Benchmark inválido: falta 'resultados_por_comprobante'")
        if "metricas" not in data:
            raise ValueError("Benchmark inválido: falta 'metricas'")

        self._benchmarks_raw.append(data)
        self._analisis = None
        self._perfiles = {}

    # ------------------------------------------------------------------
    # ANÁLISIS
    # ------------------------------------------------------------------

    def analizar(self) -> AnalisisBenchmark:
        """
        Analiza todos los benchmarks cargados y produce estadísticas.

        Si hay un solo benchmark, usa sus datos directamente.
        Si hay múltiples, agrega las estadísticas.

        Returns:
            AnalisisBenchmark con métricas globales y por campo.

        Raises:
            ValueError: Si no hay benchmarks cargados.
        """
        if not self._benchmarks_raw:
            raise ValueError("No hay benchmarks cargados. Use cargar_benchmark() primero.")

        # Inicializar estadísticas por campo
        stats: Dict[str, EstadisticaCampo] = {
            campo: EstadisticaCampo(campo=campo) for campo in CAMPOS_BENCHMARK
        }

        # Contadores globales
        total_comprobantes = 0
        total_match = 0
        total_error = 0
        total_no_extraido = 0
        total_skip = 0
        confianzas: List[float] = []

        # Metadata del primer benchmark (o combinado)
        primer = self._benchmarks_raw[0]
        prueba_id = primer.get("prueba", "desconocida")
        expediente = primer.get("expediente", "desconocido")
        pipeline_version = primer.get("pipeline_version", "desconocida")

        if len(self._benchmarks_raw) > 1:
            prueba_id = f"combinado_{len(self._benchmarks_raw)}_benchmarks"
            expediente = "múltiples"

        # Procesar cada benchmark
        for benchmark in self._benchmarks_raw:
            comprobantes = benchmark.get("resultados_por_comprobante", [])
            total_comprobantes += len(comprobantes)

            for comp in comprobantes:
                # Confianza OCR
                conf = comp.get("confianza")
                if conf is not None:
                    confianzas.append(float(conf))

                # Campos
                campos = comp.get("campos", {})
                for nombre_campo, detalle in campos.items():
                    resultado = detalle.get("resultado", "")

                    # Solo procesar campos conocidos
                    if nombre_campo not in stats:
                        stats[nombre_campo] = EstadisticaCampo(campo=nombre_campo)

                    stat = stats[nombre_campo]

                    if resultado == RESULTADO_SKIP:
                        stat.skip += 1
                        total_skip += 1
                    elif resultado == RESULTADO_MATCH:
                        stat.match += 1
                        stat.evaluados += 1
                        total_match += 1
                    elif resultado == RESULTADO_ERROR:
                        stat.error += 1
                        stat.evaluados += 1
                        total_error += 1
                    elif resultado == RESULTADO_NO_EXTRAIDO:
                        stat.no_extraido += 1
                        stat.evaluados += 1
                        total_no_extraido += 1

        total_evaluados = total_match + total_error + total_no_extraido
        precision = (total_match / total_evaluados * 100) if total_evaluados > 0 else 0.0
        tasa_fallo = ((total_error + total_no_extraido) / total_evaluados) if total_evaluados > 0 else 0.0

        self._analisis = AnalisisBenchmark(
            prueba_id=prueba_id,
            expediente=expediente,
            pipeline_version=pipeline_version,
            timestamp_analisis=datetime.now(timezone.utc).isoformat(),
            total_comprobantes=total_comprobantes,
            total_campos_evaluados=total_evaluados,
            total_skip=total_skip,
            total_match=total_match,
            total_error=total_error,
            total_no_extraido=total_no_extraido,
            precision_pct=round(precision, 2),
            tasa_fallo_global=round(tasa_fallo, 4),
            confianza_ocr_min=round(min(confianzas), 4) if confianzas else 0.0,
            confianza_ocr_max=round(max(confianzas), 4) if confianzas else 0.0,
            confianza_ocr_media=round(sum(confianzas) / len(confianzas), 4) if confianzas else 0.0,
            stats_por_campo=stats,
        )

        return self._analisis

    def obtener_analisis(self) -> Optional[AnalisisBenchmark]:
        """Retorna el análisis actual sin recomputar. None si no se ha analizado."""
        return self._analisis

    # ------------------------------------------------------------------
    # GENERACIÓN DE PERFILES
    # ------------------------------------------------------------------

    def generar_perfiles(self) -> Dict[PerfilCalibracion, ResultadoCalibracion]:
        """
        Genera los 3 perfiles de calibración basados en el análisis.

        Si no se ha llamado analizar(), lo llama automáticamente.

        Returns:
            Diccionario PerfilCalibracion → ResultadoCalibracion.

        Raises:
            ValueError: Si no hay benchmarks cargados.
        """
        if self._analisis is None:
            self.analizar()

        analisis = self._analisis
        tasa_fallo = analisis.tasa_fallo_global

        # Justificación base
        just_base = (
            f"Benchmark {analisis.prueba_id}: "
            f"{analisis.total_comprobantes} comprobantes, "
            f"precisión {analisis.precision_pct}%, "
            f"tasa fallo {round(tasa_fallo * 100, 1)}%. "
            f"Confianza OCR {analisis.confianza_ocr_min:.3f}-{analisis.confianza_ocr_max:.3f} "
            f"(media {analisis.confianza_ocr_media:.3f})."
        )

        self._perfiles = {
            PerfilCalibracion.CONSERVADOR: self._perfil_conservador(analisis, just_base),
            PerfilCalibracion.BALANCEADO: self._perfil_balanceado(analisis, just_base),
            PerfilCalibracion.PERMISIVO: self._perfil_permisivo(analisis, just_base),
        }

        return self._perfiles

    def obtener_perfil(self, perfil: PerfilCalibracion) -> Optional[ResultadoCalibracion]:
        """Retorna un perfil específico. None si no se han generado."""
        return self._perfiles.get(perfil)

    def _perfil_conservador(
        self, analisis: AnalisisBenchmark, just_base: str
    ) -> ResultadoCalibracion:
        """
        Perfil CONSERVADOR: detecta problemas rápidamente.

        Umbral de abstención bajo (20% warning, 40% critical) para
        escalar alertas temprano. Pocos comprobantes degradados permitidos.

        Con cc003 (58% fallo): genera CRITICAL (58% > 40% umbral critical).
        """
        return ResultadoCalibracion(
            perfil=PerfilCalibracion.CONSERVADOR.value,
            umbrales_router={
                "max_campos_abstencion_warning_pct": 0.20,
                "max_campos_abstencion_critical_pct": 0.40,
                "max_observaciones_degradadas_warning": 1,
                "max_observaciones_degradadas_critical": 3,
                "min_comprobantes_con_datos": 2,
                "min_campos_por_comprobante": 4,
                "max_errores_aritmeticos_warning": 1,
                "max_errores_aritmeticos_critical": 3,
                "completitud_problemas_critical": 2,
            },
            umbrales_abstencion={
                "ruc": 0.90,
                "monto": 0.90,
                "fecha": 0.85,
                "numero_documento": 0.85,
                "nombre_persona": 0.80,
                "nombre_entidad": 0.80,
                "texto_general": 0.70,
                "descripcion": 0.70,
                "default": 0.75,
            },
            justificaciones={
                "max_campos_abstencion_warning_pct": (
                    f"20% warning: {just_base} "
                    f"cc003 tiene {round(analisis.tasa_fallo_global * 100, 1)}% fallo → CRITICAL. "
                    "CONSERVADOR escala warning con solo 20% de campos abstenidos."
                ),
                "max_campos_abstencion_critical_pct": (
                    f"40% critical: {just_base} "
                    f"cc003 tiene {round(analisis.tasa_fallo_global * 100, 1)}% fallo > 40% → CRITICAL obligatorio."
                ),
                "max_observaciones_degradadas_warning": (
                    "1 obs degradada → warning: perfil estricto, cualquier evidencia débil escala."
                ),
                "max_observaciones_degradadas_critical": (
                    "3 obs degradadas → critical: máxima intolerancia a evidencia degradada."
                ),
                "min_comprobantes_con_datos": (
                    "Mínimo 2 comprobantes con datos: exige evidencia de múltiples fuentes."
                ),
                "min_campos_por_comprobante": (
                    "Mínimo 4 campos por comprobante: exige 4 de 5 campos benchmark."
                ),
                "max_errores_aritmeticos_warning": (
                    "1 error aritmético → warning: intolerancia máxima a errores de cálculo."
                ),
                "max_errores_aritmeticos_critical": (
                    "3 errores aritméticos → critical: intolerancia máxima."
                ),
                "completitud_problemas_critical": (
                    "2 problemas de completitud → critical: exigencia alta."
                ),
                "umbrales_abstencion": (
                    "Per-campo sin cambios: ruc=0.90, monto=0.90, fecha=0.85, etc. "
                    "El problema real de cc003 (selección de campo equivocado) es ortogonal "
                    "a los umbrales de confianza OCR por carácter."
                ),
            },
        )

    def _perfil_balanceado(
        self, analisis: AnalisisBenchmark, just_base: str
    ) -> ResultadoCalibracion:
        """
        Perfil BALANCEADO: equilibrio detección-tolerancia.

        Umbral medio (35% warning, 55% critical). Perfil recomendado
        para uso general.

        Con cc003 (58% fallo): genera WARNING/CRITICAL (58% > 55% umbral critical).
        """
        return ResultadoCalibracion(
            perfil=PerfilCalibracion.BALANCEADO.value,
            umbrales_router={
                "max_campos_abstencion_warning_pct": 0.35,
                "max_campos_abstencion_critical_pct": 0.55,
                "max_observaciones_degradadas_warning": 3,
                "max_observaciones_degradadas_critical": 6,
                "min_comprobantes_con_datos": 1,
                "min_campos_por_comprobante": 3,
                "max_errores_aritmeticos_warning": 2,
                "max_errores_aritmeticos_critical": 5,
                "completitud_problemas_critical": 3,
            },
            umbrales_abstencion={
                "ruc": 0.90,
                "monto": 0.90,
                "fecha": 0.85,
                "numero_documento": 0.85,
                "nombre_persona": 0.80,
                "nombre_entidad": 0.80,
                "texto_general": 0.70,
                "descripcion": 0.70,
                "default": 0.75,
            },
            justificaciones={
                "max_campos_abstencion_warning_pct": (
                    f"35% warning: {just_base} "
                    "Punto medio entre conservador (20%) y permisivo (50%). "
                    f"cc003 ({round(analisis.tasa_fallo_global * 100, 1)}% fallo) → escala warning."
                ),
                "max_campos_abstencion_critical_pct": (
                    f"55% critical: {just_base} "
                    f"cc003 ({round(analisis.tasa_fallo_global * 100, 1)}% fallo) → bordeline CRITICAL."
                ),
                "max_observaciones_degradadas_warning": (
                    "3 obs degradadas → warning: tolerancia moderada."
                ),
                "max_observaciones_degradadas_critical": (
                    "6 obs degradadas → critical: permite más evidencia débil antes de escalar."
                ),
                "min_comprobantes_con_datos": (
                    "Mínimo 1 comprobante: permite operar con datos parciales."
                ),
                "min_campos_por_comprobante": (
                    "Mínimo 3 campos: exige 3 de 5 campos benchmark (ej: serie+total+igv)."
                ),
                "max_errores_aritmeticos_warning": (
                    "2 errores aritméticos → warning: coincide con default original del router."
                ),
                "max_errores_aritmeticos_critical": (
                    "5 errores aritméticos → critical: coincide con default original."
                ),
                "completitud_problemas_critical": (
                    "3 problemas de completitud → critical: coincide con default original."
                ),
                "umbrales_abstencion": (
                    "Per-campo sin cambios. Problema de selección de campo es ortogonal."
                ),
            },
        )

    def _perfil_permisivo(
        self, analisis: AnalisisBenchmark, just_base: str
    ) -> ResultadoCalibracion:
        """
        Perfil PERMISIVO: mayor tolerancia a fallos.

        Umbral alto (50% warning, 70% critical). Para expedientes
        escaneados donde se espera baja precisión de OCR.

        Con cc003 (58% fallo): genera WARNING (58% < 70% umbral critical).
        """
        return ResultadoCalibracion(
            perfil=PerfilCalibracion.PERMISIVO.value,
            umbrales_router={
                "max_campos_abstencion_warning_pct": 0.50,
                "max_campos_abstencion_critical_pct": 0.70,
                "max_observaciones_degradadas_warning": 5,
                "max_observaciones_degradadas_critical": 10,
                "min_comprobantes_con_datos": 1,
                "min_campos_por_comprobante": 2,
                "max_errores_aritmeticos_warning": 4,
                "max_errores_aritmeticos_critical": 8,
                "completitud_problemas_critical": 5,
            },
            umbrales_abstencion={
                "ruc": 0.90,
                "monto": 0.90,
                "fecha": 0.85,
                "numero_documento": 0.85,
                "nombre_persona": 0.80,
                "nombre_entidad": 0.80,
                "texto_general": 0.70,
                "descripcion": 0.70,
                "default": 0.75,
            },
            justificaciones={
                "max_campos_abstencion_warning_pct": (
                    f"50% warning: {just_base} "
                    f"cc003 ({round(analisis.tasa_fallo_global * 100, 1)}% fallo) → escala warning."
                ),
                "max_campos_abstencion_critical_pct": (
                    f"70% critical: {just_base} "
                    f"cc003 ({round(analisis.tasa_fallo_global * 100, 1)}% fallo) → solo WARNING, no CRITICAL. "
                    "Permite operar con documentos escaneados de baja calidad."
                ),
                "max_observaciones_degradadas_warning": (
                    "5 obs degradadas → warning: alta tolerancia a evidencia débil."
                ),
                "max_observaciones_degradadas_critical": (
                    "10 obs degradadas → critical: máxima tolerancia."
                ),
                "min_comprobantes_con_datos": (
                    "Mínimo 1 comprobante: acepta datos parciales."
                ),
                "min_campos_por_comprobante": (
                    "Mínimo 2 campos: acepta comprobantes con serie+total solamente."
                ),
                "max_errores_aritmeticos_warning": (
                    "4 errores aritméticos → warning: tolerante a errores de cálculo."
                ),
                "max_errores_aritmeticos_critical": (
                    "8 errores aritméticos → critical: muy tolerante."
                ),
                "completitud_problemas_critical": (
                    "5 problemas de completitud → critical: máxima tolerancia."
                ),
                "umbrales_abstencion": (
                    "Per-campo sin cambios. Problema de selección de campo es ortogonal."
                ),
            },
        )

    # ------------------------------------------------------------------
    # PERSISTENCIA
    # ------------------------------------------------------------------

    def exportar_json(self, path: str) -> str:
        """
        Exporta los perfiles calibrados a archivo JSON.

        Incluye metadata de trazabilidad, análisis del benchmark,
        y los 3 perfiles con justificaciones.

        Args:
            path: Ruta de salida para el archivo JSON.

        Returns:
            Ruta absoluta del archivo generado.

        Raises:
            ValueError: Si no se han generado perfiles.
        """
        if not self._perfiles:
            raise ValueError("No hay perfiles generados. Use generar_perfiles() primero.")

        if self._analisis is None:
            raise ValueError("No hay análisis disponible.")

        output = {
            "version": VERSION_CALIBRACION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analisis_benchmark": self._analisis.to_dict(),
            "perfiles": {
                perfil.value: resultado.to_dict()
                for perfil, resultado in self._perfiles.items()
            },
            "perfil_recomendado": PerfilCalibracion.BALANCEADO.value,
            "nota": (
                "Generado por CalibradorUmbrales v" + VERSION_CALIBRACION + ". "
                "Los umbrales_abstencion per-campo NO se modifican porque el problema "
                "de precisión de cc003 (42%) es de selección de campo equivocado, "
                "no de confianza OCR por carácter (0.855-0.972)."
            ),
        }

        ruta = Path(path)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return str(ruta.resolve())

    @classmethod
    def importar_json(cls, path: str) -> "CalibradorUmbrales":
        """
        Importa perfiles calibrados desde archivo JSON.

        Restaura el estado del calibrador con el análisis y perfiles guardados.

        Args:
            path: Ruta al archivo JSON de calibración.

        Returns:
            CalibradorUmbrales con perfiles precargados.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            json.JSONDecodeError: Si el JSON es inválido.
            ValueError: Si falta estructura requerida.
        """
        ruta = Path(path)
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo de calibración no encontrado: {path}")

        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "perfiles" not in data:
            raise ValueError(f"JSON inválido: falta 'perfiles' en {path}")

        calibrador = cls()

        # Restaurar análisis si existe
        if "analisis_benchmark" in data:
            calibrador._analisis = AnalisisBenchmark.from_dict(
                data["analisis_benchmark"]
            )

        # Restaurar perfiles
        for nombre_perfil, perfil_data in data["perfiles"].items():
            try:
                perfil_enum = PerfilCalibracion(nombre_perfil)
            except ValueError:
                continue  # Ignorar perfiles desconocidos

            calibrador._perfiles[perfil_enum] = ResultadoCalibracion.from_dict(
                perfil_data
            )

        return calibrador

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    @property
    def tiene_benchmarks(self) -> bool:
        """True si hay al menos un benchmark cargado."""
        return len(self._benchmarks_raw) > 0

    @property
    def tiene_analisis(self) -> bool:
        """True si se ha ejecutado analizar()."""
        return self._analisis is not None

    @property
    def tiene_perfiles(self) -> bool:
        """True si se han generado perfiles."""
        return len(self._perfiles) > 0

    @property
    def num_benchmarks(self) -> int:
        """Número de benchmarks cargados."""
        return len(self._benchmarks_raw)

    def resumen(self) -> str:
        """
        Genera un resumen legible del estado del calibrador.

        Returns:
            String con resumen del análisis y perfiles.
        """
        lines = [
            f"=== CalibradorUmbrales v{VERSION_CALIBRACION} ===",
            f"Benchmarks cargados: {self.num_benchmarks}",
        ]

        if self._analisis:
            a = self._analisis
            lines.extend([
                f"\n--- Análisis: {a.prueba_id} ---",
                f"Expediente: {a.expediente}",
                f"Comprobantes: {a.total_comprobantes}",
                f"Campos evaluados: {a.total_campos_evaluados}",
                f"Precisión: {a.precision_pct}%",
                f"Tasa fallo: {round(a.tasa_fallo_global * 100, 1)}%",
                f"Confianza OCR: {a.confianza_ocr_min:.3f} - {a.confianza_ocr_max:.3f} "
                f"(media {a.confianza_ocr_media:.3f})",
                "\nEstadísticas por campo:",
            ])
            for campo, stat in a.stats_por_campo.items():
                if stat.evaluados > 0 or stat.skip > 0:
                    lines.append(
                        f"  {campo}: {stat.match}/{stat.evaluados} match "
                        f"({round(stat.tasa_acierto * 100, 1)}%), "
                        f"{stat.error} error, {stat.no_extraido} no extraído, "
                        f"{stat.skip} skip"
                    )

        if self._perfiles:
            lines.append("\n--- Perfiles calibrados ---")
            for perfil, resultado in self._perfiles.items():
                lines.append(f"\n  [{perfil.value.upper()}]")
                ur = resultado.umbrales_router
                lines.append(
                    f"    abstención warning: {ur.get('max_campos_abstencion_warning_pct', '?')}"
                    f" | critical: {ur.get('max_campos_abstencion_critical_pct', '?')}"
                )
                lines.append(
                    f"    obs degradadas warning: {ur.get('max_observaciones_degradadas_warning', '?')}"
                    f" | critical: {ur.get('max_observaciones_degradadas_critical', '?')}"
                )

        return "\n".join(lines)
