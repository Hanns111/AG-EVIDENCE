#!/usr/bin/env python3
"""
Fase A — Extracción de comprobantes con Qwen2.5-VL-7B via Ollama
Basado en PARSING_COMPROBANTES_SPEC.md (11 grupos A-K)

Regla de Oro: La IA extrae LITERALMENTE lo que ve. Python valida aritméticamente.
"""

import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# === CONFIGURACIÓN ===
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5vl:7b"
TIMEOUT = 120  # seconds per image

# === PROMPT DE EXTRACCIÓN ===
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


def encode_image(image_path: str) -> str:
    """Encode image to base64 for Ollama API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_invoice(image_path: str) -> dict:
    """Send image to Qwen2.5-VL via Ollama and extract invoice data."""
    print(f"\n{'=' * 60}")
    print(f"Procesando: {os.path.basename(image_path)}")
    print(f"{'=' * 60}")

    img_b64 = encode_image(image_path)

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": EXTRACTION_PROMPT, "images": [img_b64]}],
        "stream": False,
        "options": {
            "temperature": 0.0,  # Deterministic
            "num_predict": 4096,
            "num_ctx": 8192,
        },
    }

    start = time.time()
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start

        if resp.status_code != 200:
            print(f"ERROR HTTP {resp.status_code}: {resp.text[:200]}")
            return {"error": f"HTTP {resp.status_code}", "elapsed_s": elapsed}

        data = resp.json()
        content = data.get("message", {}).get("content", "")

        print(f"Tiempo de inferencia: {elapsed:.1f}s")
        print(f"Tokens eval: {data.get('eval_count', '?')}")

        # Parse JSON from response - handle markdown code blocks
        json_str = content.strip()
        if json_str.startswith("```"):
            # Remove markdown code block
            lines = json_str.split("\n")
            json_str = (
                "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            )
            json_str = json_str.strip()

        try:
            result = json.loads(json_str)
            result["_meta"] = {
                "tiempo_inferencia_s": round(elapsed, 2),
                "tokens_evaluados": data.get("eval_count"),
                "modelo": MODEL,
                "imagen": os.path.basename(image_path),
            }
            return result
        except json.JSONDecodeError as e:
            print(f"ERROR parsing JSON: {e}")
            print(f"Raw response (first 500 chars):\n{content[:500]}")
            return {
                "error": "JSON parse failed",
                "raw_response": content[:2000],
                "elapsed_s": elapsed,
            }

    except requests.exceptions.Timeout:
        print(f"TIMEOUT después de {TIMEOUT}s")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError:
        print("ERROR: No se puede conectar a Ollama. ¿Está corriendo?")
        print("Ejecuta: ollama serve &")
        return {"error": "connection_refused"}


def validate_arithmetic(result: dict) -> dict:
    """
    Grupo J — Validaciones aritméticas ejecutadas por Python.
    La IA NO calcula. Python valida.
    """
    validaciones = []
    totales = result.get("grupo_f_totales", {})
    items = result.get("grupo_e_items", [])
    hospedaje = result.get("grupo_h_hospedaje", {})

    TOLERANCIA = 0.02

    # J1: Suma de ítems = subtotal
    if items and totales.get("subtotal") is not None:
        suma_items = sum(
            (it.get("importe") or 0) for it in items if isinstance(it.get("importe"), (int, float))
        )
        subtotal = totales["subtotal"]
        diff = abs(suma_items - subtotal)
        validaciones.append(
            {
                "validacion": "J1_suma_items",
                "formula": f"Σ(items.importe) = {suma_items:.2f} vs subtotal = {subtotal:.2f}",
                "diferencia": round(diff, 2),
                "resultado": "OK" if diff <= TOLERANCIA else "ERROR",
                "tolerancia": TOLERANCIA,
            }
        )

    # J2: IGV = subtotal × tasa
    if totales.get("subtotal") is not None and totales.get("igv_monto") is not None:
        subtotal = totales["subtotal"]
        igv_tasa = totales.get("igv_tasa", 18)
        igv_esperado = subtotal * (igv_tasa / 100)
        igv_real = totales["igv_monto"]
        diff = abs(igv_esperado - igv_real)
        validaciones.append(
            {
                "validacion": "J2_igv",
                "formula": f"{subtotal:.2f} × {igv_tasa}% = {igv_esperado:.2f} vs IGV = {igv_real:.2f}",
                "diferencia": round(diff, 2),
                "resultado": "OK" if diff <= TOLERANCIA else "ERROR",
                "tolerancia": TOLERANCIA,
            }
        )

    # J3: Total = subtotal + IGV + otros - descuentos
    if totales.get("subtotal") is not None and totales.get("importe_total") is not None:
        subtotal = totales["subtotal"]
        igv = totales.get("igv_monto", 0) or 0
        otros = totales.get("otros_cargos", 0) or 0
        desc = totales.get("descuentos", 0) or 0
        exonerado = totales.get("total_exonerado", 0) or 0
        inafecto = totales.get("total_inafecto", 0) or 0
        total_calculado = subtotal + igv + otros - desc + exonerado + inafecto
        total_real = totales["importe_total"]
        diff = abs(total_calculado - total_real)
        validaciones.append(
            {
                "validacion": "J3_total",
                "formula": f"{subtotal:.2f} + {igv:.2f} + {otros:.2f} - {desc:.2f} + exon({exonerado:.2f}) + inaf({inafecto:.2f}) = {total_calculado:.2f} vs total = {total_real:.2f}",
                "diferencia": round(diff, 2),
                "resultado": "OK" if diff <= TOLERANCIA else "ERROR",
                "tolerancia": TOLERANCIA,
            }
        )

    # J4: Noches de hospedaje
    if (
        hospedaje.get("fecha_checkin")
        and hospedaje.get("fecha_checkout")
        and hospedaje.get("numero_noches")
    ):
        try:
            from datetime import datetime as dt

            checkin = dt.strptime(hospedaje["fecha_checkin"], "%d/%m/%Y")
            checkout = dt.strptime(hospedaje["fecha_checkout"], "%d/%m/%Y")
            noches_calc = (checkout - checkin).days
            noches_decl = hospedaje["numero_noches"]
            validaciones.append(
                {
                    "validacion": "J4_noches",
                    "formula": f"({hospedaje['fecha_checkout']} - {hospedaje['fecha_checkin']}).days = {noches_calc} vs declarado = {noches_decl}",
                    "diferencia": abs(noches_calc - noches_decl),
                    "resultado": "OK" if noches_calc == noches_decl else "ERROR",
                }
            )
        except (ValueError, TypeError):
            validaciones.append(
                {
                    "validacion": "J4_noches",
                    "resultado": "SKIP",
                    "motivo": "Formato de fecha no parseable",
                }
            )

    return {
        "grupo_j_validaciones": validaciones,
        "resumen": {
            "total_validaciones": len(validaciones),
            "ok": sum(1 for v in validaciones if v["resultado"] == "OK"),
            "errores": sum(1 for v in validaciones if v["resultado"] == "ERROR"),
            "skipped": sum(1 for v in validaciones if v["resultado"] == "SKIP"),
        },
    }


def main():
    """Process reference invoices."""
    base_dir = Path(
        "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0068815/extraccion/facturas_ref"
    )
    output_dir = Path(
        "data/expedientes/pruebas/viaticos_2026/DIRI2026-INT-0068815/extraccion/json_extraido"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3 reference invoices as specified by the user
    facturas = [
        ("pag20_el_chalan_F011-0008846.png", "El Chalán - F011-0008846"),
        ("pag22_win_win_F700-141.png", "Win & Win Hotel - F700-141"),
        ("pag42_virgen_carmen_E001-1771.png", "Virgen del Carmen - E001-1771"),
    ]

    # Verify Ollama is running
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"Ollama OK. Modelos disponibles: {models}")
            if not any(MODEL.split(":")[0] in m for m in models):
                print(f"\n⚠ Modelo {MODEL} no encontrado. Descargando...")
                os.system(f"ollama pull {MODEL}")
        else:
            print(f"Ollama respondió con status {resp.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("ERROR: Ollama no está corriendo. Ejecuta: ollama serve &")
        sys.exit(1)

    results = {}

    for filename, label in facturas:
        img_path = base_dir / filename
        if not img_path.exists():
            print(f"SKIP: {filename} no encontrado")
            continue

        print(f"\n{'#' * 60}")
        print(f"# {label}")
        print(f"{'#' * 60}")

        # Extract with Qwen-VL
        extraction = extract_invoice(str(img_path))

        if "error" not in extraction:
            # Validate arithmetic (Grupo J)
            validation = validate_arithmetic(extraction)
            extraction["grupo_j_validaciones"] = validation["grupo_j_validaciones"]
            extraction["grupo_j_resumen"] = validation["resumen"]

            # Add metadata (Grupo K)
            if "_meta" not in extraction:
                extraction["_meta"] = {}
            extraction["_meta"]["timestamp_extraccion"] = datetime.now().isoformat()
            extraction["_meta"]["pagina_origen"] = int(filename.split("_")[0].replace("pag", ""))
            extraction["_meta"]["metodo_extraccion"] = "qwen_vl"

        results[label] = extraction

        # Save individual JSON
        safe_name = filename.replace(".png", ".json")
        out_path = output_dir / safe_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(extraction, f, indent=2, ensure_ascii=False)
        print(f"Guardado: {out_path}")

    # Save combined results
    combined_path = output_dir / "resultados_fase_a.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n{'=' * 60}")
    print(f"Resultados combinados: {combined_path}")

    # Print summary
    print(f"\n{'=' * 60}")
    print("RESUMEN FASE A")
    print(f"{'=' * 60}")
    for label, res in results.items():
        if "error" in res:
            print(f"  ❌ {label}: {res['error']}")
        else:
            j = res.get("grupo_j_resumen", {})
            conf = res.get("confianza_global", "?")
            emisor = res.get("grupo_a_emisor", {}).get("ruc_emisor", "?")
            total = res.get("grupo_f_totales", {}).get("importe_total", "?")
            print(f"  ✓ {label}")
            print(f"    RUC: {emisor} | Total: S/{total} | Confianza: {conf}")
            print(
                f"    Validaciones: {j.get('ok', 0)} OK, {j.get('errores', 0)} ERR, {j.get('skipped', 0)} SKIP"
            )

    return results


if __name__ == "__main__":
    results = main()
