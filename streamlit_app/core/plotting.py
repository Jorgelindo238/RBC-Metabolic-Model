"""
Plotting Module - Interactive Plotly visualizations for Streamlit
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import streamlit as st
import sys
from pathlib import Path

# Add src to path for pH perturbation
project_root = Path(__file__).parent.parent.parent
src_path = str(project_root / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from ph_perturbation import PhPerturbation
    PH_AVAILABLE = True
except ImportError:
    PH_AVAILABLE = False


def plot_metabolites_interactive(results, selected_metabolites, show_experimental=True):
    """
    Create interactive Plotly plot for selected metabolites
    
    Parameters:
    -----------
    results : dict
        Simulation results
    selected_metabolites : list
        List of metabolite names to plot
    show_experimental : bool
        Whether to show experimental data points
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not results or 'error' in results:
        return None
    
    fig = go.Figure()
    
    # Plot each selected metabolite
    for metab in selected_metabolites:
        try:
            idx = results['metabolite_names'].index(metab)
            
            # Simulation line
            fig.add_trace(go.Scatter(
                x=results['t'],
                y=results['x'][:, idx],
                mode='lines',
                name=metab,
                line=dict(width=2),
                hovertemplate='<b>%{fullData.name}</b><br>' +
                             'Time: %{x:.2f}h<br>' +
                             'Concentration: %{y:.4f} mM<br>' +
                             '<extra></extra>'
            ))
            
            # Add experimental data if available
            if show_experimental and 'experimental_data' in results:
                exp_data = results['experimental_data']
                if metab in exp_data['metabolites']:
                    metab_idx = exp_data['metabolites'].index(metab)
                    fig.add_trace(go.Scatter(
                        x=exp_data['time'],
                        y=exp_data['values'][metab_idx, :],
                        mode='markers',
                        name=f'{metab} (exp)',
                        marker=dict(size=8, symbol='circle-open'),
                        hovertemplate='<b>%{fullData.name}</b><br>' +
                                     'Time: %{x:.2f}h<br>' +
                                     'Concentration: %{y:.4f} mM<br>' +
                                     '<extra></extra>'
                    ))
        
        except (ValueError, IndexError, KeyError) as e:
            st.warning(f"Could not plot {metab}: {e}")
            continue
    
    # Layout
    fig.update_layout(
        title=dict(
            text="Metabolite Concentrations Over Time",
            font=dict(size=20)
        ),
        xaxis=dict(
            title="Time (days)",
            gridcolor='lightgray',
            showgrid=True
        ),
        yaxis=dict(
            title="Concentration (mM)",
            gridcolor='lightgray',
            showgrid=True
        ),
        hovermode='x unified',
        template='plotly_white',
        height=600,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99
        )
    )
    
    return fig


def plot_single_metabolite_comparison(results, metabolite_name):
    """
    Plot single metabolite with experimental comparison
    Optimized for grid display with compact layout
    """
    if not results or 'error' in results:
        return None
    
    try:
        idx = results['metabolite_names'].index(metabolite_name)
    except ValueError:
        return None
    
    fig = go.Figure()
    
    # Get concentration values for auto-ranging
    conc_values = results['x'][:, idx]
    y_min, y_max = conc_values.min(), conc_values.max()
    y_range = y_max - y_min
    
    # Simulation line
    fig.add_trace(go.Scatter(
        x=results['t'],
        y=conc_values,
        mode='lines',
        name='Simulation',
        line=dict(color='#FF4B4B', width=2.5),
        hovertemplate='<b>Simulation</b><br>' +
                     'Time: %{x:.1f} days<br>' +
                     'Conc: %{y:.4f} mM<br>' +
                     '<extra></extra>'
    ))
    
    # Experimental points - Bordbar et al. data
    # Match by name (case-insensitive) for ALL metabolites
    has_experimental = False
    if 'experimental_data' in results and results['experimental_data']['metabolites']:
        exp_data = results['experimental_data']
        metab_idx = None
        
        # Same matching strategy as CLI visualization.py lines 83-84, 98-99
        metab_name_lower = metabolite_name.lower()
        match_indices = [k for k, name in enumerate(exp_data['metabolites']) 
                        if str(name).lower() == metab_name_lower]
        
        if match_indices:
            metab_idx = match_indices[0]  # Take first match if multiple
        
        if metab_idx is not None:
            try:
                # Note: exp_data['values'] is in shape (n_metabolites, n_timepoints) like CLI
                # So we index as values[metab_idx, :] not values[:, metab_idx]
                if (exp_data['values'].size > 0 and 
                    len(exp_data['values'].shape) == 2 and 
                    exp_data['values'].shape[0] > metab_idx):
                    
                    # Bordbar et al. data - circle marker with dark gray
                    fig.add_trace(go.Scatter(
                        x=exp_data['time'],
                        y=exp_data['values'][metab_idx, :],
                        mode='markers',
                        name='Bordbar et al.',
                        marker=dict(
                            size=8,
                            color='#262730',  # Dark gray
                            symbol='circle',
                            line=dict(width=1, color='white')
                        ),
                        hovertemplate='<b>Bordbar et al.</b><br>' +
                                     'Time: %{x:.1f} days<br>' +
                                     'Conc: %{y:.4f} mM<br>' +
                                     '<extra></extra>'
                    ))
                    has_experimental = True
            except (IndexError, KeyError, ValueError) as e:
                # Silently skip if data not available
                pass
    
    # Custom validation data (if in validation mode)
    if 'custom_validation_data' in results and results['custom_validation_data'] is not None:
        custom_data = results['custom_validation_data']
        
        # Check if metabolite exists in custom data
        if metabolite_name in custom_data['metabolites']:
            try:
                metab_idx = custom_data['metabolites'].index(metabolite_name)
                if (custom_data['values'].size > 0 and 
                    len(custom_data['values'].shape) == 2 and 
                    custom_data['values'].shape[0] > metab_idx):
                    
                    # Custom data - diamond marker with blue color
                    fig.add_trace(go.Scatter(
                        x=custom_data['time'],
                        y=custom_data['values'][metab_idx, :],
                        mode='markers',
                        name='Custom Data',
                        marker=dict(
                            size=10,
                            color='#1f77b4',  # Blue
                            symbol='diamond',
                            line=dict(width=2, color='white')
                        ),
                        hovertemplate='<b>Custom Data</b><br>' +
                                     'Time: %{x:.1f} days<br>' +
                                     'Conc: %{y:.4f} mM<br>' +
                                     '<extra></extra>'
                    ))
                    has_experimental = True
            except (IndexError, KeyError, ValueError) as e:
                # Silently skip if data not available
                pass
    
    # Layout optimized for grid display
    title_text = f"<b>{metabolite_name}</b>"
    if has_experimental:
        title_text += " <span style='font-size:10px; color:gray;'>(with exp. data)</span>"
    
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=14),
            x=0.5,
            xanchor='center'
        ),
        xaxis=dict(
            title="Time (days)",
            title_font=dict(size=11),
            gridcolor='#E5E5E5',
            showgrid=True
        ),
        yaxis=dict(
            title="Conc (mM)",
            title_font=dict(size=11),
            gridcolor='#E5E5E5',
            showgrid=True,
            # Auto-range with 10% padding
            range=[y_min - 0.1 * y_range, y_max + 0.1 * y_range] if y_range > 0 else None
        ),
        template='plotly_white',
        height=350,  # Compact height for grid
        margin=dict(l=50, r=20, t=50, b=40),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10)
        ),
        hovermode='x unified'
    )
    
    return fig


def plot_pathway_metabolites(results, pathway_name, metabolite_list):
    """
    Plot all metabolites from a specific pathway
    """
    return plot_metabolites_interactive(results, metabolite_list)


def create_heatmap(results, metabolite_subset=None):
    """
    Create heatmap of metabolite concentrations over time
    
    Parameters:
    -----------
    results : dict
        Simulation results
    metabolite_subset : list
        Subset of metabolites to include (default: all)
    
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not results or 'error' in results:
        return None
    
    # Select metabolites
    if metabolite_subset is None:
        metabolite_subset = results['metabolite_names'][:30]  # First 30 to avoid overcrowding
    
    # Extract data
    indices = [results['metabolite_names'].index(m) for m in metabolite_subset if m in results['metabolite_names']]
    data_matrix = results['x'][:, indices].T
    
    # Normalize for better visualization
    data_normalized = (data_matrix - data_matrix.min(axis=1, keepdims=True)) / \
                     (data_matrix.max(axis=1, keepdims=True) - data_matrix.min(axis=1, keepdims=True) + 1e-10)
    
    fig = go.Figure(data=go.Heatmap(
        z=data_normalized,
        x=results['t'],
        y=[metabolite_subset[i] for i in range(len(indices))],
        colorscale='Viridis',
        hovertemplate='Metabolite: %{y}<br>Time: %{x:.2f} days<br>Normalized: %{z:.3f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Metabolite Dynamics Heatmap",
        xaxis_title="Time (days)",
        yaxis_title="Metabolites",
        height=max(400, len(indices) * 20),
        template='plotly_white'
    )
    
    return fig


def plot_ph_profile(ph_perturbation_info, t_max):
    """
    Plot pH perturbation profile over simulation time
    
    Parameters:
    -----------
    ph_perturbation_info : dict
        pH perturbation configuration from results
    t_max : float
        Maximum simulation time
    
    Returns:
    --------
    plotly.graph_objects.Figure
        pH profile figure
    """
    if not PH_AVAILABLE or ph_perturbation_info['type'] == "None":
        return None
    
    try:
        # Recreate perturbation object from saved info
        from ph_perturbation import (create_step_perturbation, create_ramp_perturbation,
                                     get_acidosis_scenario, get_alkalosis_scenario)
        
        pert_type = ph_perturbation_info['type']
        
        if pert_type == "Acidosis":
            perturbation = get_acidosis_scenario(ph_perturbation_info['severity'])
        elif pert_type == "Alkalosis":
            perturbation = get_alkalosis_scenario(ph_perturbation_info['severity'])
        elif pert_type == "Step":
            perturbation = create_step_perturbation(pH_target=ph_perturbation_info['target'], t_start=2.0)
        elif pert_type == "Ramp":
            perturbation = create_ramp_perturbation(
                pH_initial=7.4,
                pH_final=ph_perturbation_info['target'],
                t_start=2.0,
                duration=ph_perturbation_info['duration']
            )
        else:
            return None
        
        # Generate pH values
        times = np.linspace(0, t_max, 500)
        pHe_values = [perturbation.get_pHe(t) for t in times]
        
        # Create figure
        fig = go.Figure()
        
        # pH profile line
        fig.add_trace(go.Scatter(
            x=times,
            y=pHe_values,
            mode='lines',
            name='Extracellular pH (pHe)',
            line=dict(color='#1f77b4', width=3),
            hovertemplate='Time: %{x:.1f} days<br>pHe: %{y:.2f}<extra></extra>'
        ))
        
        # Normal pH reference
        fig.add_hline(y=7.4, line_dash="dash", line_color="green", 
                     annotation_text="Normal pHe (7.4)", annotation_position="right")
        
        # Physiological range
        fig.add_hrect(y0=7.35, y1=7.45, fillcolor="green", opacity=0.1,
                     annotation_text="Normal range", annotation_position="top right")
        
        fig.update_layout(
            title=f"pH Perturbation Profile<br><sub>{ph_perturbation_info['description']}</sub>",
            xaxis_title="Time (days)",
            yaxis_title="pH",
            height=400,
            hovermode='x unified',
            template='plotly_white',
            yaxis=dict(range=[6.5, 8.0])
        )
        
        return fig
        
    except Exception as e:
        st.warning(f"Could not create pH profile plot: {e}")
        return None


def plot_summary_statistics(results):
    """
    Create summary statistics plots
    """
    if not results or 'error' in results:
        return None
    
    # Calculate statistics
    mean_conc = np.mean(results['x'], axis=0)
    std_conc = np.std(results['x'], axis=0)
    max_conc = np.max(results['x'], axis=0)
    
    # Sort by mean concentration
    sorted_idx = np.argsort(mean_conc)[::-1][:20]  # Top 20
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=[results['metabolite_names'][i] for i in sorted_idx],
        y=mean_conc[sorted_idx],
        error_y=dict(type='data', array=std_conc[sorted_idx]),
        name='Mean ± SD',
        marker_color='#FF4B4B'
    ))
    
    fig.update_layout(
        title="Top 20 Metabolites by Mean Concentration",
        xaxis_title="Metabolite",
        yaxis_title="Concentration (mM)",
        xaxis_tickangle=-45,
        height=500,
        template='plotly_white'
    )
    
    return fig


def plot_time_course_grid(results, metabolites_list, n_cols=3):
    """
    Create grid of subplots for multiple metabolites
    """
    if not results or 'error' in results:
        return None
    
    n_metabolites = len(metabolites_list)
    n_rows = (n_metabolites + n_cols - 1) // n_cols
    
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=metabolites_list,
        vertical_spacing=0.1,
        horizontal_spacing=0.1
    )
    
    for i, metab in enumerate(metabolites_list):
        try:
            idx = results['metabolite_names'].index(metab)
            row = i // n_cols + 1
            col = i % n_cols + 1
            
            fig.add_trace(
                go.Scatter(
                    x=results['t'],
                    y=results['x'][:, idx],
                    mode='lines',
                    name=metab,
                    showlegend=False,
                    line=dict(color='#FF4B4B')
                ),
                row=row,
                col=col
            )
        except (ValueError, IndexError):
            continue
    
    fig.update_xaxes(title_text="Time (days)")
    fig.update_yaxes(title_text="Conc (mM)")
    
    fig.update_layout(
        title_text="Metabolite Time Courses",
        height=300 * n_rows,
        template='plotly_white'
    )
    
    return fig
