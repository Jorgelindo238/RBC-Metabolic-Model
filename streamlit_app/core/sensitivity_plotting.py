"""
Sensitivity Analysis Plotting - Visualizations for data impact comparison
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


def plot_flux_difference_heatmap(analyzer) -> go.Figure:
    """
    Fluxes are no longer compared (identical for both datasets).
    
    Returns empty figure with message.
    
    Parameters:
    -----------
    analyzer : SensitivityAnalyzer
        Analyzer with comparison data
    
    Returns:
    --------
    go.Figure
        Empty figure with explanation
    """
    # Fluxes are determined by ODE system, not experimental data
    fig = go.Figure()
    fig.add_annotation(
        text="Flux comparison not available<br>(Fluxes are identical for both datasets)",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16)
    )
    return fig


def plot_metabolite_comparison_tornado(analyzer, n: int = 15) -> go.Figure:
    """
    Create tornado plot showing top metabolite changes.
    
    Parameters:
    -----------
    analyzer : SensitivityAnalyzer
        Analyzer with comparison data
    n : int
        Number of top metabolites to show
    
    Returns:
    --------
    go.Figure
        Tornado plot
    """
    comparison = analyzer.compare_metabolite_concentrations()
    
    if comparison.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No metabolite comparison data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    # Get top N by absolute percent change
    top_n = comparison.nlargest(n, 'Max_Difference')
    
    # Sort by percent change for tornado effect
    top_n = top_n.sort_values('Percent_Change')
    
    # Create tornado plot
    colors = ['#FF6B6B' if x > 0 else '#4ECDC4' for x in top_n['Percent_Change']]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=top_n['Metabolite'],
        x=top_n['Percent_Change'],
        orientation='h',
        marker=dict(color=colors),
        text=[f"{x:+.1f}%" for x in top_n['Percent_Change']],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Change: %{x:.2f}%<br>Max Δ: %{customdata:.4f} mM<extra></extra>',
        customdata=top_n['Max_Difference']
    ))
    
    fig.update_layout(
        title=f'Top {n} Most Sensitive Metabolites<br><sub>% Change in Mean Concentration</sub>',
        xaxis_title='Percent Change (%)',
        yaxis_title='',
        height=max(400, n * 25),
        showlegend=False,
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black')
    )
    
    return fig


def plot_pathway_impact_summary(pathway_summary: Dict) -> go.Figure:
    """
    Create summary visualization of pathway impacts.
    
    Parameters:
    -----------
    pathway_summary : dict
        Pathway impact statistics
    
    Returns:
    --------
    go.Figure
        Pathway impact bar chart
    """
    if not pathway_summary:
        fig = go.Figure()
        fig.add_annotation(
            text="No pathway data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    pathways = list(pathway_summary.keys())
    mean_changes = [pathway_summary[p]['mean_pct_change'] for p in pathways]
    n_reactions = [pathway_summary[p]['n_reactions'] for p in pathways]
    
    # Sort by absolute mean change
    sorted_indices = np.argsort([abs(x) for x in mean_changes])[::-1]
    pathways = [pathways[i] for i in sorted_indices]
    mean_changes = [mean_changes[i] for i in sorted_indices]
    n_reactions = [n_reactions[i] for i in sorted_indices]
    
    colors = ['#FF6B6B' if x > 0 else '#4ECDC4' for x in mean_changes]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=pathways,
        y=mean_changes,
        marker=dict(color=colors),
        text=[f"{x:+.1f}%<br>({n} rxns)" for x, n in zip(mean_changes, n_reactions)],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Mean Change: %{y:.2f}%<br>Reactions: %{customdata}<extra></extra>',
        customdata=n_reactions
    ))
    
    fig.update_layout(
        title='Pathway Sensitivity Summary<br><sub>Mean % Change in Flux</sub>',
        xaxis_title='Metabolic Pathway',
        yaxis_title='Mean % Change',
        height=500,
        showlegend=False,
        yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='black')
    )
    
    return fig


def plot_side_by_side_comparison(analyzer, metabolite_name: str) -> go.Figure:
    """
    Create side-by-side comparison of a specific metabolite.
    
    Parameters:
    -----------
    analyzer : SensitivityAnalyzer
        Analyzer with comparison data
    metabolite_name : str
        Name of metabolite to compare
    
    Returns:
    --------
    go.Figure
        Side-by-side comparison plot
    """
    if metabolite_name not in analyzer.metabolites:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Metabolite {metabolite_name} not found",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    met_idx = analyzer.metabolites.index(metabolite_name)
    
    # Get simulation time and concentrations (same for both)
    time_sim = analyzer.time_sim
    conc_sim = analyzer.conc_sim[:, met_idx]
    
    # Get experimental data
    exp_b = analyzer.exp_brodbar
    exp_c = analyzer.exp_custom
    
    # Create figure with two subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Bordbar et al. Data', 'Custom Data'),
        horizontal_spacing=0.1
    )
    
    # Left: Bordbar experimental data
    if exp_b and metabolite_name in exp_b.get('metabolites', []):
        idx = exp_b['metabolites'].index(metabolite_name)
        fig.add_trace(
            go.Scatter(
                x=exp_b['time'],
                y=exp_b['values'][idx, :],
                mode='markers',
                name='Bordbar Exp',
                marker=dict(size=8, color='#262730', symbol='circle'),
                hovertemplate='Time: %{x:.1f} days<br>Conc: %{y:.4f} mM<extra></extra>'
            ),
            row=1, col=1
        )
    
    # Add simulation line to Bordbar plot
    fig.add_trace(
        go.Scatter(
            x=time_sim,
            y=conc_sim,
            mode='lines',
            name='Simulation',
            line=dict(color='#FF4B4B', width=2.5),
            hovertemplate='Time: %{x:.1f} days<br>Conc: %{y:.4f} mM<extra></extra>'
        ),
        row=1, col=1
    )
    
    # Right: Custom experimental data
    if exp_c and metabolite_name in exp_c.get('metabolites', []):
        idx = exp_c['metabolites'].index(metabolite_name)
        fig.add_trace(
            go.Scatter(
                x=exp_c['time'],
                y=exp_c['values'][idx, :],
                mode='markers',
                name='Custom Exp',
                marker=dict(size=10, color='#1f77b4', symbol='diamond'),
                hovertemplate='Time: %{x:.1f} days<br>Conc: %{y:.4f} mM<extra></extra>'
            ),
            row=1, col=2
        )
    
    # Add simulation line to Custom plot
    fig.add_trace(
        go.Scatter(
            x=time_sim,
            y=conc_sim,
            mode='lines',
            name='Simulation',
            line=dict(color='#FF4B4B', width=2.5),
            hovertemplate='Time: %{x:.1f} days<br>Conc: %{y:.4f} mM<extra></extra>'
        ),
        row=1, col=2
    )
    
    fig.update_xaxes(title_text="Time (days)", row=1, col=1)
    fig.update_xaxes(title_text="Time (days)", row=1, col=2)
    fig.update_yaxes(title_text="Concentration (mM)", row=1, col=1)
    fig.update_yaxes(title_text="Concentration (mM)", row=1, col=2)
    
    fig.update_layout(
        title=f'{metabolite_name} - Data Source Comparison',
        height=400,
        showlegend=True
    )
    
    return fig


def plot_validation_metrics(metrics: Dict) -> go.Figure:
    """
    Create visualization of validation metrics.
    
    Parameters:
    -----------
    metrics : dict
        Validation metrics for each metabolite
    
    Returns:
    --------
    go.Figure
        Validation metrics visualization
    """
    if not metrics:
        fig = go.Figure()
        fig.add_annotation(
            text="No validation metrics available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig
    
    metabolites = list(metrics.keys())
    r2_values = [metrics[m]['R2'] for m in metabolites]
    rmse_values = [metrics[m]['RMSE'] for m in metabolites]
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('R² (Goodness of Fit)', 'RMSE (Prediction Error)'),
        horizontal_spacing=0.15
    )
    
    # R² plot
    fig.add_trace(
        go.Bar(
            x=metabolites,
            y=r2_values,
            name='R²',
            marker=dict(
                color=r2_values,
                colorscale='Viridis',
                cmin=0,
                cmax=1,
                colorbar=dict(title='R²', x=0.45)
            ),
            hovertemplate='<b>%{x}</b><br>R²: %{y:.3f}<extra></extra>'
        ),
        row=1, col=1
    )
    
    # RMSE plot
    fig.add_trace(
        go.Bar(
            x=metabolites,
            y=rmse_values,
            name='RMSE',
            marker=dict(color='#FF6B6B'),
            hovertemplate='<b>%{x}</b><br>RMSE: %{y:.4f} mM<extra></extra>'
        ),
        row=1, col=2
    )
    
    # Add threshold lines
    fig.add_hline(y=0.9, line=dict(color='green', dash='dash', width=1),
                  annotation_text='Good fit (R² > 0.9)', row=1, col=1)
    
    fig.update_xaxes(title_text="Metabolite", row=1, col=1)
    fig.update_xaxes(title_text="Metabolite", row=1, col=2)
    fig.update_yaxes(title_text="R² Score", range=[0, 1], row=1, col=1)
    fig.update_yaxes(title_text="RMSE (mM)", row=1, col=2)
    
    fig.update_layout(
        title='Validation Metrics: Custom Data vs Simulation',
        height=500,
        showlegend=False
    )
    
    return fig


def create_comparison_summary_cards(analyzer) -> Tuple[Dict, Dict, Dict]:
    """
    Create summary statistics for display cards.
    
    Parameters:
    -----------
    analyzer : SensitivityAnalyzer
        Analyzer with comparison data
    
    Returns:
    --------
    tuple of dicts
        (metabolite_stats, flux_stats, overall_stats)
    """
    met_comparison = analyzer.compare_metabolite_concentrations()
    flux_comparison = analyzer.compare_flux_profiles()
    
    # Metabolite stats
    if not met_comparison.empty:
        met_stats = {
            'n_metabolites': len(met_comparison),
            'max_change': met_comparison['Max_Difference'].max(),
            'mean_change': met_comparison['Mean_Difference'].mean(),
            'most_sensitive': met_comparison.iloc[0]['Metabolite'] if len(met_comparison) > 0 else 'N/A'
        }
    else:
        met_stats = {'n_metabolites': 0, 'max_change': 0, 'mean_change': 0, 'most_sensitive': 'N/A'}
    
    # Flux stats
    if not flux_comparison.empty:
        flux_stats = {
            'n_reactions': len(flux_comparison),
            'max_pct_change': flux_comparison['Absolute_Pct_Change'].max(),
            'mean_pct_change': flux_comparison['Percent_Change'].mean(),
            'most_sensitive': flux_comparison.iloc[0]['Reaction'] if len(flux_comparison) > 0 else 'N/A'
        }
    else:
        flux_stats = {'n_reactions': 0, 'max_pct_change': 0, 'mean_pct_change': 0, 'most_sensitive': 'N/A'}
    
    # Overall stats - use experimental data timepoints
    exp_b_time = analyzer.exp_brodbar.get('time', []) if analyzer.exp_brodbar else []
    exp_c_time = analyzer.exp_custom.get('time', []) if analyzer.exp_custom else []
    
    # Handle numpy arrays
    n_time_b = len(exp_b_time) if exp_b_time is not None and hasattr(exp_b_time, '__len__') else 0
    n_time_c = len(exp_c_time) if exp_c_time is not None and hasattr(exp_c_time, '__len__') else 0
    
    overall_stats = {
        'data_source': 'Custom Data',
        'n_timepoints_custom': n_time_c,
        'n_timepoints_brodbar': n_time_b,
        'simulation_match': 'Yes' if n_time_c > 0 and n_time_b > 0 and n_time_c == n_time_b else 'No'
    }
    
    return met_stats, flux_stats, overall_stats
