#!/usr/bin/env python3
from rdflib import Graph
from rdflib.namespace import RDF, RDFS
from collections import Counter, defaultdict

TTL = "merged_instances.ttl"  # change path if needed

def localname(u):
    s = str(u)
    if "#" in s: s = s.rsplit("#", 1)[-1]
    if "/" in s: s = s.rsplit("/", 1)[-1]
    return s

g = Graph()
g.parse(TTL, format="turtle")

# 1) discover 'measure-ish' and 'construct-ish' classes
MEASUREY = {"measure", "teammeasure"}
CONSTRUCTY = {"construct","teamconstruct","concept","dimension","capability","competency","skill","attribute"}

measure_nodes, construct_nodes = set(), set()
cls_counts = Counter()
for s,_,cls in g.triples((None, RDF.type, None)):
    cls_counts[localname(cls)] += 1
    ln = localname(cls).lower()
    if any(k in ln for k in MEASUREY):
        measure_nodes.add(s)
    if any(k in ln for k in CONSTRUCTY):
        construct_nodes.add(s)

print("\n=== Top rdf:type classes ===")
for name,n in cls_counts.most_common(25):
    print(f"{name:40s}  {n}")

print(f"\n# measure-ish typed nodes: {len(measure_nodes)}")
print(f"# construct-ish typed nodes: {len(construct_nodes)}")

# 2) fallbacks if none typed
if not measure_nodes:
    for s,p,o in g.triples((None,None,None)):
        if localname(p) in {"includesModality","usesAnalyticTechnique"}:
            measure_nodes.add(s)

# 3) outgoing preds from measure nodes
pred_counts = Counter()
example_obj = {}
for m in measure_nodes:
    for _,p,o in g.triples((m,None,None)):
        pn = localname(p)
        pred_counts[pn] += 1
        example_obj.setdefault(pn, o)

print("\n=== Most common outgoing predicates from measures ===")
for name,n in pred_counts.most_common(30):
    print(f"{name:40s}  {n}")

# 4) which preds point to construct-ish objects (by type name)
pred_points_to_construct = Counter()
for m in measure_nodes:
    for _,p,o in g.triples((m,None,None)):
        for _,_,ccls in g.triples((o, RDF.type, None)):
            if any(k in localname(ccls).lower() for k in CONSTRUCTY):
                pred_points_to_construct[localname(p)] += 1
                break

print("\n=== Predicates whose objects are typed as construct-ish ===")
for name,n in pred_points_to_construct.most_common():
    print(f"{name:40s}  {n}")

# 5) sample a few measure -> (pred) -> object triples
print("\n=== Examples (first 10) from frequent preds ===")
seen = 0
for pn,_ in pred_counts.most_common(10):
    o = example_obj.get(pn)
    if o:
        print(f"{pn:40s} -> object type(s): {[localname(c) for _,_,c in g.triples((o,RDF.type,None))]}")
        seen += 1
        if seen>=10: break

# 6) small sample of measure->construct links for the best candidate predicate
LIKELY = {"measuresConstruct","measuresTeamConstruct","measuresConcept","assessesConstruct","assesses"}
cand = None
for name,_ in pred_counts.most_common():
    if name in LIKELY or "construct" in name.lower():
        cand = name; break
if not cand and pred_points_to_construct:
    cand = next(iter(pred_points_to_construct.most_common(1)))[0]

print(f"\nLikely construct-link predicate (guess): {cand}")
if cand:
    print("\nSample measure -> {cand} -> object:")
    c = 0
    for m in list(measure_nodes)[:500]:
        for _,p,o in g.triples((m,None,None)):
            if localname(p)==cand:
                ml = next((str(l) for _,_,l in g.triples((m,RDFS.label,None))), localname(m))
                ol = next((str(l) for _,_,l in g.triples((o,RDFS.label,None))), localname(o))
                print(f"  {ml}  --{cand}-->  {ol}")
                c += 1
                if c>=10: break
        if c>=10: break