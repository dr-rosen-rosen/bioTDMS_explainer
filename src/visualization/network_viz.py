# src/visualization/network_viz.py
import streamlit as st
from pyvis.network import Network
import networkx as nx
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from rdflib import URIRef, Literal

class OntologyVisualizer:
    """Creates interactive visualizations of the ontology"""
    
    def __init__(self, graph, querier):
        self.graph = graph
        self.querier = querier
        print(f"OntologyVisualizer initialized with graph: {graph is not None}")
    
    def test_method(self):
        """Test method to verify the class is loaded correctly"""
        return "OntologyVisualizer is working!"
    
    def create_interactive_network(self, 
                                 focus_node: Optional[str] = None,
                                 depth: int = 2) -> Network:
        """Create an interactive network visualization"""
        print("=== create_interactive_network called ===")
        st.write("=== create_interactive_network called ===")
        
        net = Network(height="600px", width="100%", 
                     bgcolor="#ffffff", font_color="#000000")
        
        print("Network object created")
        st.write(f"Network object created: {net}")
        
        # Configure physics
        net.set_options("""
        {
            "physics": {
                "enabled": true,
                "stabilization": {
                    "enabled": true,
                    "iterations": 100
                },
                "barnesHut": {
                    "gravitationalConstant": -8000,
                    "springConstant": 0.001,
                    "springLength": 200
                }
            },
            "nodes": {
                "font": {
                    "size": 12
                }
            },
            "edges": {
                "smooth": {
                    "type": "continuous"
                }
            }
        }
        """)
        
        # Add nodes and edges
        if focus_node:
            self._add_neighborhood(net, focus_node, depth)
        else:
            self._add_full_ontology(net)
        return net
    
    def _add_full_ontology(self, net: Network):
        """Add all nodes and edges from the ontology"""
        node_colors = {
            'Construct': '#FF6B6B',
            'Measure': '#4ECDC4',
            'Study': '#45B7D1',
            'Modality': '#96CEB4',
            'Method': '#DDA0DD'
        }
        
        # Add all nodes
        added_nodes = set()
        skipped_count = 0
        total_count = 0
        
        for s, p, o in self.graph:
            total_count += 1
            
            # Skip system ontology triples
            skip_patterns = ['owl#', 'rdf-syntax', 'XMLSchema', '22-rdf-syntax']
            
            if any(skip in str(s) for skip in skip_patterns):
                skipped_count += 1
                continue
            if any(skip in str(p) for skip in skip_patterns):
                skipped_count += 1
                continue
            if not isinstance(o, Literal) and any(skip in str(o) for skip in skip_patterns):
                skipped_count += 1
                continue
            
            # Add subject node
            s_str = str(s)
            if s_str not in added_nodes:
                node_type = self._get_node_type(s_str)
                color = node_colors.get(node_type, '#CCCCCC')
                label = s_str.split('#')[-1] if '#' in s_str else s_str.split('/')[-1]
                net.add_node(s_str, label=label, color=color, 
                           title=f"{node_type}: {label}")
                added_nodes.add(s_str)
            
            # Add object node if not a literal
            if not isinstance(o, Literal):
                o_str = str(o)
                if o_str not in added_nodes:
                    node_type = self._get_node_type(o_str)
                    color = node_colors.get(node_type, '#CCCCCC')
                    label = o_str.split('#')[-1] if '#' in o_str else o_str.split('/')[-1]
                    net.add_node(o_str, label=label, color=color,
                               title=f"{node_type}: {label}")
                    added_nodes.add(o_str)
                
                # Add edge
                edge_label = str(p).split('#')[-1] if '#' in str(p) else str(p).split('/')[-1]
                net.add_edge(s_str, o_str, title=edge_label)
        
        print(f"Processed {total_count} triples, skipped {skipped_count}, added {len(added_nodes)} nodes")
        st.info(f"Processed {total_count} triples, skipped {skipped_count}, added {len(added_nodes)} nodes")
    
    def _add_neighborhood(self, net: Network, focus: str, depth: int):
        """Add nodes within a certain depth from focus node"""
        visited = set()
        to_visit = [(focus, 0)]
        
        node_colors = {
            'Construct': '#FF6B6B',
            'Measure': '#4ECDC4',
            'Study': '#45B7D1',
            'Modality': '#96CEB4',
            'Method': '#DDA0DD'
        }
        
        # Track which nodes have been added to the network
        added_nodes = set()
        
        while to_visit:
            current, current_depth = to_visit.pop(0)
            if current in visited or current_depth > depth:
                continue
            
            visited.add(current)
            
            # Skip certain system nodes
            if any(skip in str(current) for skip in ['owl#', 'rdf-syntax', 'XMLSchema']):
                continue
            
            # Determine node type and color
            node_type = self._get_node_type(current)
            color = node_colors.get(node_type, '#CCCCCC')
            
            # Add node if not already added
            if current not in added_nodes:
                label = current.split('#')[-1] if '#' in current else current.split('/')[-1]
                net.add_node(current, label=label, color=color, 
                            title=f"{node_type}: {label}")
                added_nodes.add(current)
            
            # Add connected nodes
            if current_depth < depth:
                # Outgoing edges
                for _, p, o in self.graph.triples((URIRef(current), None, None)):
                    if not isinstance(o, Literal):
                        o_str = str(o)
                        # Skip system ontology nodes
                        if any(skip in o_str for skip in ['owl#', 'rdf-syntax', 'XMLSchema']):
                            continue
                        
                        to_visit.append((o_str, current_depth + 1))
                        
                        # Add object node if not already added
                        if o_str not in added_nodes:
                            o_label = o_str.split('#')[-1] if '#' in o_str else o_str.split('/')[-1]
                            o_type = self._get_node_type(o_str)
                            o_color = node_colors.get(o_type, '#CCCCCC')
                            net.add_node(o_str, label=o_label, color=o_color,
                                       title=f"{o_type}: {o_label}")
                            added_nodes.add(o_str)
                        
                        # Add edge
                        edge_label = str(p).split('#')[-1] if '#' in str(p) else str(p).split('/')[-1]
                        net.add_edge(current, o_str, title=edge_label)
                
                # Incoming edges
                for s, p, _ in self.graph.triples((None, None, URIRef(current))):
                    s_str = str(s)
                    # Skip system ontology nodes
                    if any(skip in s_str for skip in ['owl#', 'rdf-syntax', 'XMLSchema']):
                        continue
                        
                    to_visit.append((s_str, current_depth + 1))
                    
                    # Add subject node if not already added
                    if s_str not in added_nodes:
                        s_label = s_str.split('#')[-1] if '#' in s_str else s_str.split('/')[-1]
                        s_type = self._get_node_type(s_str)
                        s_color = node_colors.get(s_type, '#CCCCCC')
                        net.add_node(s_str, label=s_label, color=s_color,
                                   title=f"{s_type}: {s_label}")
                        added_nodes.add(s_str)
                    
                    # Add edge
                    edge_label = str(p).split('#')[-1] if '#' in str(p) else str(p).split('/')[-1]
                    net.add_edge(s_str, current, title=edge_label)
    
    def _get_node_type(self, uri: str) -> str:
        """Determine the type of a node"""
        # Quick check based on namespace
        if 'teamMeasurement#' in uri:
            if any(t in uri for t in ['Construct', 'Modality', 'Method', 'Measure']):
                return uri.split('#')[-1].replace('meas:', '')
        elif 'evidence#' in uri:
            if any(t in uri for t in ['Study', 'EffectSize', 'Publication']):
                return uri.split('#')[-1].replace('evid:', '')
        elif 'instances#' in uri:
            # Instance nodes - check their type
            type_query = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?type WHERE { <%s> rdf:type ?type }
            """ % uri
            
            for row in self.graph.query(type_query):
                type_uri = str(row.type)
                if '#' in type_uri:
                    type_name = type_uri.split('#')[-1]
                    if type_name in ['Measure', 'Study', 'Publication', 'EffectSize']:
                        return type_name
        
        # Fallback type detection
        type_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?type WHERE { 
            { <%s> rdf:type ?type } 
            UNION 
            { <%s> rdfs:subClassOf ?type }
        }
        """ % (uri, uri)
        
        for row in self.graph.query(type_query):
            type_uri = str(row.type)
            if '#' in type_uri and not any(skip in type_uri for skip in ['owl#', 'rdf-syntax']):
                return type_uri.split('#')[-1]
        
        # Default based on URI pattern
        if '#' in uri:
            local_name = uri.split('#')[-1]
            if local_name.startswith('meas_'):
                return 'Measure'
            elif local_name.startswith('effect_'):
                return 'EffectSize'
            elif local_name.startswith('study_'):
                return 'Study'
            elif local_name.startswith('pub_'):
                return 'Publication'
        
        return "Unknown"
