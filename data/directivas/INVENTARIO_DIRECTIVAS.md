# Inventario de Directivas — AG-EVIDENCE

> Los PDFs de directivas NO se versionan en GitHub (son documentos oficiales pesados).
> Este inventario documenta que archivos deben existir localmente para que el sistema funcione.
> Usar `scripts/backup_local.py` para respaldar todo incluyendo PDFs.

---

## Fuente Principal de Validacion (vigente 2026)

| Archivo | Carpeta | Tamano | Uso |
|---------|---------|--------|-----|
| **NUEVA DIRECTIVA DE VIATICOS_{Res_de_Secretaria_General Nro. 023-2026-MINEDU.pdf** | VIATICO/ | 1.9 MB | **FUENTE PRINCIPAL** para validacion de viaticos |
| RESOLUCION_DE_SECRETARIA_GENERAL-00023-2026-MINEDU.pdf | VIATICO/ | 1.0 MB | Resolucion que aprueba la nueva directiva |

---

## Directivas de Contexto (referencia, no validacion principal)

### Viaticos
| Archivo | Tamano | Nota |
|---------|--------|------|
| Directiva de Viaticos 011-2020.pdf | 16.7 MB | Directiva anterior (derogada por RGS 023-2026) |
| AUSTERIDAD -MEMORANDUM_MULTIPLE-00080-2023-MINEDU-SG (1).pdf | 0.5 MB | Medidas de austeridad (complementaria) |

### Caja Chica
| Archivo | Tamano | Nota |
|---------|--------|------|
| VIGENTE AL 16.10.2025_RJ_0023-2025_Directiva Caja Chica 2025.pdf | 11.6 MB | Directiva vigente |
| Nuevas Disposiciones OFICIO_MULTIPLE-00064-2025-MINEDU-SG-OGA.pdf | 0.8 MB | Disposiciones adicionales Nov 2025 |
| Distribucion Cajas Chicas 2025.jpeg | 0.06 MB | Imagen informativa |

### Encargo
| Archivo | Tamano | Nota |
|---------|--------|------|
| Directiva de Encargos 261-2018.pdf | 11.8 MB | Directiva vigente |

### Pautas de Control Previo
| Archivo | Tamano | Nota |
|---------|--------|------|
| PAUTAS PARA LA REMISION DE EXPEDIENTES DE PAGO.pdf | ~2 MB | Guia para revision |

### IGV MYPES (normativa tributaria)
| Archivo | Tamano | Nota |
|---------|--------|------|
| Ley nro 31556.pdf | ~0.5 MB | Ley original MYPES |
| LEY N 32219_modifica Ley 31556.PDF | ~0.3 MB | Modificatoria |
| DS237_2022_EF.pdf.pdf | ~0.8 MB | Reglamento |
| **RESUMEN_TASAS_IGV_MYPES.md** | 5 KB | Resumen (SI versionado en git) |

---

## Como obtener los PDFs

1. **Directivas MINEDU:** Portal institucional o copia interna del area
2. **Normativa tributaria:** Portal SUNAT / El Peruano
3. **Backup completo:** Ejecutar `python scripts/backup_local.py`

---

## Tamano total estimado de directivas: ~46 MB

---

*Creado: 2026-02-13 por Claude Code*
