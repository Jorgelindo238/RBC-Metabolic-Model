"""
Bohr Effect Visualization Module for Streamlit
Creates interactive Plotly visualizations of oxygen binding dynamics
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np


def plot_bohr_overview(bohr_data):
    """
    Create comprehensive overview of Bohr effect
    
    Parameters:
    -----------
    bohr_data : dict
        Bohr effect metrics from simulation
        
    Returns:
    --------
    plotly.graph_objects.Figure
    """
    if not bohr_data or 'time' not in bohr_data or len(bohr_data['time']) == 0:
        return None
    
    time = np.array(bohr_data['time'])
    
    # Create 2x2 subplot grid
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>P50 (Half-Saturation Pressure)</b>',
            '<b>O₂ Saturation</b>',
            '<b>pH Dynamics</b>',
            '<b>O₂ Delivery to Tissues</b>'
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": True}, {"secondary_y": False}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.10
    )
    
    # Plot 1: P50 (Half-Saturation Pressure)
    P50 = np.array(bohr_data['P50_mmHg'])
    fig.add_trace(go.Scatter(
        x=time, y=P50,
        mode='lines',
        name='P50',
        line=dict(color='#1f77b4', width=3),
        hovertemplate='Time: %{x:.1f} days<br>P50: %{y:.2f} mmHg<extra></extra>'
    ), row=1, col=1)
    
    # Add normal P50 reference
    fig.add_hline(y=26.8, line_dash="dash", line_color="gray", 
                  annotation_text="Normal (26.8)", annotation_position="right",
                  row=1, col=1)
    fig.add_hrect(y0=25, y1=28.5, fillcolor="green", opacity=0.1,
                  annotation_text="Physiol. range", annotation_position="top right",
                  row=1, col=1)
    
    fig.update_xaxes(title_text="Time (days)", row=1, col=1)
    fig.update_yaxes(title_text="P50 (mmHg)", row=1, col=1)
    
    # Plot 2: O2 Saturation (Arterial vs Venous)
    sat_art = np.array(bohr_data['sat_arterial']) * 100
    sat_ven = np.array(bohr_data['sat_venous']) * 100
    
    fig.add_trace(go.Scatter(
        x=time, y=sat_art,
        mode='lines',
        name='Arterial',
        line=dict(color='#ff4444', width=2.5),
        hovertemplate='Time: %{x:.1f} days<br>Sat: %{y:.1f}%<extra></extra>'
    ), row=1, col=2)
    
    fig.add_trace(go.Scatter(
        x=time, y=sat_ven,
        mode='lines',
        name='Venous',
        line=dict(color='#4444ff', width=2.5),
        hovertemplate='Time: %{x:.1f} days<br>Sat: %{y:.1f}%<extra></extra>'
    ), row=1, col=2)
    
    # Add extraction zone
    fig.add_trace(go.Scatter(
        x=np.concatenate([time, time[::-1]]),
        y=np.concatenate([sat_art, sat_ven[::-1]]),
        fill='toself',
        fillcolor='rgba(100,200,100,0.2)',
        line=dict(width=0),
        name='O₂ Extraction',
        showlegend=True,
        hoverinfo='skip'
    ), row=1, col=2)
    
    fig.update_xaxes(title_text="Time (days)", row=1, col=2)
    fig.update_yaxes(title_text="O₂ Saturation (%)", row=1, col=2)
    
    # Plot 3: pH Dynamics (pHi and pHe)
    pHi = np.array(bohr_data['pHi'])
    pHe = np.array(bohr_data['pHe'])
    BPG = np.array(bohr_data['BPG_mM'])
    
    fig.add_trace(go.Scatter(
        x=time, y=pHi,
        mode='lines',
        name='pHi (Intracellular)',
        line=dict(color='#ff7f0e', width=2.5),
        hovertemplate='Time: %{x:.1f} days<br>pHi: %{y:.3f}<extra></extra>'
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=time, y=pHe,
        mode='lines',
        name='pHe (Extracellular)',
        line=dict(color='#2ca02c', width=2.5),
        hovertemplate='Time: %{x:.1f} days<br>pHe: %{y:.3f}<extra></extra>'
    ), row=2, col=1)
    
    # Add 2,3-BPG on secondary axis
    fig.add_trace(go.Scatter(
        x=time, y=BPG,
        mode='lines',
        name='2,3-BPG',
        line=dict(color='#9467bd', width=2, dash='dot'),
        yaxis='y4',
        hovertemplate='Time: %{x:.1f} days<br>BPG: %{y:.2f} mM<extra></extra>'
    ), row=2, col=1, secondary_y=True)
    
    fig.update_xaxes(title_text="Time (days)", row=2, col=1)
    fig.update_yaxes(title_text="pH", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="2,3-BPG (mM)", row=2, col=1, secondary_y=True)
    
    # Plot 4: O2 Delivery Metrics
    O2_extraction = np.array(bohr_data['O2_extracted_fraction']) * 100
    
    fig.add_trace(go.Scatter(
        x=time, y=O2_extraction,
        mode='lines',
        name='O₂ Extraction',
        line=dict(color='#d62728', width=3),
        fill='tozeroy',
        fillcolor='rgba(214, 39, 40, 0.2)',
        hovertemplate='Time: %{x:.1f} days<br>Extraction: %{y:.1f}%<extra></extra>'
    ), row=2, col=2)
    
    # Add normal extraction reference
    fig.add_hline(y=25, line_dash="dash", line_color="gray",
                  annotation_text="Normal (25%)", annotation_position="right",
                  row=2, col=2)
    
    fig.update_xaxes(title_text="Time (days)", row=2, col=2)
    fig.update_yaxes(title_text="O₂ Extraction (%)", row=2, col=2)
    
    # Update overall layout
    fig.update_layout(
        title=dict(
            text="<b>Bohr Effect: Oxygen Binding & Delivery Dynamics</b>",
            font=dict(size=18),
            x=0.5,
            xanchor='center'
        ),
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig


def plot_bohr_summary_cards(bohr_data):
    """
    Create summary metrics cards for Bohr effect
    
    Returns:
    --------
    dict with summary metrics
    """
    if not bohr_data or 'time' not in bohr_data or len(bohr_data['time']) == 0:
        return None
    
    P50_initial = bohr_data['P50_mmHg'][0]
    P50_final = bohr_data['P50_mmHg'][-1]
    P50_mean = np.mean(bohr_data['P50_mmHg'])
    
    sat_art_mean = np.mean(bohr_data['sat_arterial']) * 100
    sat_ven_mean = np.mean(bohr_data['sat_venous']) * 100
    extraction_mean = np.mean(bohr_data['O2_extracted_fraction']) * 100
    
    pH_i_mean = np.mean(bohr_data['pHi'])
    pH_e_mean = np.mean(bohr_data['pHe'])
    BPG_mean = np.mean(bohr_data['BPG_mM'])
    
    return {
        'P50': {
            'initial': P50_initial,
            'final': P50_final,
            'mean': P50_mean,
            'change': P50_final - P50_initial,
            'unit': 'mmHg'
        },
        'saturation': {
            'arterial': sat_art_mean,
            'venous': sat_ven_mean,
            'extraction': extraction_mean,
            'unit': '%'
        },
        'pH': {
            'intracellular': pH_i_mean,
            'extracellular': pH_e_mean
        },
        'BPG': {
            'mean': BPG_mean,
            'unit': 'mM'
        }
    }


def create_bohr_interpretation_text(bohr_summary, ph_type):
    """
    Generate clinical interpretation of Bohr effect results
    
    Parameters:
    -----------
    bohr_summary : dict
        Summary metrics from plot_bohr_summary_cards
    ph_type : str
        Type of pH perturbation
        
    Returns:
    --------
    str: Formatted interpretation text
    """
    if not bohr_summary:
        return "No Bohr effect data available."
    
    P50_mean = bohr_summary['P50']['mean']
    P50_change = bohr_summary['P50']['change']
    extraction = bohr_summary['saturation']['extraction']
    
    # Determine physiological state
    if P50_mean < 25:
        affinity_state = "**INCREASED O₂ affinity** (↓P50)"
        clinical = "RBCs hold onto oxygen more tightly → **Reduced tissue delivery**"
    elif P50_mean > 28.5:
        affinity_state = "**DECREASED O₂ affinity** (↑P50)"
        clinical = "RBCs release oxygen more easily → **Enhanced tissue delivery**"
    else:
        affinity_state = "**NORMAL O₂ affinity**"
        clinical = "Oxygen binding and delivery within physiological range"
    
    # Build interpretation
    interpretation = f"""
### 📊 **Bohr Effect Analysis**

**P50 Status:** {affinity_state}
- Mean P50: {P50_mean:.1f} mmHg (Normal: 26.8 mmHg)
- Change: {P50_change:+.1f} mmHg

**Clinical Significance:**
{clinical}

**O₂ Extraction Efficiency:** {extraction:.1f}% (Normal: ~25%)

---

**Mechanism ({ph_type}):**
"""
    
    if ph_type in ["Acidosis", "Step", "Ramp"] and bohr_summary['pH']['extracellular'] < 7.35:
        interpretation += """
- ↓ pH → Protonation of hemoglobin → ↓ O₂ affinity
- ↑ 2,3-BPG stabilizes T-state → Facilitates O₂ release
- **Right shift** of O₂-hemoglobin dissociation curve
"""
    elif ph_type == "Alkalosis" and bohr_summary['pH']['extracellular'] > 7.45:
        interpretation += """
- ↑ pH → Deprotonation of hemoglobin → ↑ O₂ affinity  
- ↓ 2,3-BPG → Less T-state stabilization
- **Left shift** of O₂-hemoglobin dissociation curve
"""
    else:
        interpretation += """
- pH within normal range (7.35-7.45)
- 2,3-BPG levels stable
- Standard O₂-hemoglobin dissociation curve
"""
    
    return interpretation
