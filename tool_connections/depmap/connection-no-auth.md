---
name: depmap
auth: no-auth
description: DepMap Cancer Dependency Map portal (Broad Institute) — public API for querying gene dependencies, expression, drug sensitivity, mutations, copy number across 2000+ cancer cell lines. No auth required. Use when looking up CRISPR gene effect scores, drug sensitivity AUC, expression, or mutations for specific genes or cell lines.
env_vars: []
---

# DepMap Portal — no auth

The Cancer Dependency Map (DepMap) portal at the Broad Institute. Public API for querying cancer cell line dependencies, gene expression, drug sensitivity, mutations, and more across 2000+ cancer models. No API key or login required.

API docs: https://depmap.org/portal/api/ | Swagger: https://depmap.org/portal/api/swagger.json
Source: https://github.com/broadinstitute/depmap-portal | Data pipeline: https://github.com/broadinstitute/depmap_omics | Python API wrapper: https://github.com/broadinstitute/depmap-api

**Verified:** Production (https://depmap.org/portal/api) — health_check, download/datasets, download/custom, context_explorer/context_search_options, download/gene_dep_summary — 2026-04. No VPN required.

---

## Auth

No authentication required. All endpoints are publicly accessible.

---

## Verified snippets

### Health check

```bash
curl -s "https://depmap.org/portal/api/health_check/celery_redis_check"
# → {"state": "SUCCESS", "id": "ee5eec86-3a7a-458e-ba97-d8280b25e033", "nextPollDelay": 1000, "message": null, "result": "SUCCESS", "percentComplete": null}
```

### List available datasets

```bash
curl -s "https://depmap.org/portal/api/download/datasets" | python3 -c "
import sys, json
for d in json.load(sys.stdin):
    print(d['id'], '|', d['display_name'], '|', d['data_type'])
"
# → breadbox/a2a0a725-b585-40c8-8c45-a924f8178656 | CRISPR (DepMap Public 26Q1+Score, Chronos) | CRISPR
# → breadbox/20528fee-bd1d-4f3f-b7a2-f991fc875858 | Expression (Short-read) Public 26Q1 | Expression
# → breadbox/33012dd6-9fec-4cb9-95e0-cd7ad27e4c60 | Damaging Mutations (Public 26Q1) | Mutations
# → GDSC1_AUC | Drug sensitivity AUC (Sanger GDSC1) | Drug screen
# → [60+ more datasets — full list at /download/datasets]
```

### Custom download — subset by genes and/or cell lines

```bash
# ⚠ Must send as JSON body — query params return 500 despite Swagger showing them as query params
TASK=$(curl -s -X POST "https://depmap.org/portal/api/download/custom" \
  -H "Content-Type: application/json" \
  -d '{
    "datasetId": "breadbox/a2a0a725-b585-40c8-8c45-a924f8178656",
    "featureLabels": ["EGFR", "KRAS"],
    "cellLineIds": ["ACH-000029", "ACH-000030", "ACH-000074"],
    "dropEmpty": true,
    "addCellLineMetadata": true
  }')
TASK_ID=$(echo "$TASK" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Poll until SUCCESS
sleep 3
RESULT=$(curl -s "https://depmap.org/portal/api/task/$TASK_ID")
DOWNLOAD_URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['downloadUrl'])")

curl -s "$DOWNLOAD_URL"
# → depmap_id,cell_line_display_name,lineage_1,lineage_2,lineage_3,lineage_6,lineage_4,EGFR,KRAS
# → ACH-000029,HCC827GR5,Lung,Non-Small Cell Lung Cancer,Lung Adenocarcinoma,,,-0.3109611752,-0.3082617488
# → ACH-000030,PC14,Lung,Non-Small Cell Lung Cancer,Lung Adenocarcinoma,,,-1.6675284774,-0.2064547584
# → ACH-000074,KU812,Myeloid,Myeloproliferative Neoplasms,"Chronic Myeloid Leukemia, BCR-ABL1+",BCR::ABL1,,0.0221426493,-0.5725459817
```

### Gene dependency summary (all genes, CSV)

```bash
curl -s "https://depmap.org/portal/api/download/gene_dep_summary" | head -3
# → Entrez Id,Gene,Dataset,Dependent Cell Lines,Cell Lines with Data,Strongly Selective,Common Essential
# → 1,A1BG,DependencyEnum.RNAi_merged,2.0,547.0,False,False
# → 29974,A1CF,DependencyEnum.RNAi_merged,11.0,710.0,True,False
```

### Context search options (lineages and subtypes)

```bash
curl -s "https://depmap.org/portal/api/context_explorer/context_search_options" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data['lineage'][:5]:
    print(item['name'], '|', item['subtype_code'], '| n =', item['numModels'])
"
# → Adrenal Gland | ADRENAL_GLAND | n = 2
# → Ampulla of Vater | AMPULLA_OF_VATER | n = 5
# → Biliary Tract | BILIARY_TRACT | n = 45
# → Bladder/Urinary Tract | BLADDER | n = 39
# → Bone | BONE | n = 101
```

---

## Parameters for /download/custom

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `datasetId` | string | required | Dataset ID from `/download/datasets` |
| `featureLabels` | list | null (all) | Gene or compound names, e.g. `["EGFR", "KRAS"]` |
| `cellLineIds` | list | null (all) | DepMap cell line IDs, e.g. `["ACH-000029"]` |
| `dropEmpty` | bool | false | Drop rows/cols that are entirely NAs |
| `addCellLineMetadata` | bool | false | Prepend: `depmap_id`, `cell_line_display_name`, `lineage_1`…`lineage_6` |

---

## Key dataset IDs (26Q1 release)

| data_type | display_name | id |
|-----------|-------------|-----|
| CRISPR | CRISPR (DepMap Public 26Q1+Score, Chronos) | `breadbox/a2a0a725-b585-40c8-8c45-a924f8178656` |
| CRISPR | CRISPR Gene Dependency | `breadbox/56a60301-65c6-48b3-bcab-2c98037b79ef` |
| Expression | Expression (Short-read) Public 26Q1 | `breadbox/20528fee-bd1d-4f3f-b7a2-f991fc875858` |
| Mutations | Damaging Mutations (Public 26Q1) | `breadbox/33012dd6-9fec-4cb9-95e0-cd7ad27e4c60` |
| Mutations | Hotspot Mutations (Public 26Q1) | `breadbox/a952ab7b-56c8-4aeb-872e-8ee02eeae042` |
| Drug screen | Drug sensitivity AUC (PRISM Repurposing Secondary Screen) | `Repurposing_secondary_AUC` |
| Drug screen | Drug sensitivity AUC (Sanger GDSC1) | `GDSC1_AUC` |
| Drug screen | Drug sensitivity AUC (Sanger GDSC2) | `GDSC2_AUC` |
| Drug screen | Drug sensitivity AUC (CTD^2) | `CTRP_AUC` |
| CN | Copy Number WGS Public 26Q1 | `breadbox/170f1297-8f63-412c-b468-39ce7d7a18f7` |
| Protein Expression | Harmonized MS CCLE Gygi | `breadbox/0da38e94-2ba1-4710-85de-cdf766321b1b` |
| RNAi | RNAi (Achilles+DRIVE+Marcotte, DEMETER2) | `breadbox/d3fc7be1-fa6c-40da-9103-7537efd53da6` |
| Structural variants | Fusions Public 26Q1 | `fusions` |
| MetMap | MetMap 500: Metastatic Potential | `metmap-data-f459.3/metmap500_metastatic_potential` |

Full list: `curl -s "https://depmap.org/portal/api/download/datasets"`

---

## Notes

- No search API — subset by known gene names (`featureLabels`) or DepMap IDs (`cellLineIds`)
- No AI/chat API — 404 on `/api/ai` and `/api/chat`
- Dataset IDs change between releases — use `/download/datasets` to resolve current IDs if a query fails
- `/download/custom` is async: POST → get task id → poll `/task/{id}` → download from `result.downloadUrl`
- `breadbox/` prefix IDs are the current canonical IDs; legacy short IDs (e.g. `GDSC1_AUC`) still work for older datasets
