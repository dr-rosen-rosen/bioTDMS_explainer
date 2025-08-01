# src/ontology/querier.py
from rdflib import Graph, Variable
from rdflib.plugins.sparql import prepareQuery
from typing import List, Dict, Any, Optional
import streamlit as st
from functools import lru_cache

class SPARQLQuerier:
    """Handles SPARQL queries with caching and optimization"""
    
    def __init__(self, graph: Graph):
        self.graph = graph
        self._query_cache = {}
    
    @lru_cache(maxsize=256)
    def query_evidence_for_construct(self, construct_uri: str) -> List[Dict[str, Any]]:
        """Get all evidence related to a specific construct"""
        query = """
        PREFIX evid: <http://example.org/ontology/evidence#>
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        
        SELECT ?effect ?value ?metric ?pvalue ?study ?measure ?measureName ?doi
        WHERE {
            ?effect evid:hasDependentVariable ?measure .
            ?measure meas:measuresConstruct <%s> .
            ?effect evid:hasEffectSizeValue ?value .
            ?effect evid:usesEffectSizeMetric ?metric .
            OPTIONAL { ?effect evid:hasPValue ?pvalue }
            ?study evid:reportsEffectSize ?effect .
            ?measure meas:hasName ?measureName .
            OPTIONAL {
                ?pub evid:reportsStudy ?study .
                ?pub evid:hasDOI ?doi .
            }
        }
        """ % construct_uri
        
        results = []
        for row in self.graph.query(query):
            results.append({
                'effect': str(row.effect),
                'value': float(row.value) if row.value else None,
                'metric': str(row.metric),
                'pvalue': float(row.pvalue) if row.pvalue else None,
                'study': str(row.study),
                'measure': str(row.measure),
                'measure_name': str(row.measureName),
                'doi': str(row.doi) if row.doi else None
            })
        return results
    
    @lru_cache(maxsize=256)
    def get_measures_by_modality(self, modality_uri: str) -> List[Dict[str, Any]]:
        """Get all measures that use a specific modality"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        
        SELECT ?measure ?name ?description ?construct
        WHERE {
            ?measure a meas:Measure .
            ?measure meas:includesModality <%s> .
            ?measure meas:hasName ?name .
            OPTIONAL { ?measure meas:hasDescription ?description }
            OPTIONAL { ?measure meas:measuresConstruct ?construct }
        }
        """ % modality_uri
        
        results = []
        for row in self.graph.query(query):
            results.append({
                'measure': str(row.measure),
                'name': str(row.name),
                'description': str(row.description) if row.description else None,
                'construct': str(row.construct) if row.construct else None
            })
        return results
    
    def get_all_constructs(self) -> List[Dict[str, str]]:
        """Get all constructs in the ontology"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?construct ?label
        WHERE {
            ?construct rdfs:subClassOf* meas:Construct .
            OPTIONAL { ?construct rdfs:label ?label }
        }
        """
        
        results = []
        for row in self.graph.query(query):
            construct_uri = str(row.construct)
            # Extract local name from URI
            local_name = construct_uri.split('#')[-1]
            results.append({
                'uri': construct_uri,
                'label': str(row.label) if row.label else local_name,
                'local_name': local_name
            })
        return results
    
    def get_all_modalities(self) -> List[Dict[str, str]]:
        """Get all modalities in the ontology"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?modality ?label ?parent
        WHERE {
            ?modality rdfs:subClassOf* meas:Modality .
            OPTIONAL { ?modality rdfs:label ?label }
            OPTIONAL { ?modality rdfs:subClassOf ?parent }
        }
        """
        
        results = []
        for row in self.graph.query(query):
            modality_uri = str(row.modality)
            local_name = modality_uri.split('#')[-1]
            results.append({
                'uri': modality_uri,
                'label': str(row.label) if row.label else local_name,
                'local_name': local_name,
                'parent': str(row.parent) if row.parent else None
            })
        return results