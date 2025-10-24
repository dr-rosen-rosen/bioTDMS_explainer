#!/usr/bin/env python3
"""
update_ontology_from_excel.py

One-pass ETL that:
- Reads an Excel workbook (default sheet 'measures') with columns including:
    measureID, measureLabel, NewConstruct (or construct), includesModality, usesAnalyticTechnique, description, source, levelOfAnalysis
- Loads base TTLs (teamMeasurement.ttl, evidence.ttl) and optional prior instances
- Normalizes labels, creates/links instances for Modality, Analytic Technique, Construct
- Writes a merged TTL

Design choices:
- Treat Modality and Analytic Technique values from Excel as *Named Individuals* of classes MEAS:Modality and MEAS:analyticTechnique.
- Assign optional skos:broader to coarse buckets inferred from text (communication, behavior, physiology, survey, observation, taskOutcome).
- Use consistent, URL-safe local fragments under the INST namespace.

USAGE:
python update_ontology_from_excel.py \
  --excel /path/ontology_coding_template_10-19-2025.xlsx \
  --sheet measures \
  --team-ttl /path/teamMeasurement.ttl \
  --evidence-ttl /path/evidence.ttl \
  --old-instances /path/instances_from_excel.ttl \
  --out-ttl /path/merged_instances.ttl

DEPENDENCIES: pandas, rdflib, openpyxl (for xlsx)
pip install pandas rdflib openpyxl
"""

import argparse
import re
from urllib.parse import quote
from pathlib import Path

import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, SKOS, XSD

DEFAULT_MEAS_NS = "http://example.org/ontology/teamMeasurement#"
DEFAULT_INST_NS = "http://example.org/ontology/instances#"

def norm_label(label: str) -> str:
    s = re.sub(r'\s+', ' ', str(label).strip())
    s = s.replace('—', '-').replace('–', '-').replace('‐', '-')
    # fix common typos
    s = s.replace('anlaysis', 'analysis')
    # unify DSA capitalization
    s = re.sub(r'^(dsa)\s*-\s*', 'DSA - ', s, flags=re.I)
    s = re.sub(r'^DSA\s*-\s*', 'DSA - ', s)
    return s

def slugify(label: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9]+', '_', label).strip('_')
    return s.lower()

def split_multi(val):
    if val is None:
        return []
    if isinstance(val, float) and pd.isna(val):
        return []
    return [v.strip() for v in str(val).split(',') if v.strip()]

def infer_coarse_modality(label_lower: str) -> str | None:
    ll = label_lower
    if 'physiol' in ll or 'ibi' in ll or 'cardiac' in ll or 'eda' in ll or 'eeg' in ll:
        return 'physiology'
    if 'survey' in ll or 'interview' in ll or 'questionnaire' in ll:
        return 'survey'
    if 'observ' in ll or 'ethnograph' in ll:
        return 'observation'
    if 'communicat' in ll or 'language' in ll or 'speech' in ll or 'text' in ll:
        return 'communication'
    if 'behavior' in ll or 'movement' in ll or 'system' in ll or 'log' in ll or 'task outcome' in ll:
        return 'behavior'
    if 'task outcome' in ll or 'accuracy' in ll or 'time on task' in ll:
        return 'taskOutcome'
    return None

class OntologyUpdater:
    def __init__(self, meas_ns: str, inst_ns: str):
        self.graph = Graph()
        self.MEAS = Namespace(meas_ns)
        self.INST = Namespace(inst_ns)
        self.graph.bind("meas", self.MEAS)
        self.graph.bind("inst", self.INST)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("owl", OWL)
        self.graph.bind("skos", SKOS)
    
    def load_ttls(self, paths):
        """
        Load a list of RDF files with robust format guessing and clear error messages.
        Tries: guess_format(None), 'turtle', 'n3', 'xml', 'nt', 'trig', 'nquads'.
        """
        from rdflib.util import guess_format
        import traceback

        tried_formats = ['turtle', 'n3', 'xml', 'nt', 'trig', 'nquads']
        for p in paths:
            if not p:
                continue
            pth = Path(p)
            if not pth.exists():
                print(f"[WARN] Skipping missing RDF file: {p}")
                continue
            data = None
            try:
                # First try automatic guessing by file extension
                fmt = guess_format(str(pth))
                if fmt:
                    self.graph.parse(p, format=fmt)
                    print(f"[OK] Parsed {p} as {fmt}")
                    continue
            except Exception as e:
                print(f"[INFO] Auto-guess parse failed for {p}: {e}")

            # Try common formats explicitly
            success = False
            for fmt in tried_formats:
                try:
                    self.graph.parse(p, format=fmt)
                    print(f"[OK] Parsed {p} as {fmt}")
                    success = True
                    break
                except Exception as e:
                    last_err = e
                    continue
            if not success:
                # Surface a helpful error with file path
                print(f"[ERROR] Could not parse RDF file: {p}")
                print(f"Last error: {last_err}")
                # Re-raise with context
                raise RuntimeError(f"Failed to parse RDF file {p}. Try validating syntax or different format (TTL/RDF/XML).") from last_err

    
    def get_or_create_modality(self, label: str, coarse: str | None = None) -> URIRef:
        clabel = norm_label(label)
        uri = self.INST[f"modality_{slugify(clabel)}"]
        if (uri, None, None) not in self.graph:
            self.graph.add((uri, RDF.type, self.MEAS.Modality))
            self.graph.add((uri, RDFS.label, Literal(clabel)))
            if coarse:
                coarse_uri = self.MEAS[coarse]
                self.graph.add((uri, SKOS.broader, coarse_uri))
        return uri

    def get_or_create_technique(self, label: str) -> URIRef:
        clabel = norm_label(label)
        uri = self.INST[f"tech_{slugify(clabel)}"]
        if (uri, None, None) not in self.graph:
            self.graph.add((uri, RDF.type, self.MEAS.analyticTechnique))
            self.graph.add((uri, RDFS.label, Literal(clabel)))
        return uri

    def get_or_create_construct(self, label: str) -> URIRef:
        clabel = norm_label(label)
        uri = self.INST[f"construct_{slugify(clabel)}"]
        if (uri, None, None) not in self.graph:
            self.graph.add((uri, RDF.type, self.MEAS.Construct))
            self.graph.add((uri, RDFS.label, Literal(clabel)))
        return uri

    def get_or_create_measure(self, measure_id: str, label: str | None = None) -> URIRef:
        local = f"measure_{slugify(measure_id)}" if measure_id else f"measure_{slugify(label or 'unknown')}"
        uri = self.INST[local]
        if (uri, None, None) not in self.graph:
            self.graph.add((uri, RDF.type, self.MEAS.Measure))
            if label:
                self.graph.add((uri, RDFS.label, Literal(norm_label(label))))
        # attach data property for id if you have one; here we keep as label
        return uri

    def link(self, s: URIRef, p: URIRef, o: URIRef):
        self.graph.add((s, p, o))

    def update_from_excel(self, excel_path: str, sheet: str = "measures"):
        df = pd.read_excel(excel_path, sheet_name=sheet)

        # --- Column mapping with synonyms (case-insensitive) ---
        colmap = {
            'measureID': 'measureID',                  # synonyms: measure_id, id
            'measureLabel': 'measureLabel',            # synonyms: hasName, name, label
            'NewConstruct': 'NewConstruct',
            'construct': 'construct',
            'includesModality': 'includesModality',
            'usesAnalyticTechnique': 'usesAnalyticTechnique',
            'description': 'description',              # synonyms: hasDescription, Description
            'source': 'source',
            'levelOfAnalysis': 'levelOfAnalysis'       # synonyms: hasLevelOfAnalysis, LevelOfAnalysis
        }

        existing = {c.lower(): c for c in df.columns}

        def bind_syn(target_key, *synonyms):
            # Exact present?
            if colmap[target_key] in df.columns:
                return
            # Case-insensitive of default
            if colmap[target_key].lower() in existing:
                colmap[target_key] = existing[colmap[target_key].lower()]
                return
            # Synonyms (exact or case-insensitive)
            for syn in synonyms:
                if syn in df.columns:
                    colmap[target_key] = syn; return
                if syn.lower() in existing:
                    colmap[target_key] = existing[syn.lower()]; return

        bind_syn('measureID', 'measure_id', 'MeasureID', 'id')
        bind_syn('measureLabel', 'hasName', 'name', 'label', 'MeasureLabel')
        bind_syn('description', 'hasDescription', 'Description')
        bind_syn('levelOfAnalysis', 'hasLevelOfAnalysis', 'LevelOfAnalysis')
        bind_syn('includesModality', 'modality', 'Modality')
        bind_syn('usesAnalyticTechnique', 'analyticTechnique', 'technique', 'Technique')
        # Try a bunch of likely construct headers
        bind_syn('NewConstruct', 'new_construct', 'New_Construct')
        bind_syn('construct', 'Construct', 'originalConstruct', 'MeasuresConstruct', 'measuresConstruct',
                'targetConstruct', 'TargetConstruct', 'teamConstruct', 'TeamConstruct', 'Constructs')

        # Build a dynamic list of ANY construct-ish columns present
        construct_cols = []
        # Priority order first
        for key in ('NewConstruct', 'construct'):
            col = colmap.get(key)
            if col and col in df.columns:
                construct_cols.append(col)
        # Then add any other column that contains 'construct' in its name
        for c in df.columns:
            if c not in construct_cols and 'construct' in c.lower():
                construct_cols.append(c)

        if not construct_cols:
            print("[WARN] No construct-like columns detected (headers containing 'construct'). "
                "No measuresConstruct links will be created.")

        # Safe accessor that returns None if mapped column missing
        def cell(row, key):
            col = colmap.get(key)
            if not col or col not in df.columns:
                return None
            return row.get(col)

        made_measures = 0
        made_construct_links = 0

        # --- Iterate rows and build graph ---
        for idx, row in df.iterrows():
            meas_id_raw = cell(row, 'measureID')
            meas_label_raw = cell(row, 'measureLabel')

            meas_id = str(meas_id_raw).strip() if pd.notna(meas_id_raw) else None
            meas_label = str(meas_label_raw).strip() if pd.notna(meas_label_raw) else None

            # Require at least ID or label
            if not meas_id and not meas_label:
                print(f"[SKIP] Row {idx}: missing both measureID and measureLabel/hasName.")
                continue

            m_uri = self.get_or_create_measure(meas_id or meas_label, meas_label)
            made_measures += 1

            # description (optional)
            desc_val = cell(row, 'description')
            if pd.notna(desc_val) and str(desc_val).strip():
                self.graph.add((m_uri, self.MEAS.hasDescription, Literal(str(desc_val))))

            # levelOfAnalysis (optional)
            loa_val = cell(row, 'levelOfAnalysis')
            if pd.notna(loa_val) and str(loa_val).strip():
                loa_norm = norm_label(str(loa_val))
                loa_uri = self.INST[f"level_{slugify(loa_norm)}"]
                if (loa_uri, None, None) not in self.graph:
                    self.graph.add((loa_uri, RDF.type, self.MEAS.levelOfAnalysis))
                    self.graph.add((loa_uri, RDFS.label, Literal(loa_norm)))
                self.link(m_uri, self.MEAS.hasLevelOfAnalysis, loa_uri)

            # includesModality (multi)
            inc_mod_val = cell(row, 'includesModality')
            for m in split_multi(inc_mod_val):
                coarse = infer_coarse_modality(m.lower())
                mod_uri = self.get_or_create_modality(m, coarse)
                self.link(m_uri, self.MEAS.includesModality, mod_uri)

            # usesAnalyticTechnique (multi)
            tech_val = cell(row, 'usesAnalyticTechnique')
            for t in split_multi(tech_val):
                tech_uri = self.get_or_create_technique(t)
                self.link(m_uri, self.MEAS.usesAnalyticTechnique, tech_uri)

            # measuresConstruct: pick the first non-empty value across any construct-ish columns
            cons_label = None
            for cc in construct_cols:
                v = row.get(cc)
                if pd.notna(v) and str(v).strip():
                    cons_label = str(v).strip()
                    break

            if cons_label:
                cons_uri = self.get_or_create_construct(cons_label)
                self.link(m_uri, self.MEAS.measuresConstruct, cons_uri)
                made_construct_links += 1

        print(f"[INFO] Created or updated {made_measures} Measure(s).")
        if construct_cols:
            print(f"[INFO] Construct columns used (in priority order): {construct_cols}")
        print(f"[INFO] Added {made_construct_links} measuresConstruct link(s).")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True, help="Path to Excel workbook (.xlsx)")
    ap.add_argument("--sheet", default="measures", help="Worksheet name containing measure rows (default: measures)")
    ap.add_argument("--team-ttl", required=True, help="Path to teamMeasurement.ttl")
    ap.add_argument("--evidence-ttl", required=True, help="Path to evidence.ttl")
    ap.add_argument("--old-instances", default=None, help="Optional prior instances TTL to load first")
    ap.add_argument("--out-ttl", required=True, help="Output merged TTL path")
    ap.add_argument("--meas-ns", default=DEFAULT_MEAS_NS, help="MEAS namespace IRI")
    ap.add_argument("--inst-ns", default=DEFAULT_INST_NS, help="INST namespace IRI base")
    args = ap.parse_args()

    updater = OntologyUpdater(args.meas_ns, args.inst_ns)
    load_list = [args.team_ttl, args.evidence_ttl, args.old_instances]
    updater.load_ttls(load_list)

    updater.update_from_excel(args.excel, sheet=args.sheet)

    out_path = Path(args.out_ttl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    updater.graph.serialize(destination=str(out_path), format="turtle")
    print(f"Wrote merged TTL to: {out_path}")

if __name__ == "__main__":
    main()
