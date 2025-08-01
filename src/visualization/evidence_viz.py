# src/visualization/evidence_viz.py
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Any
from plotly.subplots import make_subplots

class EvidenceVisualizer:
    """Creates visualizations for evidence strength and effect sizes"""
    
    @staticmethod
    def create_forest_plot(evidence: List[Dict[str, Any]]) -> go.Figure:
        """Create a forest plot of effect sizes"""
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(evidence)
        
        # Filter for valid effect sizes
        df = df[df['value'].notna()]
        
        # Create forest plot
        fig = go.Figure()
        
        # Add effect sizes with confidence intervals
        for idx, row in df.iterrows():
            # Calculate CI if not provided
            if 'lower_ci' not in row or pd.isna(row.get('lower_ci')):
                # Approximate CI from p-value and effect size
                se = abs(row['value']) / 1.96 if row.get('pvalue', 1) < 0.05 else abs(row['value']) / 1.0
                lower_ci = row['value'] - 1.96 * se
                upper_ci = row['value'] + 1.96 * se
            else:
                lower_ci = row['lower_ci']
                upper_ci = row['upper_ci']
            
            # Add line for confidence interval
            fig.add_trace(go.Scatter(
                x=[lower_ci, upper_ci],
                y=[idx, idx],
                mode='lines',
                line=dict(color='black', width=2),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            # Add marker for effect size
            marker_color = 'red' if row.get('pvalue', 1) < 0.05 else 'blue'
            fig.add_trace(go.Scatter(
                x=[row['value']],
                y=[idx],
                mode='markers',
                marker=dict(size=10, color=marker_color),
                name=row.get('measure_name', f"Effect {idx}"),
                hovertemplate=(
                    f"Effect size: {row['value']:.3f}<br>"
                    f"p-value: {row.get('pvalue', 'N/A')}<br>"
                    f"Study: {row.get('study', 'Unknown').split('/')[-1]}"
                )
            ))
        
        # Add vertical line at 0
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        
        # Update layout
        fig.update_layout(
            title="Effect Sizes by Study",
            xaxis_title="Effect Size",
            yaxis_title="Study",
            showlegend=False,
            height=max(400, len(df) * 50)
        )
        
        return fig
    
    @staticmethod
    def create_evidence_summary(evidence: List[Dict[str, Any]]) -> go.Figure:
        """Create a summary visualization of evidence strength"""
        df = pd.DataFrame(evidence)
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Effect Size Distribution', 'P-value Distribution',
                          'Studies by Metric Type', 'Sample Sizes'),
            specs=[[{'type': 'histogram'}, {'type': 'histogram'}],
                   [{'type': 'bar'}, {'type': 'box'}]]
        )
        
        # Effect size distribution
        fig.add_trace(
            go.Histogram(x=df['value'], nbinsx=20, name='Effect Sizes'),
            row=1, col=1
        )
        
        # P-value distribution
        if 'pvalue' in df.columns:
            fig.add_trace(
                go.Histogram(x=df['pvalue'], nbinsx=20, name='P-values'),
                row=1, col=2
            )
        
        # Studies by metric type
        metric_counts = df['metric'].value_counts()
        fig.add_trace(
            go.Bar(x=metric_counts.index, y=metric_counts.values),
            row=2, col=1
        )
        
        # Sample sizes
        if 'team_sample_size' in df.columns:
            fig.add_trace(
                go.Box(y=df['team_sample_size'], name='Team Sample Sizes'),
                row=2, col=2
            )
        
        fig.update_layout(height=800, showlegend=False)
        return fig