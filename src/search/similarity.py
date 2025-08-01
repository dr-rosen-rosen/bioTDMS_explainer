# src/search/similarity.py
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from rdflib import Literal
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx

class PatternSimilarity:
    """Calculate similarity between sensor patterns and ontology measures"""
    
    def __init__(self, ontology_graph, querier):
        self.graph = ontology_graph
        self.querier = querier
        self.nx_graph = self._build_networkx_graph()
    
    def _build_networkx_graph(self) -> nx.Graph:
        """Convert RDF graph to NetworkX for path analysis"""
        G = nx.Graph()
        
        for s, p, o in self.graph:
            if not isinstance(o, Literal):
                G.add_edge(str(s), str(o), predicate=str(p))
        
        return G
    
    def calculate_pattern_similarity(self, 
                                   pattern: Dict[str, Any], 
                                   measure_uri: str) -> float:
        """Calculate similarity between a sensor pattern and a measure"""
        score = 0.0
        weights = {
            'modality_match': 0.3,
            'level_match': 0.2,
            'technique_match': 0.2,
            'semantic_distance': 0.3
        }
        
        # Get measure properties
        measure_props = self._get_measure_properties(measure_uri)
        
        # Check modality match
        if pattern.get('modality') == measure_props.get('modality'):
            score += weights['modality_match']
        
        # Check level of analysis match
        if pattern.get('level') == measure_props.get('level'):
            score += weights['level_match']
        
        # Check analytic technique match
        if pattern.get('technique') == measure_props.get('technique'):
            score += weights['technique_match']
        
        # Calculate semantic distance
        if pattern.get('construct') and measure_props.get('construct'):
            distance = self._calculate_semantic_distance(
                pattern['construct'], 
                measure_props['construct']
            )
            # Normalize distance to similarity score
            similarity = 1 / (1 + distance)
            score += weights['semantic_distance'] * similarity
        
        return score
    
    def _get_measure_properties(self, measure_uri: str) -> Dict[str, str]:
        """Extract properties of a measure"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        
        SELECT ?modality ?level ?technique ?construct
        WHERE {
            <%s> meas:includesModality ?modality ;
                 meas:hasLevelOfAnalysis ?level .
            OPTIONAL { <%s> meas:usesAnalyticTechnique ?technique }
            OPTIONAL { <%s> meas:measuresConstruct ?construct }
        }
        """ % (measure_uri, measure_uri, measure_uri)
        
        for row in self.graph.query(query):
            return {
                'modality': str(row.modality).split('#')[-1] if row.modality else None,
                'level': str(row.level).split('#')[-1] if row.level else None,
                'technique': str(row.technique).split('#')[-1] if row.technique else None,
                'construct': str(row.construct) if row.construct else None
            }
        return {}
    
    def _calculate_semantic_distance(self, uri1: str, uri2: str) -> float:
        """Calculate graph distance between two URIs"""
        try:
            path_length = nx.shortest_path_length(self.nx_graph, uri1, uri2)
            return float(path_length)
        except nx.NetworkXNoPath:
            return float('inf')
    
    def find_similar_measures(self, 
                            pattern: Dict[str, Any], 
                            top_k: int = 5) -> List[Tuple[str, float]]:
        """Find measures most similar to a given pattern"""
        all_measures = self._get_all_measures()
        similarities = []
        
        for measure_uri in all_measures:
            score = self.calculate_pattern_similarity(pattern, measure_uri)
            similarities.append((measure_uri, score))
        
        # Sort by similarity score
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def _get_all_measures(self) -> List[str]:
        """Get all measure URIs from the ontology"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT DISTINCT ?measure
        WHERE {
            ?measure a meas:Measure .
        }
        """
        return [str(row.measure) for row in self.graph.query(query)]