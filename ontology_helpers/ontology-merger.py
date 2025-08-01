import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL
from rdflib.namespace import FOAF, SKOS, DC, DCTERMS
import os
from datetime import datetime
from typing import List, Set, Tuple

class OntologyMerger:
    """Merge and split ontology modules for WebProtégé compatibility."""
    
    def __init__(self):
        # Define namespaces
        self.MEAS = Namespace("http://example.org/ontology/teamMeasurement#")
        self.EVID = Namespace("http://example.org/ontology/evidence#")
        # self.LINK = Namespace("http://example.org/ontology/linking#")
        self.INST = Namespace("http://example.org/ontology/instances#")
        
        # Track original sources for splitting
        self.triple_sources = {}
        
    def merge_ontologies(self, 
                        ontology_files: List[str], 
                        output_file: str,
                        add_metadata: bool = True) -> Graph:
        """
        Merge multiple ontology files into a single file.
        
        Args:
            ontology_files: List of paths to TTL files to merge
            output_file: Path for merged output file
            add_metadata: Whether to add merge metadata
            
        Returns:
            Merged RDF graph
        """
        merged_graph = Graph()
        
        # Bind common namespaces
        merged_graph.bind('meas', self.MEAS)
        merged_graph.bind('evid', self.EVID)
        # merged_graph.bind('link', self.LINK)
        merged_graph.bind('inst', self.INST)
        merged_graph.bind('owl', OWL)
        merged_graph.bind('rdfs', RDFS)
        merged_graph.bind('rdf', RDF)
        
        # Track what comes from where
        source_graphs = {}
        
        # Load and merge each file
        for file_path in ontology_files:
            print(f"Loading {file_path}...")
            g = Graph()
            g.parse(file_path, format='turtle')
            
            # Store source info
            source_graphs[file_path] = g
            
            # Add all triples to merged graph
            for s, p, o in g:
                merged_graph.add((s, p, o))
                # Track source for later splitting
                self.triple_sources[(s, p, o)] = file_path
            
            print(f"  Added {len(g)} triples from {os.path.basename(file_path)}")
        
        # Add metadata about the merge
        if add_metadata:
            merge_uri = URIRef("http://example.org/ontology/merged")
            merged_graph.add((merge_uri, RDF.type, OWL.Ontology))
            merged_graph.add((merge_uri, RDFS.comment, 
                            Literal(f"Merged ontology created on {datetime.now().isoformat()}")))
            
            # Add imports statements for WebProtégé
            for file_path in ontology_files:
                module_name = os.path.basename(file_path).replace('.ttl', '')
                if module_name != 'instances':  # Don't import instances
                    import_uri = URIRef(f"http://example.org/ontology/{module_name}")
                    merged_graph.add((merge_uri, OWL.imports, import_uri))
        
        # Save merged ontology
        print(f"\nSaving merged ontology to {output_file}")
        merged_graph.serialize(output_file, format='turtle')
        print(f"Total triples in merged ontology: {len(merged_graph)}")
        
        return merged_graph
    
    def extract_instances(self, 
                         merged_file: str, 
                         output_file: str,
                         include_schema: bool = False) -> Graph:
        """
        Extract only instance data from a merged ontology.
        
        Args:
            merged_file: Path to merged ontology file
            output_file: Path for instances output file
            include_schema: Whether to include class/property definitions
            
        Returns:
            Graph containing only instances
        """
        # Load merged ontology
        full_graph = Graph()
        full_graph.parse(merged_file, format='turtle')
        
        # Create instances graph
        instances_graph = Graph()
        instances_graph.bind('inst', self.INST)
        instances_graph.bind('meas', self.MEAS)
        instances_graph.bind('evid', self.EVID)
        instances_graph.bind('rdf', RDF)
        
        # Identify instance triples
        instance_subjects = set()
        class_definitions = set()
        property_definitions = set()
        
        # First pass: identify all subjects that are instances
        for s, p, o in full_graph:
            if p == RDF.type:
                if o not in [OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, 
                           OWL.AnnotationProperty, OWL.Ontology]:
                    # This is an instance declaration
                    instance_subjects.add(s)
                else:
                    # Track schema elements
                    if o == OWL.Class:
                        class_definitions.add(s)
                    elif o in [OWL.ObjectProperty, OWL.DatatypeProperty]:
                        property_definitions.add(s)
        
        print(f"Found {len(instance_subjects)} instances")
        
        # Second pass: extract all triples about instances
        for s, p, o in full_graph:
            # Include triple if subject is an instance
            if s in instance_subjects:
                instances_graph.add((s, p, o))
                
            # Include triple if object is an instance (for object properties)
            elif o in instance_subjects and isinstance(o, URIRef):
                instances_graph.add((s, p, o))
        
        # Optionally include minimal schema
        if include_schema:
            # Add class definitions referenced by instances
            for s, p, o in full_graph:
                if s in instance_subjects and p == RDF.type and o in class_definitions:
                    # Add the class definition
                    for s2, p2, o2 in full_graph:
                        if s2 == o:
                            instances_graph.add((s2, p2, o2))
        
        # Save instances
        instances_graph.serialize(output_file, format='turtle')
        print(f"Saved {len(instances_graph)} instance triples to {output_file}")
        
        return instances_graph
    
    def validate_merge(self, original_files: List[str], merged_file: str) -> dict:
        """
        Validate that merge preserved all information.
        
        Returns:
            Dictionary with validation results
        """
        # Count triples in original files
        original_triples = set()
        original_counts = {}
        
        for file_path in original_files:
            g = Graph()
            g.parse(file_path, format='turtle')
            original_counts[os.path.basename(file_path)] = len(g)
            for triple in g:
                original_triples.add(triple)
        
        # Count triples in merged file
        merged_graph = Graph()
        merged_graph.parse(merged_file, format='turtle')
        merged_triples = set(merged_graph)
        
        # Check for lost triples
        lost_triples = original_triples - merged_triples
        extra_triples = merged_triples - original_triples
        
        validation_result = {
            'valid': len(lost_triples) == 0,
            'original_total': len(original_triples),
            'merged_total': len(merged_triples),
            'lost_triples': list(lost_triples)[:10],  # First 10 if any
            'extra_triples': list(extra_triples)[:10],  # First 10 if any
            'file_counts': original_counts
        }
        
        return validation_result
    
    def create_modular_structure(self, merged_file: str, output_dir: str):
        """
        Split a merged file back into modules based on namespace.
        Useful for maintaining modular structure after WebProtégé edits.
        """
        # Load merged ontology
        full_graph = Graph()
        full_graph.parse(merged_file, format='turtle')
        
        # Create separate graphs for each module
        measurement_graph = Graph()
        evidence_graph = Graph()
        # linking_graph = Graph()
        instances_graph = Graph()
        
        # Bind namespaces
        for g in [measurement_graph, evidence_graph, 
                #   linking_graph, 
                # instances_graph
                ]:
            g.bind('meas', self.MEAS)
            g.bind('evid', self.EVID)
            # g.bind('link', self.LINK)
            g.bind('inst', self.INST)
            g.bind('owl', OWL)
            g.bind('rdfs', RDFS)
            g.bind('rdf', RDF)
        
        # Sort triples into appropriate graphs based on namespace
        for s, p, o in full_graph:
            # Determine which module this triple belongs to
            if str(s).startswith(str(self.INST)):
                instances_graph.add((s, p, o))
            elif str(s).startswith(str(self.MEAS)) or (isinstance(o, URIRef) and str(o).startswith(str(self.MEAS))):
                measurement_graph.add((s, p, o))
            elif str(s).startswith(str(self.EVID)) or (isinstance(o, URIRef) and str(o).startswith(str(self.EVID))):
                evidence_graph.add((s, p, o))
            # elif str(s).startswith(str(self.LINK)) or (isinstance(o, URIRef) and str(o).startswith(str(self.LINK))):
            #     linking_graph.add((s, p, o))
            else:
                # Default to measurement for general ontology declarations
                measurement_graph.add((s, p, o))
        
        # Save modules
        os.makedirs(output_dir, exist_ok=True)
        
        measurement_graph.serialize(os.path.join(output_dir, 'measurement.ttl'), format='turtle')
        evidence_graph.serialize(os.path.join(output_dir, 'evidence.ttl'), format='turtle')
        # linking_graph.serialize(os.path.join(output_dir, 'linking.ttl'), format='turtle')
        instances_graph.serialize(os.path.join(output_dir, 'instances.ttl'), format='turtle')
        
        print(f"Split into modules:")
        print(f"  measurement.ttl: {len(measurement_graph)} triples")
        print(f"  evidence.ttl: {len(evidence_graph)} triples")
        # print(f"  linking.ttl: {len(linking_graph)} triples")
        print(f"  instances.ttl: {len(instances_graph)} triples")

# Convenience functions for common workflows

def merge_for_webprotege(ontology_dir: str, output_file: str = 'merged_ontology.ttl'):
    """Merge ontology files for WebProtégé upload."""
    merger = OntologyMerger()
    
    # Find all TTL files
    ttl_files = [os.path.join(ontology_dir, f) 
                 for f in os.listdir(ontology_dir) 
                 if f.endswith('.ttl') #and f != 'instances.ttl'
                 ]
    
    # Merge files
    merged_graph = merger.merge_ontologies(ttl_files, output_file)
    
    # Validate merge
    validation = merger.validate_merge(ttl_files, output_file)
    if validation['valid']:
        print("\n✓ Merge validation passed!")
    else:
        print("\n⚠ Merge validation failed!")
        print(f"  Lost {len(validation['lost_triples'])} triples")
    
    return output_file

def extract_instances_from_webprotege(downloaded_file: str, output_file: str = 'instances.ttl'):
    """Extract instances from WebProtégé download."""
    merger = OntologyMerger()
    instances = merger.extract_instances(downloaded_file, output_file)
    return output_file

# Example usage
if __name__ == "__main__":
    # Merge ontologies for WebProtégé
    print("=== Merging Ontologies for WebProtégé ===")
    merged_file = merge_for_webprotege('./ont_spec_V3')
    
    # Later, after WebProtégé editing...
    # Extract instances from downloaded file
    # print("\n=== Extracting Instances from WebProtégé ===")
    # instances_file = extract_instances_from_webprotege('webprotege_download.ttl')
    
    # Or split back into modules if needed
    # print("\n=== Splitting Back to Modules ===")
    # merger = OntologyMerger()
    # merger.create_modular_structure('webprotege_download.ttl', './ont_spec_V3_updated')