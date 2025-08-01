# src/explanation/generator.py
from typing import Dict, List, Optional, Tuple
import networkx as nx
from rdflib import Literal

class ExplanationGenerator:
    """Generates natural language explanations for pattern-measure relationships"""
    
    def __init__(self, graph, querier):
        self.graph = graph
        self.querier = querier
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """Load explanation templates"""
        return {
            'high_similarity': (
                "This sensor pattern shows {score:.0%} similarity to '{measure_name}'. "
                "The pattern matches on {matching_aspects}, which are key characteristics "
                "of this measure. {construct_explanation} {evidence_summary}"
            ),
            'moderate_similarity': (
                "This pattern has {score:.0%} similarity with '{measure_name}'. "
                "While the pattern matches on {matching_aspects}, it differs in {differing_aspects}. "
                "{construct_explanation} {evidence_summary}"
            ),
            'construct_explanation': (
                "This measure is designed to capture {construct}, which reflects "
                "{construct_description}. "
            ),
            'evidence_summary': (
                "Previous studies have shown {effect_direction} effects "
                "(average effect size: {avg_effect:.3f}) across {n_studies} studies."
            ),
            'path_explanation': (
                "The connection between your pattern and {construct} follows this path: "
                "{path_description}"
            )
        }
    
    def generate_explanation(self, 
                           pattern: Dict[str, any], 
                           measure_uri: str,
                           similarity_score: float) -> str:
        """Generate explanation for pattern-measure relationship"""
        
        # Get measure details
        measure_info = self._get_measure_info(measure_uri)
        
        # Determine matching and differing aspects
        matches, differences = self._compare_pattern_measure(pattern, measure_info)
        
        # Select appropriate template
        if similarity_score > 0.8:
            template = self.templates['high_similarity']
        else:
            template = self.templates['moderate_similarity']
        
        # Build explanation components
        explanation_parts = {
            'score': similarity_score,
            'measure_name': measure_info['name'],
            'matching_aspects': self._format_list(matches),
            'differing_aspects': self._format_list(differences),
            'construct_explanation': '',
            'evidence_summary': ''
        }
        
        # Add construct explanation if available
        if measure_info.get('construct'):
            construct_desc = self._get_construct_description(measure_info['construct'])
            explanation_parts['construct_explanation'] = self.templates['construct_explanation'].format(
                construct=measure_info['construct'].split('#')[-1],
                construct_description=construct_desc
            )
        
        # Add evidence summary
        if measure_info.get('construct'):
            evidence = self.querier.query_evidence_for_construct(measure_info['construct'])
            if evidence:
                effect_summary = self._summarize_effects(evidence)
                explanation_parts['evidence_summary'] = self.templates['evidence_summary'].format(
                    **effect_summary
                )
        
        # Generate final explanation
        explanation = template.format(**explanation_parts)
        
        # Add path explanation if requested
        if pattern.get('show_reasoning_path'):
            path_exp = self._generate_path_explanation(pattern, measure_uri)
            explanation += f"\n\n{path_exp}"
        
        return explanation
    
    def _get_measure_info(self, measure_uri: str) -> Dict[str, any]:
        """Get comprehensive measure information"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?name ?description ?modality ?level ?technique ?construct ?scale ?interpretation
        WHERE {
            <%s> meas:hasName ?name .
            OPTIONAL { <%s> meas:hasDescription ?description }
            OPTIONAL { <%s> meas:includesModality ?modality }
            OPTIONAL { <%s> meas:hasLevelOfAnalysis ?level }
            OPTIONAL { <%s> meas:usesAnalyticTechnique ?technique }
            OPTIONAL { <%s> meas:measuresConstruct ?construct }
            OPTIONAL { <%s> meas:hasScale ?scale }
            OPTIONAL { <%s> meas:hasInterpretation ?interpretation }
        }
        """ % tuple([measure_uri] * 8)
        
        for row in self.querier.graph.query(query):
            return {
                'name': str(row.name),
                'description': str(row.description) if row.description else '',
                'modality': str(row.modality) if row.modality else None,
                'level': str(row.level) if row.level else None,
                'technique': str(row.technique) if row.technique else None,
                'construct': str(row.construct) if row.construct else None,
                'scale': str(row.scale) if row.scale else None,
                'interpretation': str(row.interpretation) if row.interpretation else None
            }
        return {}
    
    def _compare_pattern_measure(self, 
                               pattern: Dict[str, any], 
                               measure_info: Dict[str, any]) -> Tuple[List[str], List[str]]:
        """Compare pattern and measure to find matches and differences"""
        matches = []
        differences = []
        
        # Compare modality
        if pattern.get('modality'):
            measure_modality = measure_info.get('modality', '').split('#')[-1]
            if pattern['modality'] == measure_modality:
                matches.append('modality')
            else:
                differences.append('modality')
        
        # Compare level
        if pattern.get('level'):
            measure_level = measure_info.get('level', '').split('#')[-1]
            if pattern['level'] == measure_level:
                matches.append('level of analysis')
            else:
                differences.append('level of analysis')
        
        # Compare technique
        if pattern.get('technique'):
            measure_technique = measure_info.get('technique', '').split('#')[-1]
            if pattern['technique'] == measure_technique:
                matches.append('analytic technique')
            else:
                differences.append('analytic technique')
        
        return matches, differences
    
    def _format_list(self, items: List[str]) -> str:
        """Format a list for natural language"""
        if not items:
            return "no aspects"
        elif len(items) == 1:
            return items[0]
        elif len(items) == 2:
            return f"{items[0]} and {items[1]}"
        else:
            return ", ".join(items[:-1]) + f", and {items[-1]}"
    
    def _get_construct_description(self, construct_uri: str) -> str:
        """Get a description of a construct"""
        # Try to get from ontology
        query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?comment WHERE {
            <%s> rdfs:comment ?comment
        }
        """ % construct_uri
        
        for row in self.querier.graph.query(query):
            return str(row.comment)
        
        # Generate default description based on construct name
        construct_name = construct_uri.split('#')[-1]
        descriptions = {
            'teamPerformance': 'the overall effectiveness and efficiency of team task completion',
            'coordination': 'the synchronization and organization of team member actions',
            'communication': 'the exchange of information between team members',
            'cohesion': 'the degree of unity and connectedness within the team',
            'situationalAwareness': 'team members\' understanding of the current environment and task state',
            'sharedMentalModel': 'the common understanding of task goals and procedures among team members',
            'stress': 'psychological and physiological responses to demanding situations',
            'cognitiveLoad': 'the mental effort required to process information and complete tasks'
        }
        
        return descriptions.get(construct_name, 'team-related processes and outcomes')
    
    def _summarize_effects(self, evidence: List[Dict]) -> Dict[str, any]:
        """Summarize effect sizes from evidence"""
        if not evidence:
            return {
                'effect_direction': 'no reported',
                'avg_effect': 0,
                'n_studies': 0
            }
        
        effects = [e['value'] for e in evidence if e.get('value') is not None]
        avg_effect = sum(effects) / len(effects) if effects else 0
        
        # Determine direction
        if avg_effect > 0.2:
            direction = 'positive'
        elif avg_effect < -0.2:
            direction = 'negative'
        else:
            direction = 'small to negligible'
        
        # Count unique studies
        studies = set(e['study'] for e in evidence)
        
        return {
            'effect_direction': direction,
            'avg_effect': avg_effect,
            'n_studies': len(studies)
        }
    
    def _generate_path_explanation(self, pattern: Dict, measure_uri: str) -> str:
        """Generate explanation of reasoning path"""
        # Build a path from pattern characteristics to measure
        path_steps = []
        
        # Start with pattern modality
        if pattern.get('modality'):
            path_steps.append(f"Your {pattern['modality']} sensor data")
        
        # Add processing technique
        if pattern.get('technique'):
            path_steps.append(f"processed using {pattern['technique']}")
        
        # Add level of analysis
        if pattern.get('level'):
            path_steps.append(f"analyzed at the {pattern['level']} level")
        
        # Connect to measure
        measure_name = self._get_measure_info(measure_uri)['name']
        path_steps.append(f"corresponds to the '{measure_name}' measure")
        
        # Add construct connection if available
        measure_info = self._get_measure_info(measure_uri)
        if measure_info.get('construct'):
            construct_name = measure_info['construct'].split('#')[-1]
            path_steps.append(f"which captures {construct_name}")
        
        path_description = " → ".join(path_steps)
        
        return self.templates['path_explanation'].format(
            construct=construct_name if measure_info.get('construct') else 'team processes',
            path_description=path_description
        )