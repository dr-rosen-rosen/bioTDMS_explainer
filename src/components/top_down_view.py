# src/components/top_down_view.py
import streamlit as st
from typing import Dict, List, Optional
import pandas as pd

class TopDownView:
    """Component for top-down exploration of constructs"""
    
    def __init__(self, querier, semantic_search, faceted_search, evidence_viz):
        self.querier = querier
        self.semantic_search = semantic_search
        self.faceted_search = faceted_search
        self.evidence_viz = evidence_viz
    
    def render(self):
        """Render the top-down view interface"""
        st.header("🔍 Top-Down Construct Explorer")
        
        # Search method selection
        search_method = st.radio(
            "Search method:",
            ["Browse Constructs", "Semantic Search"],
            horizontal=True
        )
        
        selected_construct = None
        
        if search_method == "Browse Constructs":
            # Hierarchical construct browser
            constructs = self.querier.get_all_constructs()
            
            # Group constructs by category
            construct_groups = self._group_constructs(constructs)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Construct Categories")
                category = st.selectbox(
                    "Select category:",
                    options=list(construct_groups.keys())
                )
                
                if category:
                    construct_options = construct_groups[category]
                    selected = st.selectbox(
                        "Select construct:",
                        options=construct_options,
                        format_func=lambda x: x['label']
                    )
                    if selected:
                        selected_construct = selected['uri']
            
            with col2:
                if selected_construct:
                    self._display_construct_info(selected_construct)
        
        else:  # Semantic Search
            query = st.text_input(
                "Search for constructs:",
                placeholder="e.g., 'team coordination under stress'"
            )
            
            if query:
                with st.spinner("Searching..."):
                    results = self.semantic_search.search(query, top_k=5)
                
                if results:
                    st.subheader("Search Results")
                    for item, score in results:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            if st.button(
                                f"📌 {item['label']}", 
                                key=f"select_{item['uri']}"
                            ):
                                selected_construct = item['uri']
                        with col2:
                            st.metric("Relevance", f"{score:.2%}")
        
        # Evidence exploration section
        if selected_construct:
            st.divider()
            self._explore_evidence(selected_construct)
    
    def _explore_evidence(self, construct_uri: str):
        """Explore evidence for selected construct"""
        st.subheader("📊 Evidence Analysis")
        
        # Faceted filters
        with st.expander("🔧 Filter Evidence", expanded=True):
            filters = self._render_filters()
        
        # Get evidence
        evidence = self.querier.query_evidence_for_construct(construct_uri)
        
        if evidence:
            # Apply filters
            filtered_evidence = self.faceted_search.apply_filters(evidence, filters)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Studies", len(set(e['study'] for e in filtered_evidence)))
            with col2:
                st.metric("Effect Sizes", len(filtered_evidence))
            with col3:
                avg_effect = sum(e['value'] for e in filtered_evidence) / len(filtered_evidence)
                st.metric("Avg Effect", f"{avg_effect:.3f}")
            with col4:
                sig_effects = sum(1 for e in filtered_evidence if e.get('pvalue', 1) < 0.05)
                st.metric("Significant", sig_effects)
            
            # Visualizations
            tab1, tab2, tab3 = st.tabs(["Forest Plot", "Summary Stats", "Data Table"])
            
            with tab1:
                fig = self.evidence_viz.create_forest_plot(filtered_evidence)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                fig = self.evidence_viz.create_evidence_summary(filtered_evidence)
                st.plotly_chart(fig, use_container_width=True)
            
            with tab3:
                df = pd.DataFrame(filtered_evidence)
                st.dataframe(
                    df[['measure_name', 'value', 'metric', 'pvalue', 'study']],
                    use_container_width=True
                )
        else:
            st.info("No evidence found for this construct")
    
    def _render_filters(self):
        """Render faceted filter controls"""
        from src.search.faceted_search import SearchFilters
        
        filters = SearchFilters()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # P-value threshold
            use_pvalue = st.checkbox("Filter by significance")
            if use_pvalue:
                filters.p_value_threshold = st.slider(
                    "P-value threshold:",
                    min_value=0.001,
                    max_value=0.1,
                    value=0.05,
                    step=0.001
                )
        
        with col2:
            # Effect size range
            use_effect_range = st.checkbox("Filter by effect size")
            if use_effect_range:
                filters.effect_size_range = st.slider(
                    "Effect size range:",
                    min_value=-2.0,
                    max_value=2.0,
                    value=(-1.0, 1.0),
                    step=0.1
                )
        
        with col3:
            # Study population
            populations = self.faceted_search._get_all_populations()
            selected_pops = st.multiselect(
                "Study populations:",
                options=populations
            )
            if selected_pops:
                filters.study_populations = selected_pops
        
        return filters
    
    def _group_constructs(self, constructs: List[Dict]) -> Dict[str, List[Dict]]:
        """Group constructs into categories"""
        # Simple grouping logic - could be enhanced with ontology structure
        groups = {
            'Cognitive': [],
            'Social': [],
            'Performance': [],
            'Communication': [],
            'Other': []
        }
        
        for construct in constructs:
            label = construct['label'].lower()
            if any(term in label for term in ['cognit', 'mental', 'aware']):
                groups['Cognitive'].append(construct)
            elif any(term in label for term in ['cohes', 'conflict', 'coordin']):
                groups['Social'].append(construct)
            elif any(term in label for term in ['perform', 'effect']):
                groups['Performance'].append(construct)
            elif any(term in label for term in ['commun']):
                groups['Communication'].append(construct)
            else:
                groups['Other'].append(construct)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    def _display_construct_info(self, construct_uri: str):
        """Display information about a construct"""
        # Get construct details from ontology
        st.markdown(f"**URI:** `{construct_uri}`")
        
        # Get related measures
        measures_query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT ?measure ?name ?description
        WHERE {
            ?measure meas:measuresConstruct <%s> .
            ?measure meas:hasName ?name .
            OPTIONAL { ?measure meas:hasDescription ?description }
        }
        """ % construct_uri
        
        measures = list(self.querier.graph.query(measures_query))
        if measures:
            st.markdown("**Related Measures:**")
            for measure in measures:
                st.markdown(f"- {measure.name}")
