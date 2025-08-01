# src/ontology/loader.py
import streamlit as st
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Define namespaces
MEAS = Namespace("http://example.org/ontology/teamMeasurement#")
EVID = Namespace("http://example.org/ontology/evidence#")
INST = Namespace("http://example.org/ontology/instances#")

class OntologyManager:
    """Manages RDF graph loading and caching for the application"""
    
    def __init__(self, ontology_path: Path):
        self.ontology_path = ontology_path
        self.graph = None
        self.namespaces = {
            'meas': MEAS,
            'evid': EVID,
            'inst': INST,
            'rdf': RDF,
            'rdfs': RDFS,
            'owl': OWL
        }
    
    def load_ontologies(self) -> Graph:
        """Load and merge all ontology files"""
        if self.graph is not None:
            return self.graph
            
        g = Graph()
        
        # Bind namespaces
        for prefix, namespace in self.namespaces.items():
            g.bind(prefix, namespace)
        
        # Check if path exists
        if not self.ontology_path.exists():
            logger.error(f"Ontology path does not exist: {self.ontology_path}")
            st.error(f"Ontology directory not found: {self.ontology_path}")
            return g
        
        # Load ontology files
        ttl_files = list(self.ontology_path.glob("*.ttl"))
        if not ttl_files:
            logger.error(f"No .ttl files found in {self.ontology_path}")
            st.error(f"No ontology files found in {self.ontology_path}")
            return g
            
        for ttl_file in ttl_files:
            try:
                logger.info(f"Loading {ttl_file}")
                g.parse(ttl_file, format="turtle")
                logger.info(f"Successfully loaded {ttl_file}")
            except Exception as e:
                logger.error(f"Error loading {ttl_file}: {e}")
                st.error(f"Error loading {ttl_file}: {e}")
        
        logger.info(f"Loaded {len(g)} triples total")
        self.graph = g
        return g
    
    def get_statistics(self) -> Dict[str, int]:
        """Get basic statistics about the loaded ontology"""
        if not self.graph:
            self.load_ontologies()
        
        stats = {
            'total_triples': len(self.graph),
            'classes': len(list(self.graph.subjects(RDF.type, OWL.Class))),
            'properties': len(list(self.graph.subjects(RDF.type, OWL.ObjectProperty))) + 
                         len(list(self.graph.subjects(RDF.type, OWL.DatatypeProperty))),
            'studies': len(list(self.graph.subjects(RDF.type, EVID.Study))),
            'effects': len(list(self.graph.subjects(RDF.type, EVID.EffectSize))),
            'measures': len(list(self.graph.subjects(RDF.type, MEAS.Measure)))
        }
        return stats