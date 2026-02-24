# -*- coding: utf-8 -*-
"""
Modulo de Extraccion de Campos
===============================
Subsistema de extraccion estructurada de datos de documentos.

Componentes:
  - abstencion: Politica formal de abstencion operativa (Tarea #12)
  - local_analyst: Interfaz para IA local como analista (Capa C)
  - expediente_contract: Contrato de datos tipado (Tarea #17)
  - confidence_router: Router de confianza + Integrity Checkpoint (Tarea #18)
  - calibracion: Calibración de umbrales con distribución real (Tarea #19)
  - excel_writer: Hoja DIAGNOSTICO en Excel (Tarea #20)
"""

from .abstencion import (
    CampoExtraido,
    EvidenceStatus,
    UmbralesAbstencion,
    ResultadoAbstencion,
    RazonAbstencion,
    AbstencionPolicy,
    FUENTE_ABSTENCION,
    FRASE_ABSTENCION_ESTANDAR,
)

from .local_analyst import (
    AnalysisNotes,
    analyze_evidence,
    CAMPOS_PROBATORIOS,
)

from .confidence_router import (
    VERSION_ROUTER,
    UmbralesRouter,
    EvidenceEnforcer,
    DetalleEnforcement,
    ReporteEnforcement,
    SeccionDiagnostico,
    DiagnosticoExpediente,
    IntegrityCheckpoint,
    DecisionCheckpoint,
    ResultadoRouter,
    ConfidenceRouter,
)

from .calibracion import (
    VERSION_CALIBRACION,
    PerfilCalibracion,
    EstadisticaCampo,
    AnalisisBenchmark,
    ResultadoCalibracion,
    CalibradorUmbrales,
)

from .excel_writer import (
    VERSION_EXCEL_WRITER,
    NOMBRE_HOJA,
    EscritorDiagnostico,
    escribir_diagnostico,
)

from .expediente_contract import (
    VERSION_CONTRATO,
    TipoComprobante,
    CategoriaGasto,
    MetodoExtraccionContrato,
    TipoBoleto,
    ConfianzaGlobal,
    IntegridadStatus,
    DatosEmisor,
    DatosComprobante,
    DatosAdquirente,
    CondicionesComerciales,
    ItemDetalle,
    TotalesTributos,
    ClasificacionGasto,
    DatosHospedaje,
    DatosMovilidad,
    ValidacionesAritmeticas,
    MetadatosExtraccion,
    ComprobanteExtraido,
    GastoDeclaracionJurada,
    BoletoTransporte,
    ItemAnexo3,
    DatosAnexo3,
    DocumentosConvenio,
    ArchivoFuente,
    ResumenExtraccion,
    IntegridadExpediente,
    ExpedienteJSON,
)

__all__ = [
    # abstencion.py (Tarea #12)
    "CampoExtraido",
    "EvidenceStatus",
    "UmbralesAbstencion",
    "ResultadoAbstencion",
    "RazonAbstencion",
    "AbstencionPolicy",
    "FUENTE_ABSTENCION",
    "FRASE_ABSTENCION_ESTANDAR",
    # local_analyst.py (Capa C)
    "AnalysisNotes",
    "analyze_evidence",
    "CAMPOS_PROBATORIOS",
    # confidence_router.py (Tarea #18)
    "VERSION_ROUTER",
    "UmbralesRouter",
    "EvidenceEnforcer",
    "DetalleEnforcement",
    "ReporteEnforcement",
    "SeccionDiagnostico",
    "DiagnosticoExpediente",
    "IntegrityCheckpoint",
    "DecisionCheckpoint",
    "ResultadoRouter",
    "ConfidenceRouter",
    # calibracion.py (Tarea #19)
    "VERSION_CALIBRACION",
    "PerfilCalibracion",
    "EstadisticaCampo",
    "AnalisisBenchmark",
    "ResultadoCalibracion",
    "CalibradorUmbrales",
    # excel_writer.py (Tarea #20)
    "VERSION_EXCEL_WRITER",
    "NOMBRE_HOJA",
    "EscritorDiagnostico",
    "escribir_diagnostico",
    # expediente_contract.py (Tarea #17)
    "VERSION_CONTRATO",
    "TipoComprobante",
    "CategoriaGasto",
    "MetodoExtraccionContrato",
    "TipoBoleto",
    "ConfianzaGlobal",
    "IntegridadStatus",
    "DatosEmisor",
    "DatosComprobante",
    "DatosAdquirente",
    "CondicionesComerciales",
    "ItemDetalle",
    "TotalesTributos",
    "ClasificacionGasto",
    "DatosHospedaje",
    "DatosMovilidad",
    "ValidacionesAritmeticas",
    "MetadatosExtraccion",
    "ComprobanteExtraido",
    "GastoDeclaracionJurada",
    "BoletoTransporte",
    "ItemAnexo3",
    "DatosAnexo3",
    "DocumentosConvenio",
    "ArchivoFuente",
    "ResumenExtraccion",
    "IntegridadExpediente",
    "ExpedienteJSON",
]
