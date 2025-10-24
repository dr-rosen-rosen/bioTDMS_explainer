#!/usr/bin/env python3
"""
viz.py

Create three interactive HTML network visualizations from a merged ontology TTL:

1) Global overview of Measures ↔ Constructs / Modalities / Techniques
   python viz.py global --ttl merged_instances.ttl --out viz_global.html

2) Query-to-Constructs demo ("competency text" → top-k matching constructs → linked measures)
   python viz.py query --ttl merged_instances.ttl --text "team communication under time pressure" --k 5 --out viz_query.html

   Matching is purely lexical (substring) for portability; you can swap in embedding logic later.

3) Measure-set coverage (Measures ↔ (Modalities & Techniques) ↔ Constructs)
   python viz.py set --ttl merged_instances.ttl --measures measures_list.txt --out viz_measure_set.html

DEPENDENCIES: rdflib, networkx, pyvis
pip install rdflib networkx pyvis

Note: For large graphs, you may want to downsample or filter before rendering.
"""

import argparse
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDFS
import networkx as nx
from pyvis.network import Network

MEAS = Namespace("http://example.org/ontology/teamMeasurement#")
INST = Namespace("http://example.org/ontology/instances#")
LIKELY_CONSTRUCT_PRED_NAMES = {
    "measuresConstruct", "measuresTeamConstruct", "measuresConcept",
    "measuresOutcome", "measuresCapability"
}
LIKELY_CONSTRUCT_CLASS_HINTS = {"construct","teamconstruct","concept","dimension","capability","competency","skill","attribute"}
LIKELY_CONSTRUCT_PRED_NAMES  = {"measuresConstruct","measuresTeamConstruct","measuresConcept","assessesConstruct","assesses"}
EXCLUDE_PRED_NAMES           = {"includesModality","usesAnalyticTechnique","hasLevelOfAnalysis","hasDescription","hasSource","hasID","hasLabel"}

def load_graph(ttl_path: str) -> Graph:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return g

def add_node(nt: Network, node_id: str, label: str, group: str):
    nt.add_node(node_id, label=label, title=label, group=group, shape="dot")

def add_edge(nt: Network, src: str, dst: str, label: str):
    nt.add_edge(src, dst, label=label, arrows="to")

def _localname(uri):
    s = str(uri)
    if '#' in s:
        s = s.rsplit('#', 1)[-1]
    if '/' in s:
        s = s.rsplit('/', 1)[-1]
    return s

from rdflib.namespace import RDF, RDFS
from rdflib import URIRef

def _ln(u):
    s = str(u)
    if "#" in s: s = s.rsplit("#",1)[-1]
    if "/" in s: s = s.rsplit("/",1)[-1]
    return s

def _label(g, n):
    lab = next((str(l) for _,_,l in g.triples((n, RDFS.label, None))), None)
    return lab or _ln(n)

def list_modalities(ttl: str, like: str = ""):
    g = load_graph(ttl)
    like = like.lower().strip()
    out = []
    for m in g.subjects(RDF.type, MEAS.Modality):
        lab = _label(g, m)
        if not like or like in lab.lower():
            out.append((lab, str(m)))
    out.sort()
    print("Modalities:")
    for lab, uri in out[:500]:
        print(f"  {lab}  ->  {uri}")

def list_techniques(ttl: str, like: str = ""):
    g = load_graph(ttl)
    like = like.lower().strip()
    out = []
    # analyticTechnique class name in your graph is 'analyticTechnique'
    for t in g.subjects(RDF.type, MEAS.analyticTechnique):
        lab = _label(g, t)
        if not like or like in lab.lower():
            out.append((lab, str(t)))
    out.sort()
    print("Analytic Techniques:")
    for lab, uri in out[:500]:
        print(f"  {lab}  ->  {uri}")

def resolve_modalities(g: Graph, names: list[str]) -> set[URIRef]:
    """Resolve input strings to Modality nodes by case-insensitive substring on rdfs:label or localname."""
    targets = set()
    names = [n.strip().lower() for n in names if n.strip()]
    if not names:
        return targets
    for mo in g.subjects(RDF.type, MEAS.Modality):
        lab = _label(g, mo).lower()
        loc = _ln(mo).lower()
        if any(n in lab or n == loc for n in names):
            targets.add(mo)
    return targets

def resolve_techniques(g: Graph, names: list[str]) -> set[URIRef]:
    """Resolve input strings to analyticTechnique nodes by case-insensitive substring on rdfs:label or localname."""
    targets = set()
    names = [n.strip().lower() for n in names if n.strip()]
    if not names:
        return targets
    for t in g.subjects(RDF.type, MEAS.analyticTechnique):
        lab = _label(g, t).lower()
        loc = _ln(t).lower()
        if any(n in lab or n == loc for n in names):
            targets.add(t)
    return targets

def discover_constructs_and_predicates(g: Graph):
    """
    Infer which predicates link Measures to Constructs (namespace-agnostic).
    Returns (construct_nodes_set, predicate_set_used).
    Rules:
      - Identify Measures by rdf:type whose class localname contains 'measure'
        OR subject that uses typical measure edges.
      - Candidate construct-link predicates:
          * localname in LIKELY_CONSTRUCT_PRED_NAMES
          * OR localname contains 'construct'
          * OR points to an object typed with class whose localname contains 'construct'
      - Exclude common non-construct edges.
    """
    from rdflib.namespace import RDF
    from collections import Counter, defaultdict

    EXCLUDE_PRED_NAMES = {
        "includesModality", "usesAnalyticTechnique", "hasLevelOfAnalysis",
        "hasDescription", "hasSource", "hasID", "hasLabel"
    }

    # 1) find measures
    measures = set()
    for s, _, cls in g.triples((None, RDF.type, None)):
        if 'measure' in _localname(cls).lower():
            measures.add(s)
    if not measures:
        # heuristic fallback
        for s, p, o in g.triples((None, None, None)):
            if _localname(p) in {"includesModality", "usesAnalyticTechnique"}:
                measures.add(s)

    # 2) collect outgoing predicates from measures
    pred_counter = Counter()
    preds_point_to_construct = defaultdict(bool)
    candidate_preds = set()

    # pre-seed with likely names (any namespace)
    for s, p, o in g.triples((None, None, None)):
        if _localname(p) in LIKELY_CONSTRUCT_PRED_NAMES:
            candidate_preds.add(p)

    for m in measures:
        for _, p, o in g.triples((m, None, None)):
            lname = _localname(p)
            pred_counter[lname] += 1
            if lname in EXCLUDE_PRED_NAMES:
                continue
            if 'construct' in lname.lower():
                candidate_preds.add(p)
            # check object type
            for _, _, ccls in g.triples((o, RDF.type, None)):
                if 'construct' in _localname(ccls).lower():
                    preds_point_to_construct[p] = True

    for p, flag in preds_point_to_construct.items():
        if flag:
            candidate_preds.add(p)

    # Fallback: most common non-excluded outgoing predicate
    if not candidate_preds:
        for lname, _ in pred_counter.most_common():
            if lname not in EXCLUDE_PRED_NAMES:
                for s, p, o in g.triples((None, None, None)):
                    if _localname(p) == lname:
                        candidate_preds.add(p)
                        break
            if candidate_preds:
                break

    # 3) collect constructs via these predicates
    constructs = set()
    for m in measures:
        for _, p, o in g.triples((m, None, None)):
            if any(_localname(p) == _localname(cp) for cp in candidate_preds):
                constructs.add(o)

    # 4) EXCLUDE anything that looks like a measure from constructs
    constructs = {
        c for c in constructs
        if not _localname(c).lower().startswith("measure_")
        and "measure" not in _localname(c).lower()
    }

    return constructs, candidate_preds

def viz_global(ttl: str, out_html: str, max_measures: int = 400):
    from rdflib.namespace import RDF, RDFS
    g = load_graph(ttl)

    # Build PyVis network
    # nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=True)
    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)
    nt.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=200, spring_strength=0.02, damping=0.8)
    nt.toggle_physics(True)
    nt.set_options("""
    var options = {
    nodes: { font: { size: 20, face: 'arial', vadjust: -10 } },
    edges: { smooth: { type: 'dynamic' } },
    physics: {
        barnesHut: { gravitationalConstant: -30000, springLength: 200, springConstant: 0.01 },
        stabilization: { iterations: 200 }
    }
    }
    """)

    # Helper: label fallback
    def label_or_fragment(node):
        lab = None
        for _, _, l in g.triples((node, RDFS.label, None)):
            lab = str(l)
            break
        if lab:
            return lab
        s = str(node)
        return s.rsplit('#', 1)[-1].rsplit('/', 1)[-1]

    # Collect measures by explicit rdf:type
    measures = []
    for m in g.subjects(RDF.type, MEAS.Measure):
        measures.append(m)
        if len(measures) >= max_measures:
            break

    # If none found, try loose heuristic: anything that links via meas:includesModality or usesAnalyticTechnique
    if not measures:
        for m in set(g.subjects(MEAS.includesModality, None)) | set(g.subjects(MEAS.usesAnalyticTechnique, None)) | set(g.subjects(MEAS.measuresConstruct, None)):
            measures.append(m)
            if len(measures) >= max_measures:
                break


    # Filter out placeholder node
    measures = [m for m in measures if not str(m).endswith('measure_unknown')]
    # Add nodes and edges
    added_nodes = set()
    def add_node_safe(n, group):
        nid = str(n)
        if nid in added_nodes:
            return
        nt.add_node(nid, label=label_or_fragment(n), title=str(n), group=group, shape="dot")
        added_nodes.add(nid)

    for m in measures:
        add_node_safe(m, "Measure")

        # constructs
        for c in g.objects(m, MEAS.measuresConstruct):
            add_node_safe(c, "Construct")
            nt.add_edge(str(m), str(c), label="measuresConstruct", arrows="to")

        # modalities
        for mo in g.objects(m, MEAS.includesModality):
            add_node_safe(mo, "Modality")
            nt.add_edge(str(m), str(mo), label="includesModality", arrows="to")

        # techniques
        for t in g.objects(m, MEAS.usesAnalyticTechnique):
            add_node_safe(t, "Technique")
            nt.add_edge(str(m), str(t), label="usesAnalyticTechnique", arrows="to")

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)
def viz_mod_center(ttl: str, modalities: list[str], out_html: str, show_tech_ring: bool = True, limit_related: int = 500):
    """
    Start from Modality nodes (e.g., EEG, fNIRS, ECG/IBI, Respiration),
    pull all Measures that include them, optionally add each measure's Analytic Techniques.
    """
    g = load_graph(ttl)
    mos = resolve_modalities(g, modalities)
    if not mos:
        print("[WARN] No modalities resolved. Use: python viz.py list-modalities --ttl ... --like EEG")
        nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)
        nt.write_html(out_html, notebook=False, open_browser=False); print(out_html); return

    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)

    # center nodes (modalities)
    center_ids = set()
    for mo in mos:
        cid = str(mo)
        center_ids.add(cid)
        nt.add_node(cid, label=_label(g, mo), group="ModalityCenter", shape="hexagon", size=28)

    # measures that include any of these modalities
    measures = set()
    for m in g.subjects(RDF.type, MEAS.Measure):
        its_mos = set(g.objects(m, MEAS.includesModality))
        if any(mo in its_mos for mo in mos):
            measures.add(m)
            if len(measures) >= limit_related:
                break

    # add measures & edges to their modalities
    for m in measures:
        mid = str(m)
        nt.add_node(mid, label=_label(g, m), group="Measure", shape="dot", size=12)
        for mo in g.objects(m, MEAS.includesModality):
            cid = str(mo)
            if cid in center_ids:
                nt.add_edge(mid, cid, title="includesModality")

    # optional ring: techniques for each measure
    if show_tech_ring:
        seen_tech = set()
        for m in measures:
            for t in g.objects(m, MEAS.usesAnalyticTechnique):
                tid = str(t)
                if tid not in seen_tech:
                    nt.add_node(tid, label=_label(g, t), group="Technique", shape="triangle", size=14)
                    seen_tech.add(tid)
                nt.add_edge(str(m), tid, title="usesAnalyticTechnique")

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)


def viz_tech_center(ttl: str, techniques: list[str], out_html: str, show_mod_ring: bool = True, limit_related: int = 500):
    """
    Start from Analytic Technique nodes (e.g., 'entropy', 'DSA'),
    pull all Measures that use them, optionally add each measure's Modalities.
    """
    g = load_graph(ttl)
    techs = resolve_techniques(g, techniques)
    if not techs:
        print("[WARN] No techniques resolved. Use: python viz.py list-techniques --ttl ... --like entropy")
        nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)
        nt.write_html(out_html, notebook=False, open_browser=False); print(out_html); return

    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)

    # center nodes (techniques)
    center_ids = set()
    for t in techs:
        tid = str(t)
        center_ids.add(tid)
        nt.add_node(tid, label=_label(g, t), group="TechniqueCenter", shape="triangle", size=28)

    # measures that use any of these techniques
    measures = set()
    for m in g.subjects(RDF.type, MEAS.Measure):
        its_ts = set(g.objects(m, MEAS.usesAnalyticTechnique))
        if any(t in its_ts for t in techs):
            measures.add(m)
            if len(measures) >= limit_related:
                break

    # add measures & edges to techniques
    for m in measures:
        mid = str(m)
        nt.add_node(mid, label=_label(g, m), group="Measure", shape="dot", size=12)
        for t in g.objects(m, MEAS.usesAnalyticTechnique):
            tid = str(t)
            if tid in center_ids:
                nt.add_edge(mid, tid, title="usesAnalyticTechnique")

    # optional ring: modalities for each measure
    if show_mod_ring:
        seen_mod = set()
        for m in measures:
            for mo in g.objects(m, MEAS.includesModality):
                moid = str(mo)
                if moid not in seen_mod:
                    nt.add_node(moid, label=_label(g, mo), group="Modality", shape="hexagon", size=14)
                    seen_mod.add(moid)
                nt.add_edge(str(m), moid, title="includesModality")

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)

def lexical_match_constructs(g: Graph, text: str, k: int = 5):
    """
    Fuzzy lexical match over candidate constructs' labels/altLabels/descriptions.
    Drops weak matches and anything "measure-like".
    """
    from rdflib.namespace import RDFS
    from rdflib import URIRef
    import re, difflib

    constructs, _preds = discover_constructs_and_predicates(g)
    t = (text or "").strip()
    if not t or not constructs:
        return []
    t_l = t.lower()

    SKOS_ALT = URIRef("http://www.w3.org/2004/02/skos/core#altLabel")

    def label_bundle(c):
        labels = set()
        for _, _, lab in g.triples((c, RDFS.label, None)):
            labels.add(str(lab))
        for _, _, lab in g.triples((c, SKOS_ALT, None)):
            labels.add(str(lab))
        # include any '*description*' property
        for _, p, lab in g.triples((c, None, None)):
            if 'description' in _localname(p).lower():
                try:
                    labels.add(str(lab))
                except Exception:
                    pass
        if not labels:
            labels.add(_localname(c))
        return labels

    def tokens(s):
        return re.findall(r"[A-Za-z0-9]+", s.lower())

    def bigrams(seq):
        return set(zip(seq, seq[1:])) if len(seq) > 1 else set()

    scored = []
    toks_t = tokens(t_l)
    set_t = set(toks_t)
    bgr_t = bigrams(toks_t)

    for c in constructs:
        # never match measure-like nodes as constructs
        lname = _localname(c).lower()
        if lname.startswith("measure_") or "measure" in lname:
            continue

        lb = label_bundle(c)
        max_score = 0.0
        best_label = None
        keep = False
        for s in lb:
            s_l = s.lower()
            substr = 1.0 if t_l in s_l else 0.0
            toks_s = tokens(s_l)
            set_s = set(toks_s)
            jacc = (len(set_t & set_s) / len(set_t | set_s)) if (set_t or set_s) else 0.0
            bgr_s = bigrams(toks_s)
            bjac = (len(bgr_t & bgr_s) / len(bgr_t | bgr_s)) if (bgr_t or bgr_s) else 0.0
            ratio = difflib.SequenceMatcher(None, t_l, s_l).ratio()

            score = 2.5*substr + 1.5*jacc + 1.2*bjac + 1.0*ratio

            # require at least some overlap to keep (or an exact substring)
            if substr > 0 or jacc >= 0.05:
                keep = True
            if score > max_score:
                max_score = score
                best_label = s

        if keep and max_score >= 0.35:
            scored.append((max_score, c, best_label or next(iter(lb))))

    # If nothing decent, take top by ratio but still exclude measure-like names
    if not scored and constructs:
        for c in constructs:
            lname = _localname(c).lower()
            if lname.startswith("measure_") or "measure" in lname:
                continue
            lab = next(iter(label_bundle(c)))
            ratio = difflib.SequenceMatcher(None, t_l, lab.lower()).ratio()
            scored.append((ratio, c, lab))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(c, lab, float(s)) for s, c, lab in scored[:k]]

def viz_query(ttl: str, text: str, out_html: str, k: int = 5):
    from rdflib.namespace import RDFS

    g = load_graph(ttl)
    matches = lexical_match_constructs(g, text, k=k)

    constructs_all, pred_set = discover_constructs_and_predicates(g)
    pred_names = {_localname(p) for p in pred_set} or {'measuresConstruct'}

    nt = Network(height="800px", width="100%", cdn_resources="remote", notebook=False, directed=True)
    query_id = f"query:{text[:60]}"
    add_node(nt, query_id, f"Query: {text}", "Query")

    if not matches:
        nt.add_node("note:none", label="No construct matches found", group="Info", shape="box")
        nt.add_edge(query_id, "note:none", label="0 results")
        nt.write_html(out_html, notebook=False, open_browser=False)
        print(out_html)
        return

    for c, clabel, score in matches:
        node_label = f"{clabel}  (score {score:.2f})"
        add_node(nt, str(c), node_label, "Construct")
        add_edge(nt, query_id, str(c), "matchesConstruct")

        # Expand to measures via discovered predicates
        for s, p, o in g.triples((None, None, c)):
            if _localname(p) in pred_names:
                m = s
                # skip placeholder/unknown
                m_lname = _localname(m).lower()
                if m_lname == "measure_unknown" or "measure_unknown" in m_lname:
                    continue

                # label if present
                mlabel = None
                for _, _, l in g.triples((m, RDFS.label, None)):
                    mlabel = str(l); break
                add_node(nt, str(m), mlabel or _localname(m), "Measure")
                add_edge(nt, str(c), str(m), _localname(p))

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)

def viz_measure_set(ttl: str, measures_list_path: str, out_html: str):
    g = load_graph(ttl)
    ids = [line.strip() for line in Path(measures_list_path).read_text().splitlines() if line.strip()]
    # Interpret IDs as either full IRIs or local IDs after inst:measure_
    m_uris = []
    for idv in ids:
        if idv.startswith("http://") or idv.startswith("https://"):
            m_uris.append(idv)
        else:
            # allow raw ids like "meas_001" or "measure_meas_001"
            local = idv
            if not local.startswith("measure_"):
                local = "measure_" + local
            m_uris.append(str(INST[local]))

    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=True)

    # Add measure nodes and link out
    for m in m_uris:
        lab_res = list(g.query(f"""
            PREFIX rdfs: <{RDFS}>
            SELECT ?l WHERE {{ <{m}> rdfs:label ?l . }} LIMIT 1
        """))
        mlabel = lab_res[0][0] if lab_res else Path(m).name
        add_node(nt, m, str(mlabel), "Measure")

        # modality
        for mo, mol in g.query(f"""
            PREFIX meas: <{MEAS}>
            PREFIX rdfs: <{RDFS}>
            SELECT DISTINCT ?mo ?mol WHERE {{
              <{m}> meas:includesModality ?mo . ?mo rdfs:label ?mol .
            }}
        """):
            add_node(nt, str(mo), str(mol), "Modality")
            add_edge(nt, m, str(mo), "includesModality")

        # technique
        for t, tl in g.query(f"""
            PREFIX meas: <{MEAS}>
            PREFIX rdfs: <{RDFS}>
            SELECT DISTINCT ?t ?tl WHERE {{
              <{m}> meas:usesAnalyticTechnique ?t . ?t rdfs:label ?tl .
            }}
        """):
            add_node(nt, str(t), str(tl), "Technique")
            add_edge(nt, m, str(t), "usesAnalyticTechnique")

        # construct
        for c, cl in g.query(f"""
            PREFIX meas: <{MEAS}>
            PREFIX rdfs: <{RDFS}>
            SELECT DISTINCT ?c ?cl WHERE {{
              <{m}> meas:measuresConstruct ?c . ?c rdfs:label ?cl .
            }}
        """):
            add_node(nt, str(c), str(cl), "Construct")
            add_edge(nt, m, str(c), "measuresConstruct")

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(f"Wrote {out_html}")
# ===== Helpers for measure set expansions =====
from rdflib.namespace import RDF, RDFS
from rdflib import URIRef

def _ln(u):
    s = str(u)
    if "#" in s: s = s.rsplit("#",1)[-1]
    if "/" in s: s = s.rsplit("/",1)[-1]
    return s

def _label(g, n):
    lab = next((str(l) for _,_,l in g.triples((n, RDFS.label, None))), None)
    return lab or _ln(n)

from difflib import SequenceMatcher
import re

def _norm_text(s: str) -> str:
    if s is None:
        return ""
    # strip quotes (straight + smart), collapse whitespace, lowercase
    s = str(s)
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-").replace("—", "-")
    s = s.strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def _resolve_measures(g: Graph, path: str) -> set[str]:
    """
    Read a file of measure identifiers (label or full IRI) and resolve to URIs.
    Robust to quotes, spacing, case, and partial matches.
    """
    # read seeds.txt lines
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")  # handles BOM if present
    except Exception:
        raw = Path(path).read_text()  # fallback
    wanted = [ln for ln in (l.strip() for l in raw.splitlines()) if ln]

    # index labels -> uris + localnames -> uris
    label_index = {}          # normalized label -> set(uris)
    local_index = {}          # normalized localname -> set(uris)
    all_entries = []          # [(uri, label_norm, local_norm, label_raw)]

    from rdflib.namespace import RDF, RDFS
    for m in g.subjects(RDF.type, MEAS.Measure):
        lab_raw = next((str(l) for _, _, l in g.triples((m, RDFS.label, None))), "")
        lab_norm = _norm_text(lab_raw)
        loc_norm = _norm_text(str(m).rsplit("#", 1)[-1].rsplit("/", 1)[-1])
        u = str(m)
        label_index.setdefault(lab_norm, set()).add(u)
        local_index.setdefault(loc_norm, set()).add(u)
        all_entries.append((u, lab_norm, loc_norm, lab_raw))

    resolved = set()

    def best_candidates(qnorm: str):
        # Exact label
        if qnorm in label_index:
            return list(label_index[qnorm])
        # Exact localname
        if qnorm in local_index:
            return list(local_index[qnorm])

        # Substring search over labels
        subs = [u for (u, lab, loc, _) in all_entries if qnorm and qnorm in lab]
        if subs:
            return subs

        # Fuzzy (difflib) over labels & locals
        scored = []
        for (u, lab, loc, _) in all_entries:
            r = max(SequenceMatcher(None, qnorm, lab).ratio(),
                    SequenceMatcher(None, qnorm, loc).ratio())
            scored.append((r, u))
        scored.sort(reverse=True)
        # keep reasonable matches only
        return [u for (r, u) in scored if r >= 0.60][:10]

    for line in wanted:
        q = _norm_text(line)
        if not q:
            continue
        # full IRI
        if q.startswith("http://") or q.startswith("https://"):
            resolved.add(line.strip())
            continue
        # try measure_ localname directly
        if q.startswith("measure_"):
            if q in local_index:
                resolved |= local_index[q]
                continue
        # general matching
        cands = best_candidates(q)
        resolved |= set(cands)

    if not resolved:
        # print some helpful suggestions to the console
        print("[WARN] No seed measures resolved. Nearby label suggestions:")
        # show top 10 labels similar to the first query line
        if wanted:
            q0 = _norm_text(wanted[0])
            candidates = sorted(
                ((max(SequenceMatcher(None, q0, lab).ratio(),
                      SequenceMatcher(None, q0, loc).ratio()), u, raw)
                 for (u, lab, loc, raw) in all_entries),
                reverse=True
            )[:10]
            for r, u, raw in candidates:
                print(f"  {r:.2f}  {raw}  ->  {u}")

    return resolved

def _measure_modalities(g: Graph, m) -> set:
    return set(g.objects(m, MEAS.includesModality))

def _measure_techniques(g: Graph, m) -> set:
    return set(g.objects(m, MEAS.usesAnalyticTechnique))

def _modality_bucket(label: str) -> str | None:
    """
    Heuristic bucket: ANS vs CNS (for compact grouping).
    """
    s = label.lower()
    # ANS hints
    ans_terms = ["autonomic", "sympathetic", "parasympathetic", "hrv", "ibi", "ecg", "eda", "gsr", "pupil", "pupill", "resp", "breath", "skin conduct", "cardiac"]
    if any(t in s for t in ans_terms):
        return "ANS"
    # CNS hints
    cns_terms = ["cns", "eeg", "meg", "erp", "fnirs", "bold", "fmri", "hemodynamic", "neural", "brain"]
    if any(t in s for t in cns_terms):
        return "CNS"
    return None
# ---------- FINDER: list measures by modality/label keywords ----------
def find_measures(ttl: str, mod_keywords=None, label_keywords=None, limit=200):
    """
    Print measures whose modalities or labels match any of the provided keywords (case-insensitive).
    """
    from rdflib.namespace import RDF, RDFS

    def norm(s): return (s or "").strip().lower()
    mod_keywords = [k.lower() for k in (mod_keywords or [])]
    label_keywords = [k.lower() for k in (label_keywords or [])]

    g = load_graph(ttl)

    hits = []
    for m in g.subjects(RDF.type, MEAS.Measure):
        mlabel = next((str(l) for _,_,l in g.triples((m, RDFS.label, None))), "")
        mlabel_n = norm(mlabel)

        # collect modality labels for this measure
        mos = list(g.objects(m, MEAS.includesModality))
        mo_labels = [next((str(l) for _,_,l in g.triples((mo, RDFS.label, None))), str(mo)) for mo in mos]
        mo_labels_n = [norm(x) for x in mo_labels]

        mod_ok = (not mod_keywords) or any(any(k in x for x in mo_labels_n) for k in mod_keywords)
        lab_ok = (not label_keywords) or any(k in mlabel_n for k in label_keywords)

        if mod_ok and lab_ok:
            hits.append((mlabel or str(m), str(m), mo_labels[:5]))

        if len(hits) >= limit:
            break

    if not hits:
        print("[INFO] No measures matched your filters.")
    else:
        print("Matched measures (label  ->  URI  [first few modalities]):")
        for lab, uri, mos in hits:
            print(f"  {lab}  ->  {uri}  {mos[:5]}")

def _style_seed(nt: Network, node_id: str):
    # make seed measures visually pop
    try:
        nt.nodes[-1]  # ensure list exists
    except:
        return
    for n in nt.nodes:
        if n["id"] == node_id:
            n.update({"shape": "star", "size": 22})
            break

# ===== Modality-first view =====
def viz_modality_first(ttl: str, seeds_path: str, out_html: str, use_buckets: bool = True, limit_related: int = 300):
    g = load_graph(ttl)
    seed_uris = _resolve_measures(g, seeds_path)
    if not seed_uris:
        print("[WARN] No seed measures resolved from file.")
    seed_nodes = [URIRef(u) for u in seed_uris]

    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)

    # 1) Collect modalities from seeds
    modalities = set()
    for su in seed_nodes:
        modalities |= _measure_modalities(g, su)

    # 2) Optionally reduce to ANS/CNS buckets; else keep specific modalities
    centers = set()
    center_labels = {}
    if use_buckets:
        buckets = {}
        for mo in modalities:
            b = _modality_bucket(_label(g, mo)) or "Other"
            buckets.setdefault(b, set()).add(mo)
        for b in buckets.keys():
            centers.add(b)  # just the string name as node id
            center_labels[b] = b
    else:
        for mo in modalities:
            centers.add(str(mo))
            center_labels[str(mo)] = _label(g, mo)

    # 3) Add center nodes (modalities or buckets)
    for cid in centers:
        nt.add_node(cid, label=center_labels[cid], group="ModalityCenter", shape="hexagon", size=28)

    # 4) Add seed measures connected to their centers
    seen_measures = set()
    for su in seed_nodes:
        lab = _label(g, su)
        nid = str(su)
        nt.add_node(nid, label=lab, group="SeedMeasure", shape="dot", size=16)
        _style_seed(nt, nid)
        seen_measures.add(nid)
        # connect to centers
        mos = _measure_modalities(g, su)
        if use_buckets:
            buckets_here = set(_modality_bucket(_label(g, mo)) or "Other" for mo in mos)
            for b in buckets_here:
                nt.add_edge(nid, b)
        else:
            for mo in mos:
                nt.add_node(str(mo), label=_label(g, mo), group="Modality")
                nt.add_edge(nid, str(mo))

    # 5) Pull in related measures that share these modalities/buckets
    related = set()
    for m in g.subjects(RDF.type, MEAS.Measure):
        mid = str(m)
        if mid in seen_measures:
            continue
        mos = _measure_modalities(g, m)
        if not mos:
            continue
        if use_buckets:
            bm = set(_modality_bucket(_label(g, mo)) or "Other" for mo in mos)
            if any(c in centers for c in bm):
                related.add(m)
        else:
            if any(str(mo) in centers for mo in mos):
                related.add(m)

    # limit to keep viz readable
    related = list(related)[:limit_related]

    for m in related:
        mid = str(m)
        nt.add_node(mid, label=_label(g, m), group="RelatedMeasure", shape="dot", size=12)
        # connect to centers
        mos = _measure_modalities(g, m)
        if use_buckets:
            buckets_here = set(_modality_bucket(_label(g, mo)) or "Other" for mo in mos)
            for b in buckets_here:
                if b in centers:
                    nt.add_edge(mid, b)
        else:
            for mo in mos:
                if str(mo) in centers:
                    nt.add_edge(mid, str(mo))

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)

# ===== Technique-first view =====
def viz_technique_first(ttl: str, seeds_path: str, out_html: str, technique_contains: str = "", limit_related: int = 300):
    """
    technique_contains: if provided (e.g., 'DSA' or 'entropy'), restrict center techniques to labels containing this substring (case-insensitive).
    """
    g = load_graph(ttl)
    seed_uris = _resolve_measures(g, seeds_path)
    seed_nodes = [URIRef(u) for u in seed_uris]

    nt = Network(height="850px", width="100%", cdn_resources="remote", notebook=False, directed=False)

    # 1) Collect techniques from seeds
    techs = set()
    for su in seed_nodes:
        techs |= _measure_techniques(g, su)

    if technique_contains:
        tsub = technique_contains.lower()
        techs = {t for t in techs if tsub in _label(g, t).lower()}

    if not techs:
        print("[WARN] No techniques discovered from seeds (or filtered away).")
    centers = {str(t) for t in techs}

    # 2) Add center technique nodes
    for tid in centers:
        nt.add_node(tid, label=_label(g, URIRef(tid)), group="TechniqueCenter", shape="triangle", size=28)

    # 3) Add seed measures, link to techniques
    seen_measures = set()
    for su in seed_nodes:
        nid = str(su)
        nt.add_node(nid, label=_label(g, su), group="SeedMeasure", shape="dot", size=16)
        _style_seed(nt, nid)
        seen_measures.add(nid)
        for t in _measure_techniques(g, su):
            tid = str(t)
            if tid in centers:
                nt.add_edge(nid, tid)

    # 4) Pull in related measures that use one or more of the center techniques
    related = set()
    for m in g.subjects(RDF.type, MEAS.Measure):
        mid = str(m)
        if mid in seen_measures:
            continue
        ts = _measure_techniques(g, m)
        if any(str(t) in centers for t in ts):
            related.add(m)

    related = list(related)[:limit_related]

    for m in related:
        mid = str(m)
        nt.add_node(mid, label=_label(g, m), group="RelatedMeasure", shape="dot", size=12)
        for t in _measure_techniques(g, m):
            tid = str(t)
            if tid in centers:
                nt.add_edge(mid, tid)

    nt.write_html(out_html, notebook=False, open_browser=False)
    print(out_html)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g1 = sub.add_parser("global", help="Global overview viz")
    g1.add_argument("--ttl", required=True)
    g1.add_argument("--out", required=True)
    g1.add_argument("--max-measures", type=int, default=400)

    q1 = sub.add_parser("query", help="User text → constructs → measures")
    q1.add_argument("--ttl", required=True)
    q1.add_argument("--text", required=True)
    q1.add_argument("--k", type=int, default=5)
    q1.add_argument("--out", required=True)

    s1 = sub.add_parser("set", help="Measure-set coverage viz")
    s1.add_argument("--ttl", required=True)
    s1.add_argument("--measures", required=True, help="Text file with one measure id per line (ids or full IRIs)")
    s1.add_argument("--out", required=True)
    mf = sub.add_parser("modality-first", help="Seed measures -> Modality(center) -> related measures")
    mf.add_argument("--ttl", required=True)
    mf.add_argument("--seeds", required=True, help="Text file: one seed measure (label or IRI) per line")
    mf.add_argument("--out", required=True)
    mf.add_argument("--no-buckets", action="store_true", help="Do not group modalities (ANS/CNS); show specific modalities")
    # finder subcommand
    fm = sub.add_parser("find", help="Find measures by modality/label substring")
    fm.add_argument("--ttl", required=True)
    fm.add_argument("--mod", nargs="*", default=[], help="Modality keyword(s), e.g., eeg fnirs ibi ecg respiration electrodermal")
    fm.add_argument("--label-like", nargs="*", default=[], help="Measure label substring(s), e.g., physio entropy")
    
    tf = sub.add_parser("technique-first", help="Seed measures -> Technique(center) -> related measures")
    tf.add_argument("--ttl", required=True)
    tf.add_argument("--seeds", required=True, help="Text file: one seed measure (label or IRI) per line")
    tf.add_argument("--out", required=True)
    tf.add_argument("--filter-tech", default="", help="Substring to restrict center techniques (e.g., 'DSA' or 'entropy')")
    # list helpers
    lm = sub.add_parser("list-modalities", help="Print all modalities (filter with --like)")
    lm.add_argument("--ttl", required=True)
    lm.add_argument("--like", default="", help="Substring filter, e.g., 'eeg' or 'fnirs'")

    lt = sub.add_parser("list-techniques", help="Print all analytic techniques (filter with --like)")
    lt.add_argument("--ttl", required=True)
    lt.add_argument("--like", default="", help="Substring filter, e.g., 'entropy' or 'DSA'")

    # center-first vizzes
    mc = sub.add_parser("mod-center", help="Center on modality labels and pull all measures that include them")
    mc.add_argument("--ttl", required=True)
    mc.add_argument("--mods", nargs="+", required=True, help="Modality labels or substrings, e.g., EEG fNIRS ECG Respiration")
    mc.add_argument("--out", required=True)
    mc.add_argument("--no-tech-ring", action="store_true", help="Do not add analytic technique ring")

    tc = sub.add_parser("tech-center", help="Center on technique labels and pull all measures that use them")
    tc.add_argument("--ttl", required=True)
    tc.add_argument("--techs", nargs="+", required=True, help="Technique labels or substrings, e.g., entropy DSA")
    tc.add_argument("--out", required=True)
    tc.add_argument("--no-mod-ring", action="store_true", help="Do not add modality ring")
    args = ap.parse_args()
    if args.cmd == "global":
        viz_global(args.ttl, args.out, max_measures=args.max_measures)
    elif args.cmd == "query":
        viz_query(args.ttl, args.text, args.out, k=args.k)
    elif args.cmd == "set":
        viz_measure_set(args.ttl, args.measures, args.out)
    elif args.cmd == "modality-first":
        viz_modality_first(args.ttl, args.seeds, args.out, use_buckets=(not args.no_buckets))
    elif args.cmd == "technique-first":
        viz_technique_first(args.ttl, args.seeds, args.out, technique_contains=args.filter_tech)
    elif args.cmd == "find":
        find_measures(args.ttl, mod_keywords=args.mod, label_keywords=args.label_like)
    elif args.cmd == "list-modalities":
        list_modalities(args.ttl, like=args.like)
    elif args.cmd == "list-techniques":
        list_techniques(args.ttl, like=args.like)
    elif args.cmd == "mod-center":
        # was: args.no-tech_ring  (invalid)
        viz_mod_center(args.ttl, args.mods, args.out, show_tech_ring=(not args.no_tech_ring))

    elif args.cmd == "tech-center":
        # was: args.no-mod_ring  (invalid)
        viz_tech_center(args.ttl, args.techs, args.out, show_mod_ring=(not args.no_mod_ring))

if __name__ == "__main__":
    main()
