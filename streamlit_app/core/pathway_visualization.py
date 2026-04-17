"""
Advanced Pathway Visualization Module
KEGG-style metabolic network visualization with animations

Author: Jorgelindo da Veiga
Date: 2025-11-22
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import networkx as nx
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from pathway_registry import build_canonical_pathway_registry


@dataclass
class PathwayNode:
    """Metabolite node in pathway"""
    name: str
    x: float
    y: float
    compartment: str = "cytosol"
    color: str = "#3498db"


@dataclass
class PathwayEdge:
    """Reaction edge in pathway"""
    source: str
    target: str
    enzyme: str
    reversible: bool = False
    color: str = "#95a5a6"


class MetabolicNetworkVisualizer:
    """
    Create interactive metabolic network visualizations
    KEGG-style pathway maps with temporal dynamics
    """
    
    def __init__(self):
        """Initialize visualizer"""
        self.graph = nx.DiGraph()
        self.node_positions = {}
        self.metabolite_colors = {}
        
        # Color schemes
        self.pathway_colors = {
            'glycolysis': '#e74c3c',
            'ppp': '#9b59b6',
            'rapoport_luebering': '#f39c12',
            'nucleotide': '#1abc9c',
            'amino_acid': '#34495e'
        }
        
    def define_rbc_pathway_layout(self) -> Dict[str, Tuple[float, float]]:
        """
        Define manual layout for RBC metabolic pathways
        Mimics KEGG-style positioning

        Returns layout dictionary: {metabolite: (x, y)}
        """
        registry = build_canonical_pathway_registry()
        return {node.id: (node.x, node.y) for node in registry.nodes}
    
    def define_rbc_reactions(self) -> List[PathwayEdge]:
        """
        Define RBC metabolic reactions

        Returns list of PathwayEdge objects
        """
        registry = build_canonical_pathway_registry()
        return [
            PathwayEdge(
                edge.source,
                edge.target,
                edge.enzyme,
                reversible=edge.reversible,
                color=edge.color,
            )
            for edge in registry.edges
        ]
    
    def build_network(self, reactions: List[PathwayEdge], layout: Dict[str, Tuple[float, float]]):
        """
        Build NetworkX graph from reactions
        
        Parameters:
        -----------
        reactions : list
            List of PathwayEdge objects
        layout : dict
            Node positions {metabolite: (x, y)}
        """
        self.graph.clear()
        
        # Add nodes
        for metabolite, pos in layout.items():
            self.graph.add_node(metabolite, pos=pos)
        
        # Add edges
        for reaction in reactions:
            if reaction.source in layout and reaction.target in layout:
                self.graph.add_edge(
                    reaction.source,
                    reaction.target,
                    enzyme=reaction.enzyme,
                    reversible=reaction.reversible,
                    color=reaction.color
                )
        
        self.node_positions = layout
    
    def create_static_pathway_map(self, 
                                   metabolite_data: Optional[pd.DataFrame] = None,
                                   title: str = "RBC Metabolic Network") -> go.Figure:
        """
        Create static KEGG-style pathway map
        
        Parameters:
        -----------
        metabolite_data : DataFrame, optional
            Current metabolite concentrations for node sizing/coloring
        title : str
            Plot title
            
        Returns:
        --------
        plotly Figure
        """
        # Build network if not already done
        if len(self.graph.nodes) == 0:
            layout = self.define_rbc_pathway_layout()
            reactions = self.define_rbc_reactions()
            self.build_network(reactions, layout)
        
        # Create figure
        fig = go.Figure()
        
        # Draw edges (reactions)
        for edge in self.graph.edges(data=True):
            source, target, data = edge
            
            if source in self.node_positions and target in self.node_positions:
                x0, y0 = self.node_positions[source]
                x1, y1 = self.node_positions[target]
                
                # Draw edge
                fig.add_trace(go.Scatter(
                    x=[x0, x1],
                    y=[y0, y1],
                    mode='lines',
                    line=dict(
                        color=data.get('color', '#95a5a6'),
                        width=2
                    ),
                    hoverinfo='text',
                    hovertext=f"{data.get('enzyme', 'Unknown')}<br>{source} → {target}",
                    showlegend=False
                ))
                
                # Add arrow
                if not data.get('reversible', False):
                    # Calculate arrow position (80% along line)
                    arrow_x = x0 + 0.8 * (x1 - x0)
                    arrow_y = y0 + 0.8 * (y1 - y0)
                    
                    # Calculate arrow direction
                    dx = x1 - x0
                    dy = y1 - y0
                    norm = np.sqrt(dx**2 + dy**2)
                    if norm > 0:
                        dx, dy = dx/norm, dy/norm
                    
                    fig.add_annotation(
                        x=arrow_x,
                        y=arrow_y,
                        ax=arrow_x - 0.1*dx,
                        ay=arrow_y - 0.1*dy,
                        xref='x',
                        yref='y',
                        axref='x',
                        ayref='y',
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=2,
                        arrowcolor=data.get('color', '#95a5a6')
                    )
        
        # Draw nodes (metabolites)
        node_x = []
        node_y = []
        node_text = []
        node_sizes = []
        node_colors = []
        
        for node in self.graph.nodes():
            if node in self.node_positions:
                x, y = self.node_positions[node]
                node_x.append(x)
                node_y.append(y)
                
                # Get concentration if available
                conc = 0
                if metabolite_data is not None and node in metabolite_data.columns:
                    conc = metabolite_data[node].iloc[-1]  # Latest value
                
                node_text.append(f"{node}<br>Conc: {conc:.3f} mM")
                
                # Size based on concentration (or default)
                size = 20 if conc == 0 else 15 + min(conc * 10, 50)
                node_sizes.append(size)
                
                # Color based on concentration
                if conc > 0:
                    # Gradient from blue (low) to red (high)
                    intensity = min(conc / 2.0, 1.0)  # Normalize
                    node_colors.append(f'rgba({int(255*intensity)}, {int(100*(1-intensity))}, {int(255*(1-intensity))}, 0.8)')
                else:
                    node_colors.append('#3498db')
        
        fig.add_trace(go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(color='white', width=2)
            ),
            text=[node for node in self.graph.nodes() if node in self.node_positions],
            textposition='middle center',
            textfont=dict(size=9, color='white', family='Arial Black'),
            hoverinfo='text',
            hovertext=node_text,
            showlegend=False
        ))
        
        # Layout
        fig.update_layout(
            title=title,
            title_font_size=20,
            showlegend=False,
            hovermode='closest',
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-0.5, 9]
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-0.5, 11]
            ),
            plot_bgcolor='#ecf0f1',
            width=1200,
            height=800
        )
        
        return fig
    
    def create_animated_pathway(self, 
                                simulation_results: pd.DataFrame,
                                frame_step: int = 5) -> go.Figure:
        """
        Create animated pathway map showing metabolite changes over time
        
        Parameters:
        -----------
        simulation_results : DataFrame
            Simulation results with time column and metabolite concentrations
        frame_step : int
            Use every Nth timepoint for animation (reduces frames)
            
        Returns:
        --------
        plotly Figure with animation
        """
        # Build network
        layout = self.define_rbc_pathway_layout()
        reactions = self.define_rbc_reactions()
        self.build_network(reactions, layout)
        
        # Prepare frames
        time_points = simulation_results['time'].values[::frame_step]
        frames = []
        
        for t_idx, t in enumerate(time_points):
            # Get data for this timepoint
            data_row = simulation_results[simulation_results['time'] == t].iloc[0]
            
            # Node data
            node_x = []
            node_y = []
            node_sizes = []
            node_colors = []
            node_text = []
            
            for node in self.graph.nodes():
                if node in self.node_positions:
                    x, y = self.node_positions[node]
                    node_x.append(x)
                    node_y.append(y)
                    
                    conc = data_row.get(node, 0)
                    size = 15 + min(conc * 10, 50)
                    node_sizes.append(size)
                    
                    intensity = min(conc / 2.0, 1.0)
                    node_colors.append(f'rgba({int(255*intensity)}, {int(100*(1-intensity))}, {int(255*(1-intensity))}, 0.8)')
                    node_text.append(f"{node}<br>{conc:.3f} mM")
            
            frame = go.Frame(
                data=[go.Scatter(
                    x=node_x,
                    y=node_y,
                    mode='markers+text',
                    marker=dict(
                        size=node_sizes,
                        color=node_colors,
                        line=dict(color='white', width=2)
                    ),
                    text=[n for n in self.graph.nodes() if n in self.node_positions],
                    textposition='middle center',
                    textfont=dict(size=9, color='white', family='Arial Black'),
                    hovertext=node_text,
                    hoverinfo='text'
                )],
                name=str(t)
            )
            frames.append(frame)
        
        # Create initial figure
        fig = self.create_static_pathway_map(
            simulation_results.iloc[[0]],
            title=f"RBC Metabolic Network - t={time_points[0]:.1f}h"
        )
        
        # Add frames
        fig.frames = frames
        
        # Animation controls
        fig.update_layout(
            updatemenus=[{
                'type': 'buttons',
                'showactive': False,
                'buttons': [
                    {'label': '▶ Play', 'method': 'animate', 
                     'args': [None, {'frame': {'duration': 100, 'redraw': True}, 
                                    'fromcurrent': True, 'mode': 'immediate'}]},
                    {'label': '⏸ Pause', 'method': 'animate',
                     'args': [[None], {'frame': {'duration': 0, 'redraw': False}, 
                                      'mode': 'immediate', 'transition': {'duration': 0}}]}
                ]
            }],
            sliders=[{
                'active': 0,
                'steps': [
                    {'args': [[f.name], {'frame': {'duration': 0, 'redraw': True}, 
                                        'mode': 'immediate'}],
                     'label': f"{float(f.name):.1f}h",
                     'method': 'animate'}
                    for f in frames
                ],
                'x': 0.1,
                'len': 0.9,
                'xanchor': 'left',
                'y': 0,
                'yanchor': 'top'
            }]
        )
        
        return fig


def create_3d_metabolite_heatmap(simulation_results: pd.DataFrame, 
                                  metabolites: List[str]) -> go.Figure:
    """
    Create 3D heatmap of metabolite concentrations over time
    
    Parameters:
    -----------
    simulation_results : DataFrame
        Simulation results with time + metabolites
    metabolites : list
        List of metabolites to visualize
        
    Returns:
    --------
    plotly Figure
    """
    # Extract data
    time = simulation_results['time'].values
    data_matrix = []
    
    for metab in metabolites:
        if metab in simulation_results.columns:
            data_matrix.append(simulation_results[metab].values)
        else:
            data_matrix.append(np.zeros(len(time)))
    
    data_matrix = np.array(data_matrix)
    
    # Create 3D surface
    fig = go.Figure(data=[go.Surface(
        z=data_matrix,
        x=time,
        y=list(range(len(metabolites))),
        colorscale='Viridis',
        hovertemplate='Time: %{x:.1f}h<br>Metabolite: %{y}<br>Conc: %{z:.3f} mM<extra></extra>'
    )])
    
    fig.update_layout(
        title='3D Metabolite Heatmap',
        scene=dict(
            xaxis_title='Time (hours)',
            yaxis=dict(
                title='Metabolite',
                ticktext=metabolites,
                tickvals=list(range(len(metabolites)))
            ),
            zaxis_title='Concentration (mM)'
        ),
        width=900,
        height=700
    )
    
    return fig


def create_hierarchical_clustering(simulation_results: pd.DataFrame,
                                   metabolites: List[str]) -> go.Figure:
    """
    Create hierarchical clustering dendrogram of metabolites
    Based on temporal correlation patterns
    
    Parameters:
    -----------
    simulation_results : DataFrame
        Simulation results
    metabolites : list
        Metabolites to cluster
        
    Returns:
    --------
    plotly Figure
    """
    from scipy.cluster.hierarchy import dendrogram, linkage
    from scipy.spatial.distance import pdist
    
    # Extract data matrix
    data_matrix = []
    valid_metabolites = []
    
    for metab in metabolites:
        if metab in simulation_results.columns:
            data_matrix.append(simulation_results[metab].values)
            valid_metabolites.append(metab)
    
    if len(data_matrix) < 2:
        # Not enough data
        fig = go.Figure()
        fig.add_annotation(text="Not enough metabolites for clustering",
                          xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False)
        return fig
    
    data_matrix = np.array(data_matrix)
    
    # Compute linkage
    linkage_matrix = linkage(data_matrix, method='ward')
    
    # Create dendrogram
    dend = dendrogram(linkage_matrix, labels=valid_metabolites, no_plot=True)
    
    # Create plotly figure
    fig = go.Figure()
    
    # Add dendrogram lines
    for i, (x, y) in enumerate(zip(dend['icoord'], dend['dcoord'])):
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines',
            line=dict(color='#2c3e50', width=2),
            hoverinfo='skip',
            showlegend=False
        ))
    
    # Add labels
    fig.update_layout(
        title='Hierarchical Clustering of Metabolites',
        xaxis=dict(
            title='Metabolites',
            ticktext=dend['ivl'],
            tickvals=dend['icoord'][0][1::2],
            tickangle=-45
        ),
        yaxis=dict(title='Distance'),
        width=1000,
        height=600
    )
    
    return fig
