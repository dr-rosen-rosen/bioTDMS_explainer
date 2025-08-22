from pathlib import Path
from rdflib import Graph

script_dir = Path(__file__).parent.resolve()
ontology_path = (script_dir.parent.parent / "data" / "ontologies").resolve()

print(f"Checking TTL files in {ontology_path}\n")

ttl_files = list(ontology_path.glob("*.ttl"))

if not ttl_files:
    print("No TTL files found! Here’s everything in the folder:")
    print(list(ontology_path.iterdir()))
else:
    for ttl_file in ttl_files:
        g = Graph()
        g.parse(ttl_file, format="turtle")
        print(f"{ttl_file.name}: {len(g)} triples")