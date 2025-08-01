# src/visualization/pattern_builder.py
import streamlit as st
from typing import Dict, List, Any, Optional
import json

class PatternBuilder:
    """Visual interface for building sensor patterns"""
    
    def __init__(self, ontology_data: Dict[str, List]):
        self.modalities = ontology_data.get('modalities', [])
        self.levels = ontology_data.get('levels', ['individual', 'dyad', 'team', 'crossLevel'])
        self.techniques = ontology_data.get('techniques', [])
        self.constructs = ontology_data.get('constructs', [])
    
    def render_pattern_builder(self) -> Dict[str, Any]:
        """Render the pattern building interface"""
        st.subheader("Visual Pattern Builder")
        
        pattern = {}
        
        # Check if we have data
        if not self.modalities:
            st.warning("No modalities found in ontology. Loading default values...")
            self.modalities = ['physiology', 'communication', 'behavior', 'survey', 'observation']
        
        if not self.techniques:
            self.techniques = ['simpleAggregation', 'synchrony', 'networkAnalysis', 
                             'informationTheoretic', 'CRQA']
        
        # Create columns for pattern components
        col1, col2 = st.columns(2)
        
        with col1:
            # Modality selection with visual hierarchy
            st.markdown("### 1. Select Modality")
            modality_tree = self._create_modality_tree()
            selected_modality = st.selectbox(
                "Primary modality:",
                options=self.modalities,
                format_func=lambda x: f"📊 {x}" if 'physiology' in x.lower() 
                                    else f"💬 {x}" if 'communication' in x.lower()
                                    else f"🎯 {x}" if 'behavior' in x.lower()
                                    else f"📋 {x}"
            )
            pattern['modality'] = selected_modality
            
            # Level of analysis
            st.markdown("### 2. Level of Analysis")
            level_icons = {
                'individual': '👤',
                'dyad': '👥',
                'team': '👥👥',
                'crossLevel': '🔄'
            }
            
            # Handle case where levels might be empty
            if self.levels:
                level_cols = st.columns(len(self.levels))
                for idx, level in enumerate(self.levels):
                    with level_cols[idx]:
                        icon = level_icons.get(level, '📍')
                        if st.button(f"{icon}\n{level}", key=f"level_{level}"):
                            pattern['level'] = level
            else:
                st.warning("No levels of analysis found in ontology")
            
            if 'level' in pattern:
                st.success(f"Selected: {pattern['level']}")
        
        with col2:
            # Analytic technique
            st.markdown("### 3. Analytic Technique")
            technique = st.selectbox(
                "Analysis method:",
                options=[''] + self.techniques,
                format_func=lambda x: 'Select...' if x == '' else x
            )
            if technique:
                pattern['technique'] = technique
            
            # Temporal characteristics
            st.markdown("### 4. Temporal Characteristics")
            temporal_options = {
                'static': 'Single time point',
                'dynamic': 'Time series',
                'synchrony': 'Temporal alignment',
                'lagged': 'Lagged relationships'
            }
            
            temporal = st.radio(
                "Temporal nature:",
                options=list(temporal_options.keys()),
                format_func=lambda x: temporal_options[x]
            )
            pattern['temporal'] = temporal
        
        # Advanced options in expander
        with st.expander("Advanced Pattern Options"):
            # Multi-modal patterns
            st.markdown("#### Multi-modal Pattern")
            additional_modalities = st.multiselect(
                "Additional modalities:",
                options=[m for m in self.modalities if m != selected_modality]
            )
            if additional_modalities:
                pattern['additional_modalities'] = additional_modalities
            
            # Custom constraints
            st.markdown("#### Custom Constraints")
            constraint_text = st.text_area(
                "Describe additional pattern constraints:",
                placeholder="e.g., 'High frequency sampling (>100Hz)', 'Requires baseline normalization'"
            )
            if constraint_text:
                pattern['constraints'] = constraint_text
        
        # Visual pattern summary
        if pattern:
            st.markdown("### Pattern Summary")
            self._render_pattern_summary(pattern)
        
        return pattern
    
    def _create_modality_tree(self) -> Dict[str, List[str]]:
        """Create hierarchical structure of modalities"""
        # This would be populated from the ontology
        return {
            'physiology': ['CNS', 'PNS', 'autonomic'],
            'communication': ['content', 'flow'],
            'behavior': ['physical', 'task', 'eye movement'],
            'survey': ['self-report', 'observer']
        }
    
    def _render_pattern_summary(self, pattern: Dict[str, Any]):
        """Render a visual summary of the built pattern"""
        summary_html = """
        <div style="border: 2px solid #4ECDC4; border-radius: 10px; padding: 15px; background-color: #f8f9fa;">
            <h4 style="color: #2c3e50; margin-top: 0;">Pattern Configuration</h4>
        """
        
        for key, value in pattern.items():
            if key == 'additional_modalities':
                value = ', '.join(value)
            summary_html += f"""
            <p style="margin: 5px 0;">
                <strong style="color: #34495e;">{key.replace('_', ' ').title()}:</strong> 
                <span style="color: #16a085;">{value}</span>
            </p>
            """
        
        summary_html += "</div>"
        st.markdown(summary_html, unsafe_allow_html=True)
    
    def export_pattern(self, pattern: Dict[str, Any]) -> str:
        """Export pattern as JSON"""
        return json.dumps(pattern, indent=2)
    
    def import_pattern(self, pattern_json: str) -> Dict[str, Any]:
        """Import pattern from JSON"""
        try:
            return json.loads(pattern_json)
        except json.JSONDecodeError:
            st.error("Invalid pattern JSON")
            return {}