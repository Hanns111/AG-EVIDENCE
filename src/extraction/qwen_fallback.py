# -*- coding: utf-8 -*-
"""
Qwen Fallback — Cliente VLM para extracción de comprobantes
============================================================
Tarea #23 del Plan de Desarrollo (Fase 3: Parseo Profundo)

Cliente que envía imágenes de comprobantes a Qwen3-VL:8b vía Ollama
y convierte la respuesta en ComprobanteExtraido tipado (Grupos A-K).

Principios:
  - Literalidad forense: la IA extrae lo que ve, Python valida (Grupo J)
  - Retry automático: max 2 intentos para JSON corrupto
  - Deduplicación: por serie_numero entre chunks superpuestos
  - Abstención: si falla tras retries → CampoExtraido con ILEGIBLE

Hallazgos absorbidos de Viáticos AI (informe técnico 2026-03-12):
  - Prompt forense para comprobantes peruanos
  - Chunking con overlap 2 páginas + deduplicación por serie_numero
  - Retry automático (max 2) para JSON corrupto antes de abstención
  - VLM extrae texto, Python parsea con regex. NUNCA pedir JSON final al LLM.

Uso:
    from src.extraction.qwen_fallback import QwenFallbackClient

    client = QwenFallbackClient()
    comprobantes = client.extraer_comprobantes(
        imagenes_b64=["base64..."],
        archivo="expediente.pdf",
        paginas=[1, 2, 3],
    )

Versión: 1.0.0
"""

import base64
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Asegurar path del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import VLM_CONFIG, MetodoExtraccion
from src.extraction.abstencion import CampoExtraido
from src.extraction.expediente_contract import (
    ClasificacionGasto,
    ComprobanteExtraido,
    CondicionesComerciales,
    DatosAdquirente,
    DatosComprobante,
    DatosEmisor,
    DatosHospedaje,
    DatosMovilidad,
    ItemDetalle,
    MetadatosExtraccion,
    TotalesTributos,
    ValidacionesAritmeticas,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTES
# ==============================================================================

VERSION_QWEN_FALLBACK = "1.0.0"

TOLERANCIA_ARITMETICA = 0.02  # ±0.02 soles

# Prompt forense para extracción de comprobantes peruanos
EXTRACTION_PROMPT = """Eres un extractor forense de comprobantes de pago peruanos.

REGLA ABSOLUTA: Extrae SOLO lo que ves literalmente en la imagen.
- NO calcules nada
- NO inventes datos
- NO autocompletes campos que no puedes leer
- Si un campo no es visible, usa null
- Si un valor es parcialmente legible, extrae lo que puedas y marca confianza "baja"

Extrae los siguientes campos del comprobante de pago en la imagen y devuelve ÚNICAMENTE un JSON válido (sin texto adicional, sin markdown, sin explicaciones):

{
  "grupo_a_emisor": {
    "ruc_emisor": "string o null",
    "razon_social": "string o null",
    "nombre_comercial": "string o null",
    "direccion_emisor": "string o null",
    "ubigeo_emisor": "string o null"
  },
  "grupo_b_comprobante": {
    "tipo_comprobante": "FACTURA|BOLETA|NOTA_CREDITO|NOTA_DEBITO|RECIBO_HONORARIOS",
    "serie": "string",
    "numero": "string",
    "fecha_emision": "DD/MM/YYYY",
    "fecha_vencimiento": "DD/MM/YYYY o null",
    "moneda": "PEN|USD|EUR",
    "forma_pago": "CONTADO|CREDITO|null",
    "es_electronico": true
  },
  "grupo_c_adquirente": {
    "ruc_adquirente": "string o null",
    "razon_social_adquirente": "string o null",
    "direccion_adquirente": "string o null"
  },
  "grupo_d_condiciones": {
    "condicion_pago": "string o null",
    "guia_remision": "string o null",
    "orden_compra": "string o null",
    "observaciones": "string o null"
  },
  "grupo_e_items": [
    {
      "cantidad": 0.0,
      "unidad": "string o null",
      "descripcion": "string",
      "valor_unitario": 0.00,
      "importe": 0.00
    }
  ],
  "grupo_f_totales": {
    "subtotal": 0.00,
    "igv_tasa": 18,
    "igv_monto": 0.00,
    "total_gravado": 0.00,
    "total_exonerado": 0.00,
    "total_inafecto": 0.00,
    "total_gratuito": null,
    "otros_cargos": null,
    "descuentos": null,
    "importe_total": 0.00,
    "monto_letras": "string o null"
  },
  "grupo_g_clasificacion": {
    "categoria_gasto": "ALIMENTACION|HOSPEDAJE|TRANSPORTE|MOVILIDAD_LOCAL|OTROS",
    "subcategoria": "string o null"
  },
  "grupo_h_hospedaje": {
    "fecha_checkin": "DD/MM/YYYY o null",
    "fecha_checkout": "DD/MM/YYYY o null",
    "numero_noches": null,
    "numero_habitacion": "string o null",
    "nombre_huesped": "string o null",
    "numero_reserva": "string o null"
  },
  "grupo_i_movilidad": {
    "origen": "string o null",
    "destino": "string o null",
    "fecha_servicio": "string o null",
    "placa_vehiculo": "string o null",
    "nombre_pasajero": "string o null"
  },
  "campos_no_encontrados": ["lista de campos obligatorios no visibles"],
  "confianza_global": "alta|media|baja"
}

IMPORTANTE:
- Los montos son NÚMEROS (no strings). Ejemplo: 150.00, no "150.00"
- Las fechas son STRINGS en formato DD/MM/YYYY
- Si el comprobante NO es de hospedaje, grupo_h debe tener todos los campos en null
- Si el comprobante NO es de transporte/movilidad, grupo_i debe tener todos null
- El campo confianza_global refleja tu certeza general sobre la extracción

Responde SOLO con el JSON. Nada más."""


# ==============================================================================
# DATACLASSES DE RESULTADO
# ==============================================================================


@dataclass
class ResultadoVLM:
    """Resultado crudo de una invocación al VLM."""

    exito: bool
    json_extraido: Optional[Dict[str, Any]] = None
    error: str = ""
    tiempo_inferencia_s: float = 0.0
    tokens_evaluados: int = 0
    intentos: int = 0
    modelo: str = ""


@dataclass
class ResultadoExtraccion:
    """Resultado completo de la extracción de comprobantes de un expediente."""

    comprobantes: List[ComprobanteExtraido] = field(default_factory=list)
    total_paginas: int = 0
    paginas_procesadas: int = 0
    paginas_con_comprobante: int = 0
    tiempo_total_s: float = 0.0
    errores: List[str] = field(default_factory=list)
    deduplicados: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_comprobantes": len(self.comprobantes),
            "total_paginas": self.total_paginas,
            "paginas_procesadas": self.paginas_procesadas,
            "paginas_con_comprobante": self.paginas_con_comprobante,
            "tiempo_total_s": round(self.tiempo_total_s, 2),
            "errores": self.errores,
            "deduplicados": self.deduplicados,
        }


# ==============================================================================
# CLIENTE VLM
# ==============================================================================


class QwenFallbackClient:
    """
    Cliente para extracción de comprobantes via Qwen3-VL:8b (Ollama).

    Envía imágenes de páginas PDF al VLM con prompt forense,
    parsea la respuesta JSON, y convierte a ComprobanteExtraido tipado.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        trace_logger: Any = None,
    ):
        cfg = config or VLM_CONFIG
        self.model = cfg.get("model", "qwen3-vl:8b")
        self.fallback_model = cfg.get("fallback_model", "qwen2.5vl:7b")
        self.ollama_url = cfg.get("ollama_url", "http://localhost:11434")
        self.timeout = cfg.get("timeout_seconds", 120)
        self.max_tokens = cfg.get("max_tokens", 16384)
        self.temperature = cfg.get("temperature", 0.1)
        self.num_ctx = cfg.get("num_ctx", 16384)
        self.max_retries = cfg.get("max_retries", 2)
        self.trace_logger = trace_logger

    # ------------------------------------------------------------------
    # Verificación de conectividad
    # ------------------------------------------------------------------

    def healthcheck(self) -> bool:
        """Verifica que Ollama esté corriendo y el modelo disponible."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            nombres = [m["name"] for m in data.get("models", [])]
            return self.model in nombres
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Invocación VLM
    # ------------------------------------------------------------------

    def _invocar_vlm(self, image_b64: str, modelo: str) -> ResultadoVLM:
        """
        Envía una imagen al VLM y retorna el JSON extraído.
        Maneja thinking blocks de qwen3-vl y retry automático.
        """
        payload = {
            "model": modelo,
            "messages": [
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        for intento in range(1, self.max_retries + 1):
            start = time.time()
            try:
                req = urllib.request.Request(
                    f"{self.ollama_url}/api/chat",
                    data=payload_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())

                elapsed = time.time() - start
                content = data.get("message", {}).get("content", "")
                tokens = data.get("eval_count", 0)

                # Extraer JSON de la respuesta (maneja thinking blocks)
                parsed = self._extraer_json(content)
                if parsed is not None:
                    self._log_info(
                        f"VLM extracción OK (intento {intento}, {elapsed:.1f}s, {tokens} tokens)"
                    )
                    return ResultadoVLM(
                        exito=True,
                        json_extraido=parsed,
                        tiempo_inferencia_s=elapsed,
                        tokens_evaluados=tokens,
                        intentos=intento,
                        modelo=modelo,
                    )

                # JSON no parseable — retry
                self._log_warning(
                    f"JSON corrupto intento {intento}/{self.max_retries}: {content[:100]}"
                )

            except urllib.error.URLError as e:
                elapsed = time.time() - start
                self._log_warning(f"Error de conexión intento {intento}: {e}")
                return ResultadoVLM(
                    exito=False,
                    error=f"connection_error: {e}",
                    tiempo_inferencia_s=elapsed,
                    intentos=intento,
                    modelo=modelo,
                )
            except Exception as e:
                elapsed = time.time() - start
                self._log_warning(f"Error inesperado intento {intento}: {e}")
                if intento == self.max_retries:
                    return ResultadoVLM(
                        exito=False,
                        error=f"unexpected: {e}",
                        tiempo_inferencia_s=elapsed,
                        intentos=intento,
                        modelo=modelo,
                    )

        # Agotados los reintentos
        return ResultadoVLM(
            exito=False,
            error=f"JSON corrupto tras {self.max_retries} intentos",
            intentos=self.max_retries,
            modelo=modelo,
        )

    def _extraer_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extrae JSON de la respuesta del VLM.
        Maneja: thinking blocks, markdown code blocks, texto extra.
        """
        if not content or not content.strip():
            return None

        text = content.strip()

        # 1. Eliminar bloques <think>...</think> de qwen3-vl
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. Eliminar markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Quitar primera y última línea (```json y ```)
            if lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1]).strip()
            else:
                text = "\n".join(lines[1:]).strip()

        # 3. Buscar primer { y último } si aún no es JSON puro
        if not text.startswith("{"):
            brace_start = text.find("{")
            brace_end = text.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                text = text[brace_start : brace_end + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------------
    # Extracción principal
    # ------------------------------------------------------------------

    def extraer_comprobante(
        self,
        image_b64: str,
        archivo: str = "",
        pagina: int = 0,
    ) -> Optional[ComprobanteExtraido]:
        """
        Extrae un comprobante de una imagen individual.

        Args:
            image_b64: Imagen en base64.
            archivo: Nombre del archivo fuente.
            pagina: Número de página (1-indexed).

        Returns:
            ComprobanteExtraido tipado o None si falla.
        """
        resultado = self._invocar_vlm(image_b64, self.model)

        # Si modelo principal falla, intentar fallback
        if not resultado.exito and self.fallback_model:
            self._log_warning(
                f"Modelo principal {self.model} falló, intentando fallback {self.fallback_model}"
            )
            resultado = self._invocar_vlm(image_b64, self.fallback_model)

        if not resultado.exito or resultado.json_extraido is None:
            self._log_warning(f"Extracción fallida para {archivo} pág {pagina}: {resultado.error}")
            return None

        # Convertir JSON crudo a ComprobanteExtraido tipado
        comprobante = self._json_a_comprobante(
            resultado.json_extraido,
            archivo=archivo,
            pagina=pagina,
            modelo=resultado.modelo,
            tiempo_s=resultado.tiempo_inferencia_s,
        )

        # Validar aritmética (Grupo J) — Python, NUNCA la IA
        comprobante.grupo_j = self._validar_aritmetica(comprobante)

        return comprobante

    def extraer_comprobantes(
        self,
        imagenes_b64: List[str],
        archivo: str = "",
        paginas: Optional[List[int]] = None,
    ) -> ResultadoExtraccion:
        """
        Extrae comprobantes de múltiples imágenes con deduplicación.

        Args:
            imagenes_b64: Lista de imágenes en base64.
            archivo: Nombre del archivo fuente.
            paginas: Lista de números de página (1-indexed).

        Returns:
            ResultadoExtraccion con comprobantes deduplicados.
        """
        if paginas is None:
            paginas = list(range(1, len(imagenes_b64) + 1))

        resultado = ResultadoExtraccion(total_paginas=len(imagenes_b64))
        start_total = time.time()
        todos: List[ComprobanteExtraido] = []

        for idx, img_b64 in enumerate(imagenes_b64):
            pag = paginas[idx] if idx < len(paginas) else idx + 1
            self._log_info(f"Procesando página {pag}/{len(imagenes_b64)}")

            comprobante = self.extraer_comprobante(
                image_b64=img_b64,
                archivo=archivo,
                pagina=pag,
            )
            resultado.paginas_procesadas += 1

            if comprobante is not None:
                todos.append(comprobante)
                resultado.paginas_con_comprobante += 1

        # Deduplicar por serie_numero
        antes = len(todos)
        resultado.comprobantes = self._deduplicar(todos)
        resultado.deduplicados = antes - len(resultado.comprobantes)
        resultado.tiempo_total_s = time.time() - start_total

        if resultado.deduplicados > 0:
            self._log_info(
                f"Deduplicados: {resultado.deduplicados} comprobantes "
                f"(de {antes} a {len(resultado.comprobantes)})"
            )

        return resultado

    # ------------------------------------------------------------------
    # Conversión JSON → ComprobanteExtraido tipado
    # ------------------------------------------------------------------

    def _json_a_comprobante(
        self,
        data: Dict[str, Any],
        archivo: str = "",
        pagina: int = 0,
        modelo: str = "",
        tiempo_s: float = 0.0,
    ) -> ComprobanteExtraido:
        """Convierte el JSON crudo del VLM a un ComprobanteExtraido tipado."""
        confianza_global = data.get("confianza_global", "baja")
        confianza_num = {"alta": 0.95, "media": 0.75, "baja": 0.45}.get(confianza_global, 0.45)
        metodo = MetodoExtraccion.HEURISTICA  # VLM es heurística

        def _campo(
            nombre: str,
            valor: Any,
            tipo: str = "",
            confianza_override: Optional[float] = None,
        ) -> Optional[CampoExtraido]:
            if valor is None:
                return None
            return CampoExtraido(
                nombre_campo=nombre,
                valor=str(valor) if not isinstance(valor, str) else valor,
                archivo=archivo,
                pagina=pagina,
                confianza=confianza_override if confianza_override is not None else confianza_num,
                metodo=metodo,
                snippet=f"VLM:{modelo}",
                regla_aplicada="qwen_fallback_v1",
                tipo_campo=tipo,
                motor_ocr=modelo,
            )

        # Grupo A — Emisor
        ga = data.get("grupo_a_emisor", {}) or {}
        grupo_a = DatosEmisor(
            ruc_emisor=_campo("ruc_emisor", ga.get("ruc_emisor"), "ruc"),
            razon_social=_campo("razon_social", ga.get("razon_social"), "texto"),
            nombre_comercial=_campo("nombre_comercial", ga.get("nombre_comercial"), "texto"),
            direccion_emisor=_campo("direccion_emisor", ga.get("direccion_emisor"), "texto"),
            ubigeo_emisor=_campo("ubigeo_emisor", ga.get("ubigeo_emisor"), "texto"),
        )

        # Grupo B — Comprobante
        gb = data.get("grupo_b_comprobante", {}) or {}
        grupo_b = DatosComprobante(
            tipo_comprobante=_campo("tipo_comprobante", gb.get("tipo_comprobante"), "tipo"),
            serie=_campo("serie", gb.get("serie"), "serie"),
            numero=_campo("numero", gb.get("numero"), "numero"),
            fecha_emision=_campo("fecha_emision", gb.get("fecha_emision"), "fecha"),
            fecha_vencimiento=_campo("fecha_vencimiento", gb.get("fecha_vencimiento"), "fecha"),
            moneda=_campo("moneda", gb.get("moneda"), "moneda"),
            forma_pago=_campo("forma_pago", gb.get("forma_pago"), "texto"),
            es_electronico=_campo("es_electronico", gb.get("es_electronico"), "booleano"),
        )

        # Grupo C — Adquirente
        gc = data.get("grupo_c_adquirente", {}) or {}
        grupo_c = DatosAdquirente(
            ruc_adquirente=_campo("ruc_adquirente", gc.get("ruc_adquirente"), "ruc"),
            razon_social_adquirente=_campo(
                "razon_social_adquirente", gc.get("razon_social_adquirente"), "texto"
            ),
            direccion_adquirente=_campo(
                "direccion_adquirente", gc.get("direccion_adquirente"), "texto"
            ),
        )

        # Grupo D — Condiciones
        gd = data.get("grupo_d_condiciones", {}) or {}
        grupo_d = CondicionesComerciales(
            condicion_pago=_campo("condicion_pago", gd.get("condicion_pago"), "texto"),
            guia_remision=_campo("guia_remision", gd.get("guia_remision"), "texto"),
            orden_compra=_campo("orden_compra", gd.get("orden_compra"), "texto"),
            observaciones=_campo("observaciones", gd.get("observaciones"), "texto"),
        )

        # Grupo E — Ítems
        ge_raw = data.get("grupo_e_items", []) or []
        grupo_e = []
        for item_raw in ge_raw:
            if not isinstance(item_raw, dict):
                continue
            grupo_e.append(
                ItemDetalle(
                    cantidad=_campo("cantidad", item_raw.get("cantidad"), "monto"),
                    unidad=_campo("unidad", item_raw.get("unidad"), "texto"),
                    descripcion=_campo("descripcion", item_raw.get("descripcion"), "texto"),
                    valor_unitario=_campo(
                        "valor_unitario", item_raw.get("valor_unitario"), "monto"
                    ),
                    importe=_campo("importe", item_raw.get("importe"), "monto"),
                )
            )

        # Grupo F — Totales
        gf = data.get("grupo_f_totales", {}) or {}
        grupo_f = TotalesTributos(
            subtotal=_campo("subtotal", gf.get("subtotal"), "monto"),
            igv_tasa=_campo("igv_tasa", gf.get("igv_tasa"), "tasa"),
            igv_monto=_campo("igv_monto", gf.get("igv_monto"), "monto"),
            total_gravado=_campo("total_gravado", gf.get("total_gravado"), "monto"),
            total_exonerado=_campo("total_exonerado", gf.get("total_exonerado"), "monto"),
            total_inafecto=_campo("total_inafecto", gf.get("total_inafecto"), "monto"),
            total_gratuito=_campo("total_gratuito", gf.get("total_gratuito"), "monto"),
            otros_cargos=_campo("otros_cargos", gf.get("otros_cargos"), "monto"),
            descuentos=_campo("descuentos", gf.get("descuentos"), "monto"),
            importe_total=_campo("importe_total", gf.get("importe_total"), "monto"),
            monto_letras=_campo("monto_letras", gf.get("monto_letras"), "texto"),
        )

        # Grupo G — Clasificación
        gg = data.get("grupo_g_clasificacion", {}) or {}
        grupo_g = ClasificacionGasto(
            categoria_gasto=_campo("categoria_gasto", gg.get("categoria_gasto"), "tipo"),
            subcategoria=_campo("subcategoria", gg.get("subcategoria"), "texto"),
        )

        # Grupo H — Hospedaje (opcional)
        gh = data.get("grupo_h_hospedaje", {}) or {}
        grupo_h = None
        if any(v is not None for v in gh.values()):
            grupo_h = DatosHospedaje(
                fecha_checkin=_campo("fecha_checkin", gh.get("fecha_checkin"), "fecha"),
                fecha_checkout=_campo("fecha_checkout", gh.get("fecha_checkout"), "fecha"),
                numero_noches=_campo("numero_noches", gh.get("numero_noches"), "numero"),
                numero_habitacion=_campo("numero_habitacion", gh.get("numero_habitacion"), "texto"),
                nombre_huesped=_campo("nombre_huesped", gh.get("nombre_huesped"), "texto"),
                numero_reserva=_campo("numero_reserva", gh.get("numero_reserva"), "texto"),
            )

        # Grupo I — Movilidad (opcional)
        gi = data.get("grupo_i_movilidad", {}) or {}
        grupo_i = None
        if any(v is not None for v in gi.values()):
            grupo_i = DatosMovilidad(
                origen=_campo("origen", gi.get("origen"), "texto"),
                destino=_campo("destino", gi.get("destino"), "texto"),
                fecha_servicio=_campo("fecha_servicio", gi.get("fecha_servicio"), "fecha"),
                placa_vehiculo=_campo("placa_vehiculo", gi.get("placa_vehiculo"), "texto"),
                nombre_pasajero=_campo("nombre_pasajero", gi.get("nombre_pasajero"), "texto"),
            )

        # Grupo K — Metadatos
        grupo_k = MetadatosExtraccion(
            pagina_origen=pagina,
            metodo_extraccion="qwen_vl",
            confianza_global=confianza_global,
            campos_no_encontrados=data.get("campos_no_encontrados", []) or [],
            timestamp_extraccion=datetime.now().isoformat(),
        )

        return ComprobanteExtraido(
            grupo_a=grupo_a,
            grupo_b=grupo_b,
            grupo_c=grupo_c,
            grupo_d=grupo_d,
            grupo_e=grupo_e,
            grupo_f=grupo_f,
            grupo_g=grupo_g,
            grupo_h=grupo_h,
            grupo_i=grupo_i,
            grupo_j=ValidacionesAritmeticas(),  # Se llena después
            grupo_k=grupo_k,
        )

    # ------------------------------------------------------------------
    # Validaciones aritméticas (Grupo J) — Python, NUNCA la IA
    # ------------------------------------------------------------------

    def _validar_aritmetica(self, comp: ComprobanteExtraido) -> ValidacionesAritmeticas:
        """
        Ejecuta validaciones aritméticas del Grupo J con Python.
        La IA NUNCA calcula. Python valida.
        """
        resultado = ValidacionesAritmeticas()

        # Helpers para extraer valor numérico de CampoExtraido
        def _num(campo: Optional[CampoExtraido]) -> Optional[float]:
            if campo is None or campo.valor is None:
                return None
            try:
                return float(campo.valor)
            except (ValueError, TypeError):
                return None

        # J1: Suma de ítems = subtotal
        subtotal = _num(comp.grupo_f.subtotal)
        if comp.grupo_e and subtotal is not None:
            importes = [_num(item.importe) for item in comp.grupo_e]
            importes_valid = [i for i in importes if i is not None]
            if importes_valid:
                suma = sum(importes_valid)
                diff = abs(suma - subtotal)
                resultado.suma_items_ok = diff <= TOLERANCIA_ARITMETICA
                if not resultado.suma_items_ok:
                    resultado.errores_detalle.append(
                        f"J1: Σ items={suma:.2f} vs subtotal={subtotal:.2f} (diff={diff:.2f})"
                    )

        # J2: IGV = subtotal × tasa
        igv_monto = _num(comp.grupo_f.igv_monto)
        igv_tasa = _num(comp.grupo_f.igv_tasa)
        if subtotal is not None and igv_monto is not None:
            tasa = igv_tasa if igv_tasa is not None else 18.0
            igv_esperado = subtotal * (tasa / 100.0)
            diff = abs(igv_esperado - igv_monto)
            resultado.igv_ok = diff <= TOLERANCIA_ARITMETICA
            if not resultado.igv_ok:
                resultado.errores_detalle.append(
                    f"J2: {subtotal:.2f}×{tasa}%={igv_esperado:.2f} vs IGV={igv_monto:.2f}"
                )

        # J3: Total = subtotal + IGV + otros - descuentos
        total = _num(comp.grupo_f.importe_total)
        if subtotal is not None and total is not None:
            igv = igv_monto if igv_monto is not None else 0.0
            otros = _num(comp.grupo_f.otros_cargos) or 0.0
            desc = _num(comp.grupo_f.descuentos) or 0.0
            exonerado = _num(comp.grupo_f.total_exonerado) or 0.0
            inafecto = _num(comp.grupo_f.total_inafecto) or 0.0
            calculado = subtotal + igv + otros - desc + exonerado + inafecto
            diff = abs(calculado - total)
            resultado.total_ok = diff <= TOLERANCIA_ARITMETICA
            if not resultado.total_ok:
                resultado.errores_detalle.append(
                    f"J3: calculado={calculado:.2f} vs total={total:.2f} (diff={diff:.2f})"
                )

        # J4: Noches de hospedaje
        if comp.grupo_h:
            checkin_str = comp.grupo_h.fecha_checkin.valor if comp.grupo_h.fecha_checkin else None
            checkout_str = (
                comp.grupo_h.fecha_checkout.valor if comp.grupo_h.fecha_checkout else None
            )
            noches_decl = _num(comp.grupo_h.numero_noches)
            if checkin_str and checkout_str and noches_decl is not None:
                try:
                    checkin = datetime.strptime(checkin_str, "%d/%m/%Y")
                    checkout = datetime.strptime(checkout_str, "%d/%m/%Y")
                    noches_calc = (checkout - checkin).days
                    resultado.noches_ok = noches_calc == int(noches_decl)
                    if not resultado.noches_ok:
                        resultado.errores_detalle.append(
                            f"J4: calc={noches_calc} vs decl={int(noches_decl)}"
                        )
                except (ValueError, TypeError):
                    pass  # Formato no parseable, skip

        return resultado

    # ------------------------------------------------------------------
    # Deduplicación por serie_numero
    # ------------------------------------------------------------------

    def _deduplicar(self, comprobantes: List[ComprobanteExtraido]) -> List[ComprobanteExtraido]:
        """
        Deduplica comprobantes por serie-número.
        En caso de duplicado, conserva el de mayor confianza.
        """
        vistos: Dict[str, ComprobanteExtraido] = {}

        for comp in comprobantes:
            key = comp.get_serie_numero()
            if key == "SIN_IDENTIFICAR":
                # No se puede deduplicar sin serie_numero
                vistos[f"_sin_id_{id(comp)}"] = comp
                continue

            if key not in vistos:
                vistos[key] = comp
            else:
                # Conservar el de mayor confianza
                existente = vistos[key]
                conf_existente = {"alta": 3, "media": 2, "baja": 1}.get(
                    existente.grupo_k.confianza_global, 0
                )
                conf_nuevo = {"alta": 3, "media": 2, "baja": 1}.get(
                    comp.grupo_k.confianza_global, 0
                )
                if conf_nuevo > conf_existente:
                    vistos[key] = comp

        return list(vistos.values())

    # ------------------------------------------------------------------
    # Logging con TraceLogger (duck typing)
    # ------------------------------------------------------------------

    def _log_info(self, msg: str) -> None:
        logger.info(msg)
        if self.trace_logger:
            try:
                self.trace_logger.info(msg, agent_id="QWEN_FALLBACK", operation="extraccion")
            except Exception:
                pass

    def _log_warning(self, msg: str) -> None:
        logger.warning(msg)
        if self.trace_logger:
            try:
                self.trace_logger.warning(msg, agent_id="QWEN_FALLBACK", operation="extraccion")
            except Exception:
                pass


# ==============================================================================
# FUNCIÓN DE CONVENIENCIA
# ==============================================================================


def extraer_comprobantes_vlm(
    imagenes_b64: List[str],
    archivo: str = "",
    paginas: Optional[List[int]] = None,
    config: Optional[Dict[str, Any]] = None,
    trace_logger: Any = None,
) -> ResultadoExtraccion:
    """
    Función de conveniencia para extraer comprobantes con el VLM.

    Args:
        imagenes_b64: Lista de imágenes de páginas en base64.
        archivo: Nombre del archivo fuente.
        paginas: Números de página (1-indexed).
        config: Override de VLM_CONFIG.
        trace_logger: TraceLogger para auditoría.

    Returns:
        ResultadoExtraccion con comprobantes deduplicados.
    """
    client = QwenFallbackClient(config=config, trace_logger=trace_logger)
    return client.extraer_comprobantes(
        imagenes_b64=imagenes_b64,
        archivo=archivo,
        paginas=paginas,
    )
