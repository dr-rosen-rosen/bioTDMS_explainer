# src/components/bottom_up_view.py
import streamlit as st
from typing import Dict, List, Optional
import pandas as pd

class BottomUpView:
    """Component for bottom-up pattern analysis"""
    
    def __init__(self, pattern_builder, similarity_engine, explanation_gen, querier):
        self.pattern_builder = pattern_builder
        self.similarity_engine = similarity_engine
        self.explanation_gen = explanation_gen
        self.querier = querier
    
    def render(self):
        """Render the bottom-up view interface"""
        st.header("🔄 Bottom-Up Pattern Analyzer")
        
        # Input method selection
        input_method = st.radio(
            "Pattern input method:",
            ["Visual Builder", "Text Description", "Import JSON"],
            horizontal=True
        )
        
        pattern = None
        
        if input_method == "Visual Builder":
            # Update pattern builder with fresh ontology data
            ontology_data = {
                'modalities': [m['local_name'] for m in self.querier.get_all_modalities()],
                'levels': ['individual', 'dyad', 'team', 'crossLevel'],
                'techniques': ['simpleAggregation', 'synchrony', 'networkAnalysis', 
                              'informationTheoretic', 'CRQA'],
                'constructs': [c['label'] for c in self.querier.get_all_constructs()]
            }
            
            # Update pattern builder data
            self.pattern_builder.modalities = ontology_data['modalities'] or ['physiology', 'communication', 'behavior', 'survey']
            self.pattern_builder.levels = ontology_data['levels']
            self.pattern_builder.techniques = ontology_data['techniques']
            self.pattern_builder.constructs = ontology_data['constructs']
            
            pattern = self.pattern_builder.render_pattern_builder()
        
        elif input_method == "Text Description":
            st.subheader("Describe Your Sensor Pattern")
            
            description = st.text_area(
                "Pattern description:",
                placeholder="e.g., 'Cross-correlation of heart rate variability between team members during high-stress phases'",
                height=100
            )
            
            if description:
                # Parse description into pattern
                pattern = self._parse_text_description(description)
                st.json(pattern)
        
        else:  # Import JSON
            json_input = st.text_area(
                "Paste pattern JSON:",
                height=200
            )
            
            if json_input:
                pattern = self.pattern_builder.import_pattern(json_input)
        
        # Analysis section
        if pattern and st.button("Analyze Pattern", type="primary"):
            self._analyze_pattern(pattern)
    
    def _analyze_pattern(self, pattern: Dict[str, any]):
        """Analyze the pattern and show results"""
        st.divider()
        st.subheader("🎯 Pattern Analysis Results")
        
        with st.spinner("Finding similar measures..."):
            # Find similar measures
            similar_measures = self.similarity_engine.find_similar_measures(pattern, top_k=5)
        
        if similar_measures:
            # Display results
            for rank, (measure_uri, score) in enumerate(similar_measures, 1):
                # Get measure details
                measure_info = self._get_measure_details(measure_uri)
                
                # Create expandable result card
                with st.expander(
                    f"#{rank} - {measure_info['name']} (Similarity: {score:.2%})",
                    expanded=(rank == 1)
                ):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Description:** {measure_info.get('description', 'N/A')}")
                        st.markdown(f"**Modality:** {measure_info.get('modality', 'N/A')}")
                        st.markdown(f"**Level:** {measure_info.get('level', 'N/A')}")
                        
                        if measure_info.get('construct'):
                            st.markdown(f"**Measures:** {measure_info['construct']}")
                    
                    with col2:
                        # Similarity breakdown
                        st.markdown("**Match Details:**")
                        breakdown = self._get_similarity_breakdown(pattern, measure_uri)
                        for aspect, match in breakdown.items():
                            if match:
                                st.success(f"✓ {aspect}")
                            else:
                                st.error(f"✗ {aspect}")
                    
                    # Generate explanation
                    if st.button(f"Generate Explanation", key=f"explain_{rank}"):
                        explanation = self.explanation_gen.generate_explanation(
                            pattern, measure_uri, score
                        )
                        st.info(explanation)
                    
                    # Show related evidence
                    if measure_info.get('construct'):
                        evidence = self.querier.query_evidence_for_construct(
                            measure_info['construct']
                        )
                        if evidence:
                            st.markdown("**Related Evidence:**")
                            evidence_df = pd.DataFrame(evidence)
                            st.dataframe(
                                evidence_df[['value', 'metric', 'pvalue']].head(),
                                use_container_width=True
                            )
        else:
            st.warning("No similar measures found in the ontology")
    
    def _parse_text_description(self, description: str) -> Dict[str, any]:
        """Parse text description into pattern structure"""
        # Simple keyword-based parsing
        pattern = {}
        
        # Detect modality
        if any(term in description.lower() for term in ['heart', 'cardiac', 'eeg', 'physiolog']):
            pattern['modality'] = 'physiology'
        elif any(term in description.lower() for term in ['commun', 'speech', 'dialog']):
            pattern['modality'] = 'communication'
        elif any(term in description.lower() for term in ['behav', 'movement', 'action']):
            pattern['modality'] = 'behavior'
        
        # Detect level
        if any(term in description.lower() for term in ['team', 'group']):
            pattern['level'] = 'team'
        elif any(term in description.lower() for term in ['between', 'dyad', 'pair']):
            pattern['level'] = 'dyad'
        elif any(term in description.lower() for term in ['individual', 'person']):
            pattern['level'] = 'individual'
        
        # Detect technique
        if any(term in description.lower() for term in ['correlat', 'synchron', 'align']):
            pattern['technique'] = 'synchrony'
        elif any(term in description.lower() for term in ['network', 'graph']):
            pattern['technique'] = 'networkAnalysis'
        elif any(term in description.lower() for term in ['entropy', 'information']):
            pattern['technique'] = 'informationTheoretic'
        
        pattern['description'] = description
        
        return pattern
    
    def _get_measure_details(self, measure_uri: str) -> Dict[str, str]:
        """Get detailed information about a measure"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        
        SELECT ?name ?description ?modality ?level ?construct
        WHERE {
            <%s> meas:hasName ?name .
            OPTIONAL { <%s> meas:hasDescription ?description }
            OPTIONAL { <%s> meas:includesModality ?modality }
            OPTIONAL { <%s> meas:hasLevelOfAnalysis ?level }
            OPTIONAL { <%s> meas:measuresConstruct ?construct }
        }
        """ % (measure_uri, measure_uri, measure_uri, measure_uri, measure_uri)
        
        for row in self.querier.graph.query(query):
            return {
                'name': str(row.name),
                'description': str(row.description) if row.description else None,
                'modality': str(row.modality).split('#')[-1] if row.modality else None,
                'level': str(row.level).split('#')[-1] if row.level else None,
                'construct': str(row.construct).split('#')[-1] if row.construct else None
            }
        return {}
    
    def _get_similarity_breakdown(self, pattern: Dict, measure_uri: str) -> Dict[str, bool]:
        """Get breakdown of similarity matches"""
        measure_props = self.similarity_engine._get_measure_properties(measure_uri)
        
        return {
            'Modality': pattern.get('modality') == measure_props.get('modality'),
            'Level': pattern.get('level') == measure_props.get('level'),
            'Technique': pattern.get('technique') == measure_props.get('technique')
        }