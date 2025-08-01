# src/search/faceted_search.py
from typing import Dict, List, Any, Optional, Tuple
import streamlit as st
from dataclasses import dataclass

@dataclass
class SearchFilters:
    """Container for search filter values"""
    modalities: List[str] = None
    levels_of_analysis: List[str] = None
    study_populations: List[str] = None
    effect_size_range: Tuple[float, float] = None
    p_value_threshold: float = None
    
class FacetedSearch:
    """Implements faceted filtering for evidence search"""
    
    def __init__(self, querier):
        self.querier = querier
    
    def get_available_facets(self) -> Dict[str, List[str]]:
        """Get all available facet values from the ontology"""
        facets = {
            'modalities': self._get_all_modalities(),
            'levels_of_analysis': self._get_all_levels(),
            'study_populations': self._get_all_populations(),
            'analytic_techniques': self._get_all_techniques()
        }
        return facets
    
    def _get_all_modalities(self) -> List[str]:
        """Extract all modality types"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT DISTINCT ?modality
        WHERE {
            ?measure meas:includesModality ?modality .
        }
        """
        results = []
        for row in self.querier.graph.query(query):
            modality = str(row.modality).split('#')[-1]
            results.append(modality)
        return sorted(results)
    
    def _get_all_levels(self) -> List[str]:
        """Extract all levels of analysis"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT DISTINCT ?level
        WHERE {
            ?measure meas:hasLevelOfAnalysis ?level .
        }
        """
        results = []
        for row in self.querier.graph.query(query):
            level = str(row.level).split('#')[-1]
            results.append(level)
        return sorted(results)
    
    def _get_all_populations(self) -> List[str]:
        """Extract all study populations"""
        query = """
        PREFIX evid: <http://example.org/ontology/evidence#>
        SELECT DISTINCT ?population
        WHERE {
            ?study evid:hasStudyPopulation ?population .
        }
        """
        results = []
        for row in self.querier.graph.query(query):
            results.append(str(row.population))
        return sorted(results)
    
    def _get_all_techniques(self) -> List[str]:
        """Extract all analytic techniques"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT DISTINCT ?technique
        WHERE {
            ?measure meas:usesAnalyticTechnique ?technique .
        }
        """
        results = []
        for row in self.querier.graph.query(query):
            technique = str(row.technique).split('#')[-1]
            results.append(technique)
        return sorted(results)
    
    def apply_filters(self, evidence: List[Dict], filters: SearchFilters) -> List[Dict]:
        """Apply filters to evidence results"""
        filtered = evidence
        
        # Filter by p-value
        if filters.p_value_threshold is not None:
            filtered = [e for e in filtered 
                       if e.get('pvalue') and e['pvalue'] <= filters.p_value_threshold]
        
        # Filter by effect size range
        if filters.effect_size_range is not None:
            min_val, max_val = filters.effect_size_range
            filtered = [e for e in filtered 
                       if e.get('value') and min_val <= e['value'] <= max_val]
        
        # Additional filtering logic for modalities, levels, etc.
        # This would require joining with measure properties
        
        return filtered