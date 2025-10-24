# Ontology ETL + Visualization (Quick-Start)

This drop-in set of scripts lets you **ingest the Excel workbook** into your ontology (as TTL) and **generate three interactive HTML visualizations**.

## 0) Install dependencies

```bash
pip install pandas rdflib openpyxl networkx pyvis
```

## 1) Update ontology from Excel

```bash
python update_ontology_from_excel.py \
  --excel /mnt/data/ontology_coding_template_10-19-2025.xlsx \
  --sheet measures \
  --team-ttl /mnt/data/teamMeasurement.ttl \
  --evidence-ttl /mnt/data/evidence.ttl \
  --old-instances /mnt/data/instances_from_excel.ttl \
  --out-ttl /mnt/data/merged_instances.ttl
```

What it does:
- Loads base TTLs and optional prior instances
- Normalizes labels
- Creates **Named Individuals** for every **Modality** and **Analytic Technique** in the workbook
- Links each `Measure` to `Construct`, `Modality`, `Analytic Technique`, and (optionally) Level of Analysis

> Namespaces default to `http://example.org/ontology/teamMeasurement#` and `http://example.org/ontology/instances#`. Override with `--meas-ns` and `--inst-ns` if different in your files.

## 2) (Optional) Validate with SHACL

Use your preferred SHACL runner against `shapes_measure_required.ttl` to ensure each Measure has the three key links.

## 3) Visualizations

### 3.1 Global overview
```bash
python viz.py global --ttl /mnt/data/merged_instances.ttl --out /mnt/data/viz_global.html
```

### 3.2 User text → constructs → measures
```bash
python viz.py query --ttl /mnt/data/merged_instances.ttl \
  --text "team communication under time pressure" \
  --k 5 \
  --out /mnt/data/viz_query_example.html
```

### 3.3 Measure-set coverage
Create a simple text file with one measure id per line (either full IRI, or local id like `meas_001` or `measure_meas_001`).

```bash
echo "meas_001" > /mnt/data/measure_list.txt
echo "meas_003" >> /mnt/data/measure_list.txt

python viz.py set --ttl /mnt/data/merged_instances.ttl \
  --measures /mnt/data/measure_list.txt \
  --out /mnt/data/viz_measure_set.html
```

## 4) SPARQL helpers

- `queries/coverage_by_construct.rq` → Construct coverage counts
- `queries/measure_triplets_for_set.rq` → Modality/Technique/Construct triplets for a chosen set of Measures

## Notes

- The ETL treats Modality and Analytic Technique as **instances** (individuals) to keep linkage simple and compatible with existing object properties. You can enrich hierarchies later via `skos:broader` and friends.
- Label normalization (DSA casing, hyphens, whitespace) is handled in one place; extend as needed for new patterns.
- If you change sheet or column names, adjust `--sheet` or the column detection logic in the script.
