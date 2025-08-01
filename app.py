# app.py - Main Streamlit Application
import streamlit as st
from pathlib import Path
import yaml
from src.ontology.loader import OntologyManager
from src.ontology.querier import SPARQLQuerier
from src.search.semantic_search import SemanticSearchEngine
from src.search.faceted_search import FacetedSearch
from src.search.similarity import PatternSimilarity
from src.visualization.network_viz import OntologyVisualizer
from src.visualization.evidence_viz import EvidenceVisualizer
from src.visualization.pattern_builder import PatternBuilder
from src.explanation.generator import ExplanationGenerator
from src.components.ontology_browser import OntologyBrowser
from src.components.top_down_view import TopDownView
from src.components.bottom_up_view import BottomUpView

# Page configuration
st.set_page_config(
    page_title="BioTDMS Explainer",
    page_icon=":cake:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #e0e2e6;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_ontology_graph():
    """Load the ontology graph with caching"""
    ontology_path = Path("data/ontologies")
    onto_manager = OntologyManager(ontology_path)
    return onto_manager.load_ontologies()

def initialize_components():
    """Initialize all application components"""
    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Load the cached graph
    graph = load_ontology_graph()
    
    # Initialize querier with the graph
    querier = SPARQLQuerier(graph)
    
    # Get ontology data for pattern builder
    ontology_data = {
        'modalities': [m['local_name'] for m in querier.get_all_modalities()],
        'levels': ['individual', 'dyad', 'team', 'crossLevel'],
        'techniques': ['simpleAggregation', 'synchrony', 'networkAnalysis', 
                      'informationTheoretic', 'CRQA'],
        'constructs': [c['label'] for c in querier.get_all_constructs()]
    }
    
    # Initialize search engines
    embedding_path = Path(config['data']['embedding_path'])
    semantic_search = SemanticSearchEngine(embedding_path)
    faceted_search = FacetedSearch(querier)
    similarity_engine = PatternSimilarity(graph, querier)
    
    # Initialize visualizers
    ontology_viz = OntologyVisualizer(graph, querier)
    evidence_viz = EvidenceVisualizer()
    pattern_builder = PatternBuilder(ontology_data)
    
    # Initialize explanation generator
    explanation_gen = ExplanationGenerator(graph, querier)
    
    # Create ontology manager for statistics
    onto_manager = OntologyManager(Path(config['data']['ontology_path']))
    onto_manager.graph = graph  # Use the already loaded graph
    
    return {
        'onto_manager': onto_manager,
        'querier': querier,
        'semantic_search': semantic_search,
        'faceted_search': faceted_search,
        'similarity_engine': similarity_engine,
        'ontology_viz': ontology_viz,
        'evidence_viz': evidence_viz,
        'pattern_builder': pattern_builder,
        'explanation_gen': explanation_gen
    }

def main():
    """Main application entry point"""
    # Title and description
    st.title(":cake: BioTDMS Explainer")
    st.markdown("""
    An system for understanding and explaining multi-modal sensor patterns 
    in team-based simulations using evidence from scientific literature.
    """)
    
    # Initialize components
    components = initialize_components()
    
    # Sidebar with statistics
    with st.sidebar:
        st.header("📊 Ontology Statistics")
        stats = components['onto_manager'].get_statistics()
        
        for key, value in stats.items():
            st.metric(key.replace('_', ' ').title(), value)
        
        st.divider()
        
        # Quick actions
        st.header("⚡ Quick Actions")
        if st.button("Regenerate Embeddings"):
            # Script to regenerate embeddings
            st.info("Regenerating embeddings...")
            # Call generate_embeddings.py script
        
        if st.button("Validate Ontology"):
            # Script to validate ontology
            st.info("Validating ontology...")
            # Call validate_ontology.py script
    
    # Main content area with tabs
    tab1, tab2, tab3 = st.tabs([
        "🔍 Browse Ontology", 
        "📊 Top-Down Analysis", 
        "🔄 Bottom-Up Analysis"
    ])
    
    with tab1:
        # Ontology Browser
        browser = OntologyBrowser(
            components['ontology_viz'],
            components['querier']
        )
        browser.render()
    
    with tab2:
        # Top-Down View
        top_down = TopDownView(
            components['querier'],
            components['semantic_search'],
            components['faceted_search'],
            components['evidence_viz']
        )
        top_down.render()
    
    with tab3:
        # Bottom-Up View
        bottom_up = BottomUpView(
            components['pattern_builder'],
            components['similarity_engine'],
            components['explanation_gen'],
            components['querier']
        )
        bottom_up.render()
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #888;'>
        BioTDMS Explainer v0.1 | 
        <a href='#' style='color: #888;'>Documentation</a> | 
        <a href='#' style='color: #888;'>Report Issue</a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()