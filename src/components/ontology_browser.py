# src/components/ontology_browser.py
import streamlit as st
from typing import Dict, List, Optional
import pandas as pd
from pyvis.network import Network
import tempfile

class OntologyBrowser:
    """Component for browsing and visualizing the ontology"""
    
    def __init__(self, ontology_viz, querier):
        self.ontology_viz = ontology_viz
        self.querier = querier
    
    def render(self):
        """Render the ontology browser interface"""
        st.header("🌐 Ontology Browser")

        # Sidebar details (always available, regardless of view)
        self._render_sidebar_node_details()
        
        # View selection
        view_type = st.radio(
            "Select view:",
            ["Interactive Network", "Hierarchical Tree", "Statistics"],
            horizontal=True
        )
        
        if view_type == "Interactive Network":
            self._render_network_view()
        elif view_type == "Hierarchical Tree":
            self._render_tree_view()
        else:
            self._render_statistics_view()
    
    def _render_network_view(self):
            """Render interactive network visualization"""
            container = st.container()
            with container:
                try:
                    # Put controls in an expander at the top
                    with st.expander("⚙️ Network Options", expanded=False):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            # Focus node selection
                            constructs = self.querier.get_all_constructs()
                            focus_options = ["Full Ontology"] + [c['label'] for c in constructs]
                            
                            selected_focus = st.selectbox(
                                "Focus on:",
                                options=focus_options
                            )
                        
                        with col2:
                            depth = st.slider(
                                "Neighborhood depth:",
                                min_value=1,
                                max_value=4,
                                value=2,
                                disabled=(selected_focus == "Full Ontology")
                            )
                        
                        with col3:
                            # Visualization options
                            show_labels = st.checkbox("Show labels", value=True)
                            physics_enabled = st.checkbox("Enable physics", value=True)
                        
                        with col4:
                            # Debug info
                            if st.checkbox("Show debug info"):
                                st.write(f"Graph has {len(self.querier.graph)} triples")
                                st.write(f"Ontology viz graph: {self.ontology_viz.graph is not None}")
                    
                    # Now render the network using full width
                    try:
                        # Create network
                        net = None
                        if selected_focus == "Full Ontology":
                            net = self.ontology_viz.create_interactive_network()
                            if st.session_state.get('debug_mode', False):
                                st.write(f"Network returned: {net is not None}")
                                st.write(f"Network type: {type(net)}")
                        else:
                            # Find URI for selected construct
                            focus_uri = next(
                                (c['uri'] for c in constructs if c['label'] == selected_focus),
                                None
                            )
                            if focus_uri:
                                net = self.ontology_viz.create_interactive_network(
                                    focus_node=focus_uri,
                                    depth=depth
                                )
                            else:
                                st.warning("Could not find URI for selected construct")
                        
                        # Save and display
                        if net is not None:
                            # Apply visualization settings
                            if not show_labels:
                                for node in net.nodes:
                                    node['label'] = ''
                            
                            if not physics_enabled:
                                net.set_options("""
                                {
                                    "physics": {
                                        "enabled": false
                                    }
                                }
                                """)
                            
                            try:
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as tmp:
                                    net.save_graph(tmp.name)
                                    
                                    with open(tmp.name, 'r') as f:
                                        html_content = f.read()
                                    
                                    # Display with full width and increased height
                                    # st.components.v1.html(html_content, height=800, scrolling=True)
                                    # Inject CSS to force full width
                                    html_content = html_content.replace(
                                        '<style>',
                                        '''<style>
                                        #mynetworkId {
                                            width: 100% !important;
                                            position: relative !important;
                                        }
                                        .card {
                                            width: 100% !important;
                                        }
                                        body {
                                            margin: 0;
                                            padding: 0;
                                            width: 100%;
                                        }
                                        '''
                                    )

                                    # Also update the container div to use full viewport width
                                    html_content = html_content.replace(
                                        'width: 100%',
                                        'width: 100vw'
                                    )

                                    # Display with full container width
                                    st.components.v1.html(
                                        html_content, 
                                        height=800, 
                                        width=800,
                                        scrolling=True
                                    )
                                    
                            except Exception as e:
                                st.error(f"Error during save/display: {type(e).__name__}: {str(e)}")
                                if st.session_state.get('debug_mode', False):
                                    import traceback
                                    st.code(traceback.format_exc())
                        else:
                            st.error("Failed to create network visualization.")
                            
                            # Try a simple test
                            if st.button("Test Simple Network"):
                                test_net = Network(height="400px", width="100%")
                                test_net.add_node("1", label="Test Node 1", color="#FF6B6B")
                                test_net.add_node("2", label="Test Node 2", color="#4ECDC4")
                                test_net.add_edge("1", "2", title="Test Edge")
                                
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as tmp:
                                    test_net.save_graph(tmp.name)
                                    with open(tmp.name, 'r') as f:
                                        html_content = f.read()
                                    st.components.v1.html(html_content, height=400)
                                    
                    except Exception as e:
                        st.error(f"Error creating visualization: {type(e).__name__}: {str(e)}")
                        if st.session_state.get('debug_mode', False):
                            import traceback
                            st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"Error creating network container: {type(e).__name__}: {str(e)}")

    def _render_sidebar_node_details(self):
        """Render sidebar panel showing details for a selected node"""
        st.sidebar.header("🔎 Node Details")

        focus_node = st.sidebar.text_input("Enter node URI or short name:")

        if focus_node:
            match = None
            for node in self.ontology_viz.graph.all_nodes():
                node_str = str(node)
                if focus_node in node_str or node_str.endswith(focus_node):
                    match = node_str
                    break

            if match:
                node_type = self.ontology_viz._get_node_type(match)
                annotations = self.ontology_viz._get_annotations(match)

                st.sidebar.markdown(f"**Type:** {node_type}")
                st.sidebar.markdown(f"**URI:** {match}")

                if annotations:
                    st.sidebar.subheader("Annotations")
                    for k, v in annotations.items():
                        st.sidebar.markdown(f"- **{k}:** {v}")
                else:
                    st.sidebar.info("No annotations found for this node.")
            else:
                st.sidebar.warning("No matching node found in ontology.")

    def _render_tree_view(self):
        """Render hierarchical tree view"""
        st.subheader("Hierarchical View")
        
        # Get all classes and their relationships
        tree_data = self._build_tree_structure()
        
        if not tree_data:
            st.warning("No hierarchical data found in ontology")
            return
        
        # Display the tree
        for top_level_name, top_level_data in tree_data.items():
            with st.expander(f"📁 {top_level_name}", expanded=True):
                if top_level_data.get('children'):
                    self._render_tree_children(top_level_data['children'], level=1)
                else:
                    st.write("*No subclasses found*")
                
                # Show instance count
                total_instances = self._count_instances(top_level_data)
                st.caption(f"Total instances: {total_instances}")

    def _render_tree_children(self, children: Dict, level: int = 0):
        """Recursively render tree children"""
        indent = "&nbsp;" * (level * 4)
        
        for child_name, child_data in children.items():
            # Create the node display
            if child_data.get('instances'):
                # Has instances - show count
                st.markdown(f"{indent}├─ **{child_name}** ({len(child_data['instances'])} instances)")
                
                # Show instances in a collapsible section
                with st.expander(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;Show instances", expanded=False):
                    for instance in child_data['instances']:
                        st.markdown(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {instance['name']}")
            else:
                # No instances
                st.markdown(f"{indent}├─ **{child_name}**")
            
            # Recursively render children
            if child_data.get('children'):
                self._render_tree_children(child_data['children'], level + 1)

    def _count_instances(self, node: Dict) -> int:
        """Count total instances in a tree node and its children"""
        count = len(node.get('instances', []))
        
        if 'children' in node:
            for child in node['children'].values():
                count += self._count_instances(child)
        
        return count
    
    def _render_tree_node(self, node_data: Dict, level: int = 0):
        """Recursively render tree nodes"""
        indent = "  " * level
        for name, data in node_data.items():
            if isinstance(data, dict):
                # Display the node name
                st.markdown(f"{indent}↳ **{name}**")
                
                # Display instances if any
                if 'instances' in data and data['instances']:
                    for instance in data['instances']:
                        st.markdown(f"{indent}    • {instance['name']}")
                
                # Display children if any
                if 'children' in data and data['children']:
                    self._render_tree_node(data['children'], level + 1)
    
    def _render_statistics_view(self):
        """Render detailed statistics"""
        st.subheader("Ontology Statistics")
        
        # Get detailed statistics
        stats = self._get_detailed_statistics()
        
        # Display in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Classes", stats['total_classes'])
            st.metric("Total Properties", stats['total_properties'])
        
        with col2:
            st.metric("Total Instances", stats['total_instances'])
            st.metric("Total Triples", stats['total_triples'])
        
        with col3:
            st.metric("Studies", stats['studies'])
            st.metric("Effect Sizes", stats['effects'])
        
        # Show distributions
        st.divider()
        
        # Modality distribution
        modality_dist = self._get_modality_distribution()
        if modality_dist:
            st.subheader("Measure Distribution by Modality")
            df = pd.DataFrame(
                list(modality_dist.items()),
                columns=['Modality', 'Count']
            )
            st.bar_chart(df.set_index('Modality'))
    
    def _build_tree_structure(self) -> Dict:
        """Build hierarchical tree structure from ontology"""
        tree = {}
        
        # First, let's get the top-level classes we care about
        top_level_classes = ['Construct', 'Modality', 'Method']
        
        for class_name in top_level_classes:
            # Find the URI for this class
            class_query = """
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT DISTINCT ?class
            WHERE {
                ?class a owl:Class .
                FILTER(STRENDS(STR(?class), "#%s"))
            }
            """ % class_name
            
            results = list(self.querier.graph.query(class_query))
            if results:
                class_uri = str(results[0]['class'])
                tree[class_name] = {
                    'children': {},
                    'uri': class_uri,
                    'instances': []
                }
                
                # Now get all direct subclasses
                subclass_query = """
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                
                SELECT DISTINCT ?subclass ?label
                WHERE {
                    ?subclass rdfs:subClassOf <%s> .
                    ?subclass a owl:Class .
                    OPTIONAL { ?subclass rdfs:label ?label }
                }
                """ % class_uri
                
                subclass_results = list(self.querier.graph.query(subclass_query))
                
                # Debug: show what we found
                if st.checkbox(f"Debug: Show subclasses of {class_name}"):
                    st.write(f"Found {len(subclass_results)} subclasses")
                    for r in subclass_results:
                        st.write(f"- {r.subclass}")
                
                for sub_row in subclass_results:
                    subclass_uri = str(sub_row.subclass)
                    subclass_name = str(sub_row.label) if sub_row.label else subclass_uri.split('#')[-1]
                    
                    tree[class_name]['children'][subclass_name] = {
                        'uri': subclass_uri,
                        'children': {},
                        'instances': []
                    }
                    
                    # Get instances for this subclass
                    instance_query = """
                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT DISTINCT ?instance ?label
                    WHERE {
                        ?instance rdf:type <%s> .
                        OPTIONAL { ?instance rdfs:label ?label }
                    }
                    """ % subclass_uri
                    
                    instances = []
                    for inst_row in self.querier.graph.query(instance_query):
                        instance_uri = str(inst_row.instance)
                        instance_name = str(inst_row.label) if inst_row.label else instance_uri.split('#')[-1]
                        instances.append({
                            'uri': instance_uri,
                            'name': instance_name
                        })
                    
                    tree[class_name]['children'][subclass_name]['instances'] = instances
                    
                    # Recursively add sub-subclasses
                    self._add_subclasses_to_tree(
                        tree[class_name]['children'][subclass_name], 
                        subclass_uri
                    )
        
        # Debug: show the tree structure
        if st.checkbox("Debug: Show tree structure"):
            st.json(tree)
        
        return tree

    def _add_subclasses_to_tree(self, parent_node: Dict, parent_uri: str):
        """Recursively add subclasses to tree"""
        subclass_query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT DISTINCT ?subclass ?label
        WHERE {
            ?subclass rdfs:subClassOf <%s> .
            ?subclass a owl:Class .
            OPTIONAL { ?subclass rdfs:label ?label }
        }
        """ % parent_uri
        
        for row in self.querier.graph.query(subclass_query):
            subclass_uri = str(row.subclass)
            subclass_name = str(row.label) if row.label else subclass_uri.split('#')[-1]
            
            if subclass_name not in parent_node['children']:  # Avoid duplicates
                parent_node['children'][subclass_name] = {
                    'uri': subclass_uri,
                    'children': {},
                    'instances': []
                }
                
                # Get instances
                instance_query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT DISTINCT ?instance ?label
                WHERE {
                    ?instance rdf:type <%s> .
                    OPTIONAL { ?instance rdfs:label ?label }
                }
                """ % subclass_uri
                
                instances = []
                for inst_row in self.querier.graph.query(instance_query):
                    instance_uri = str(inst_row.instance)
                    instance_name = str(inst_row.label) if inst_row.label else instance_uri.split('#')[-1]
                    instances.append({
                        'uri': instance_uri,
                        'name': instance_name
                    })
                
                parent_node['children'][subclass_name]['instances'] = instances
                
                # Recurse
                self._add_subclasses_to_tree(
                    parent_node['children'][subclass_name], 
                    subclass_uri
                )
    
    def _get_detailed_statistics(self) -> Dict[str, int]:
        """Get detailed statistics from ontology"""
        # Get basic counts using simpler queries
        stats = {}
        
        # Count classes
        class_query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?class) as ?count)
        WHERE { ?class a owl:Class }
        """
        for row in self.querier.graph.query(class_query):
            stats['total_classes'] = int(row[0]) if row[0] else 0
        
        # Count properties
        prop_query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?prop) as ?count)
        WHERE { 
            { ?prop a owl:ObjectProperty } 
            UNION 
            { ?prop a owl:DatatypeProperty }
        }
        """
        for row in self.querier.graph.query(prop_query):
            stats['total_properties'] = int(row[0]) if row[0] else 0
        
        # Count measures
        measure_query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        SELECT (COUNT(DISTINCT ?measure) as ?count)
        WHERE { ?measure a meas:Measure }
        """
        for row in self.querier.graph.query(measure_query):
            stats['total_instances'] = int(row[0]) if row[0] else 0
        
        # Count studies
        study_query = """
        PREFIX evid: <http://example.org/ontology/evidence#>
        SELECT (COUNT(DISTINCT ?study) as ?count)
        WHERE { ?study a evid:primaryStudy }            #SEARCH IN PRIMARY STUDIES
        """
        for row in self.querier.graph.query(study_query):
            stats['studies'] = int(row[0]) if row[0] else 0
        
        # Count effects
        effect_query = """
        PREFIX evid: <http://example.org/ontology/evidence#>
        SELECT (COUNT(DISTINCT ?effect) as ?count)
        WHERE { ?effect a evid:EffectSize }
        """
        for row in self.querier.graph.query(effect_query):
            stats['effects'] = int(row[0]) if row[0] else 0
        
        # Total triples
        stats['total_triples'] = len(self.querier.graph)
        
        return stats
    
    def _get_modality_distribution(self) -> Dict[str, int]:
        """Get distribution of measures by modality"""
        query = """
        PREFIX meas: <http://example.org/ontology/teamMeasurement#>
        
        SELECT ?modality (COUNT(?measure) as ?count)
        WHERE {
            ?measure a meas:Measure .
            ?measure meas:includesModality ?modality .
        }
        GROUP BY ?modality
        """
        
        distribution = {}
        for row in self.querier.graph.query(query):
            modality = str(row.modality).split('#')[-1]
            # Access the count value properly
            count_value = row[1]  # Second element in the row tuple
            distribution[modality] = int(count_value)
        
        return distribution
    
    def _debug_ontology_structure(self):
        """Debug method to explore what's actually in the ontology"""
        st.write("### Debugging Ontology Structure")
        
        # 1. Check what classes exist
        st.write("#### All Classes in Ontology:")
        class_query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?class ?label
        WHERE {
            ?class a owl:Class .
            OPTIONAL { ?class rdfs:label ?label }
        }
        LIMIT 20
        """
        
        classes = []
        for row in self.querier.graph.query(class_query):
            class_uri = str(row['class'])
            label = str(row.label) if row.label else class_uri.split('#')[-1]
            classes.append({'uri': class_uri, 'label': label})
        
        st.write(pd.DataFrame(classes))
        
        # 2. Check for Construct-related classes
        st.write("#### Classes with 'Construct' in name:")
        construct_query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?class ?label
        WHERE {
            ?class a owl:Class .
            OPTIONAL { ?class rdfs:label ?label }
            FILTER(CONTAINS(STR(?class), "Construct"))
        }
        """
        
        construct_classes = []
        for row in self.querier.graph.query(construct_query):
            class_uri = str(row['class'])
            label = str(row.label) if row.label else class_uri.split('#')[-1]
            construct_classes.append({'uri': class_uri, 'label': label})
        
        st.write(pd.DataFrame(construct_classes))
        
        # 3. Check subclass relationships
        st.write("#### Subclass Relationships:")
        subclass_query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT DISTINCT ?parent ?child
        WHERE {
            ?child rdfs:subClassOf ?parent .
            ?child a owl:Class .
            ?parent a owl:Class .
        }
        LIMIT 20
        """
        
        relationships = []
        for row in self.querier.graph.query(subclass_query):
            parent = str(row.parent).split('#')[-1]
            child = str(row.child).split('#')[-1]
            relationships.append({'parent': parent, 'child': child})
        
        st.write(pd.DataFrame(relationships))