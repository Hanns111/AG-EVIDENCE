# -*- coding: utf-8 -*-
"""
Capa B — Validadores Deterministas de Campos
==============================================
Validaciones formales por tipo de campo extraido.

Cada validador recibe un valor (string) y retorna un ValidationResult
indicando si el valor es valido, que flags tiene, y si requiere
revision humana.

Principio: Solo validacion de formato y consistencia.
No extraccion, no inferencia, no estimacion.

Validadores disponibles:
  - validar_ruc: RUC peruano (11 digitos, prefijo 10/20)
  - validar_serie_numero: Serie-numero de comprobante SUNAT
  - validar_monto: Monto monetario (numerico, positivo)
  - validar_fecha: Fecha en formato DD/MM/YYYY o ISO
  - validar_consistencia_aritmetica: subtotal + IGV = total

Uso:
    from src.rules.field_validators import validar_ruc, ValidationResult

    result = validar_ruc("20100039207")
    if not result.valido:
        print(f"Flags: {result.flags}")
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


# ==============================================================================
# DATACLASSES
# ==============================================================================


@dataclass
class ValidationResult:
    """
    Resultado de validacion de un campo individual.

    Attributes:
        valido: True si el valor pasa todas las validaciones.
        flags: Lista de codigos de flag (ej: "RUC_LONGITUD_INVALIDA").
        needs_human_review: True si el campo requiere revision manual.
        detalle: Descripcion legible del resultado.
    """

    valido: bool
    flags: List[str] = field(default_factory=list)
    needs_human_review: bool = False
    detalle: str = ""

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "valido": self.valido,
            "flags": self.flags,
            "needs_human_review": self.needs_human_review,
            "detalle": self.detalle,
        }


@dataclass
class ValidationFlag:
    """
    Flag de validacion con contexto.

    Attributes:
        campo: Nombre del campo validado.
        codigo: Codigo del flag (ej: "RUC_CHECKSUM_FAIL").
        detalle: Descripcion legible.
        needs_human_review: Si requiere revision manual.
    """

    campo: str
    codigo: str
    detalle: str = ""
    needs_human_review: bool = False

    def to_dict(self) -> dict:
        return {
            "campo": self.campo,
            "codigo": self.codigo,
            "detalle": self.detalle,
            "needs_human_review": self.needs_human_review,
        }


# ==============================================================================
# VALIDADOR DE RUC
# ==============================================================================


def validar_ruc(valor: Optional[str]) -> ValidationResult:
    """
    Valida un RUC peruano.

    Reglas:
      - Exactamente 11 digitos
      - Solo caracteres numericos
      - Prefijo 10 (persona natural) o 20 (persona juridica)

    Args:
        valor: RUC como string.

    Returns:
        ValidationResult con flags si invalido.
    """
    if valor is None or valor.strip() == "":
        return ValidationResult(
            valido=False,
            flags=["RUC_VACIO"],
            needs_human_review=True,
            detalle="RUC vacio o nulo",
        )

    valor = valor.strip()
    flags = []

    # Solo digitos
    if not valor.isdigit():
        flags.append("RUC_NO_NUMERICO")

    # Longitud exacta
    if len(valor) != 11:
        flags.append("RUC_LONGITUD_INVALIDA")

    # Prefijo valido (10=PN, 20=PJ, 15=no domiciliado, 17=otro)
    prefijos_validos = {"10", "15", "17", "20"}
    if len(valor) >= 2 and valor[:2] not in prefijos_validos:
        flags.append("RUC_PREFIJO_INVALIDO")

    if flags:
        return ValidationResult(
            valido=False,
            flags=flags,
            needs_human_review=True,
            detalle=f"RUC '{valor}' no cumple validacion: {', '.join(flags)}",
        )

    return ValidationResult(
        valido=True,
        detalle=f"RUC '{valor}' valido (prefijo {valor[:2]})",
    )


# ==============================================================================
# VALIDADOR DE SERIE-NUMERO
# ==============================================================================

# Patrones SUNAT de serie-numero de comprobante
_PATRONES_SERIE_NUMERO = [
    # Factura electronica: F + 3 digitos - 1 a 8 digitos
    (r"^F\d{3}-\d{1,8}$", "FACTURA_ELECTRONICA"),
    # Boleta electronica: B + 3 digitos - 1 a 8 digitos
    (r"^B\d{3}-\d{1,8}$", "BOLETA_ELECTRONICA"),
    # Factura/boleta con prefijo E (electronica): E + 3 digitos - digitos
    (r"^E\d{3}-\d{1,8}$", "COMPROBANTE_ELECTRONICO"),
    # Boleta de venta: BV o EB + digitos
    (r"^(BV|EB)\d{2,3}-\d{1,8}$", "BOLETA_VENTA"),
    # Factura con prefijo FO (factura original): FO + digitos
    (r"^FO\d{2,3}-\d{1,8}$", "FACTURA_ORIGINAL"),
    # Factura con prefijo FD: FD + digitos
    (r"^FD\d{1,3}-\d{1,8}$", "FACTURA_FD"),
    # Factura con prefijo FQ: FQ + digitos
    (r"^FQ\d{2,3}-\d{1,8}$", "FACTURA_FQ"),
    # Recibo de servicios publicos: patron numerico largo
    (r"^\d{4,}-\d{8,}$", "RECIBO_SERVICIO"),
    # Declaracion jurada: 0000-NNN
    (r"^0{4}-\d{1,6}$", "DECLARACION_JURADA"),
]


def validar_serie_numero(valor: Optional[str]) -> ValidationResult:
    """
    Valida formato de serie-numero de comprobante SUNAT.

    Acepta multiples formatos (factura, boleta, recibo, DJ).

    Args:
        valor: Serie-numero como string (ej: "F001-468").

    Returns:
        ValidationResult con tipo de comprobante detectado.
    """
    if valor is None or valor.strip() == "":
        return ValidationResult(
            valido=False,
            flags=["SERIE_NUMERO_VACIO"],
            needs_human_review=True,
            detalle="Serie-numero vacio o nulo",
        )

    valor = valor.strip().upper()
    flags = []

    # Verificar si contiene el separador
    if "-" not in valor:
        flags.append("SERIE_NUMERO_SIN_SEPARADOR")
        return ValidationResult(
            valido=False,
            flags=flags,
            needs_human_review=True,
            detalle=f"Serie-numero '{valor}' no contiene separador '-'",
        )

    # Buscar patron valido
    for patron, tipo in _PATRONES_SERIE_NUMERO:
        if re.match(patron, valor):
            return ValidationResult(
                valido=True,
                detalle=f"Serie-numero '{valor}' valido (tipo: {tipo})",
            )

    # Ningun patron coincidio — formato desconocido
    flags.append("SERIE_NUMERO_FORMATO_DESCONOCIDO")
    return ValidationResult(
        valido=False,
        flags=flags,
        needs_human_review=True,
        detalle=f"Serie-numero '{valor}' no coincide con ningun patron SUNAT conocido",
    )


# ==============================================================================
# VALIDADOR DE MONTO
# ==============================================================================


def validar_monto(valor: Optional[str]) -> ValidationResult:
    """
    Valida un monto monetario.

    Reglas:
      - Convertible a float
      - Positivo o cero
      - Maximo 2 decimales

    Args:
        valor: Monto como string (ej: "250.00", "1,234.56").

    Returns:
        ValidationResult.
    """
    if valor is None or str(valor).strip() == "":
        return ValidationResult(
            valido=False,
            flags=["MONTO_VACIO"],
            needs_human_review=True,
            detalle="Monto vacio o nulo",
        )

    valor_str = str(valor).strip()

    # Limpiar formato: quitar S/, comas de miles, espacios
    valor_limpio = valor_str.replace("S/", "").replace(",", "").strip()
    valor_limpio = valor_limpio.replace(" ", "")

    flags = []

    try:
        monto = float(valor_limpio)
    except (ValueError, TypeError):
        return ValidationResult(
            valido=False,
            flags=["MONTO_NO_NUMERICO"],
            needs_human_review=True,
            detalle=f"Monto '{valor_str}' no es convertible a numero",
        )

    if monto < 0:
        flags.append("MONTO_NEGATIVO")

    # Verificar maximo 2 decimales
    if "." in valor_limpio:
        decimales = valor_limpio.split(".")[1]
        if len(decimales) > 2:
            flags.append("MONTO_MAS_DE_2_DECIMALES")

    if flags:
        return ValidationResult(
            valido=False,
            flags=flags,
            needs_human_review=True,
            detalle=f"Monto '{valor_str}' tiene flags: {', '.join(flags)}",
        )

    return ValidationResult(
        valido=True,
        detalle=f"Monto '{valor_str}' valido ({monto:.2f})",
    )


# ==============================================================================
# VALIDADOR DE FECHA
# ==============================================================================

_FORMATOS_FECHA = [
    "%d/%m/%Y",  # DD/MM/YYYY (formato peruano)
    "%Y-%m-%d",  # ISO 8601
    "%d-%m-%Y",  # DD-MM-YYYY
    "%d.%m.%Y",  # DD.MM.YYYY
]


def validar_fecha(
    valor: Optional[str],
    rango_min: str = "2020-01-01",
    rango_max: str = "2030-12-31",
) -> ValidationResult:
    """
    Valida una fecha en formatos aceptados.

    Reglas:
      - Debe coincidir con alguno de los formatos aceptados
      - Debe estar dentro del rango razonable (2020-2030)

    Args:
        valor: Fecha como string.
        rango_min: Fecha minima aceptable (ISO).
        rango_max: Fecha maxima aceptable (ISO).

    Returns:
        ValidationResult.
    """
    if valor is None or valor.strip() == "":
        return ValidationResult(
            valido=False,
            flags=["FECHA_VACIA"],
            needs_human_review=True,
            detalle="Fecha vacia o nula",
        )

    valor = valor.strip()
    flags = []

    # Intentar parsear con cada formato
    fecha_parseada = None
    for fmt in _FORMATOS_FECHA:
        try:
            fecha_parseada = datetime.strptime(valor, fmt)
            break
        except ValueError:
            continue

    if fecha_parseada is None:
        return ValidationResult(
            valido=False,
            flags=["FECHA_FORMATO_INVALIDO"],
            needs_human_review=True,
            detalle=f"Fecha '{valor}' no coincide con ningun formato aceptado",
        )

    # Verificar rango
    fecha_min = datetime.strptime(rango_min, "%Y-%m-%d")
    fecha_max = datetime.strptime(rango_max, "%Y-%m-%d")

    if fecha_parseada < fecha_min or fecha_parseada > fecha_max:
        flags.append("FECHA_FUERA_DE_RANGO")
        return ValidationResult(
            valido=False,
            flags=flags,
            needs_human_review=True,
            detalle=f"Fecha '{valor}' fuera de rango [{rango_min}, {rango_max}]",
        )

    return ValidationResult(
        valido=True,
        detalle=f"Fecha '{valor}' valida ({fecha_parseada.strftime('%Y-%m-%d')})",
    )


# ==============================================================================
# VALIDACION DE CONSISTENCIA ARITMETICA
# ==============================================================================


def validar_consistencia_aritmetica(
    valor_venta: Optional[float],
    igv: Optional[float],
    total: Optional[float],
    tolerancia: float = 0.02,
) -> ValidationResult:
    """
    Verifica que valor_venta + igv == total (con tolerancia).

    Args:
        valor_venta: Subtotal/base imponible.
        igv: Monto del IGV.
        total: Monto total del comprobante.
        tolerancia: Diferencia maxima aceptable en soles.

    Returns:
        ValidationResult con flag si hay discrepancia.
    """
    flags = []

    if valor_venta is None or igv is None or total is None:
        faltantes = []
        if valor_venta is None:
            faltantes.append("valor_venta")
        if igv is None:
            faltantes.append("igv")
        if total is None:
            faltantes.append("total")
        return ValidationResult(
            valido=False,
            flags=["ARITMETICA_CAMPOS_FALTANTES"],
            needs_human_review=True,
            detalle=f"Campos faltantes para check aritmetico: {', '.join(faltantes)}",
        )

    suma = round(valor_venta + igv, 2)
    diferencia = abs(suma - total)

    if diferencia > tolerancia:
        flags.append("ARITMETICA_DISCREPANCIA")
        return ValidationResult(
            valido=False,
            flags=flags,
            needs_human_review=True,
            detalle=(
                f"valor_venta({valor_venta:.2f}) + igv({igv:.2f}) = "
                f"{suma:.2f} != total({total:.2f}). "
                f"Diferencia: S/{diferencia:.2f}"
            ),
        )

    return ValidationResult(
        valido=True,
        detalle=(f"Consistencia OK: {valor_venta:.2f} + {igv:.2f} = {suma:.2f} == {total:.2f}"),
    )
