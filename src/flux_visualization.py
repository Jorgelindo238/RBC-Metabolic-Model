"""
Flux Visualization Module for RBC Metabolic Model
==================================================

This module provides comprehensive visualization of reaction fluxes
alongside metabolite concentrations.

Author: Jorgelindo da Veiga
Date: 2025-11-14
"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib.backends.backend_pdf


class FluxTracker:
    """
    Tracks and stores reaction fluxes during ODE integration.
    """
    
    def __init__(self):
        self.times = []
        self.fluxes = {}
        self.reaction_names = []
        
    def add_timepoint(self, t: float, flux_dict: Dict[str, float]):
        """
        Add flux values for a specific timepoint.
        
        Parameters:
        -----------
        t : float
            Time point (hours)
        flux_dict : dict
            Dictionary of {reaction_name: flux_value}
        """
        self.times.append(t)
        for reaction, flux in flux_dict.items():
            if reaction not in self.fluxes:
                self.fluxes[reaction] = []
                if reaction not in self.reaction_names:
                    self.reaction_names.append(reaction)
            self.fluxes[reaction].append(flux)
    
    def get_flux_array(self) -> np.ndarray:
        """
        Get fluxes as a 2D numpy array (time x reactions).
        
        Returns:
        --------
        np.ndarray
            Array of shape (n_timepoints, n_reactions)
        """
        flux_matrix = []
        for reaction in self.reaction_names:
            flux_matrix.append(self.fluxes[reaction])
        return np.array(flux_matrix).T
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert flux data to pandas DataFrame.
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with time as index and reactions as columns
        """
        df = pd.DataFrame(self.fluxes, index=self.times)
        df.index.name = 'Time (hours)'
        return df
    
    def save_to_csv(self, filepath: str):
        """Save flux data to CSV file."""
        df = self.to_dataframe()
        df.to_csv(filepath)
        print(f"[OK] Flux data saved to: {filepath}")


def categorize_reactions() -> Dict[str, List[str]]:
    """
    Categorize reactions by metabolic pathway.
    
    Returns:
    --------
    dict
        Dictionary of {pathway_name: [reaction_names]}
    """
    return {
        'Glycolysis': [
            'VHK', 'VPGI', 'VPFK', 'VALDO', 'VTPI', 'VGAPDH', 
            'VPGK', 'VPGM', 'VENO', 'VPK', 'VLDH'
        ],
        'Pentose Phosphate Pathway': [
            'VG6PDH', 'VPGL', 'VGD', 'VRU5P', 'VXISO', 'VRIBO', 
            'VTK1', 'VTK2', 'VTA'
        ],
        'Adenylate Metabolism': [
            'VATP', 'VADP', 'VAMP', 'VAK', 'VADEK', 'VADA', 
            'VADNK', 'VAPRT', 'VHGPRT'
        ],
        'Purine Salvage': [
            'VHXPRT', 'VIMPD', 'VGMPS', 'VGMPR', 'VAMPD', 
            'VADA', 'VADNK', 'VNP', 'VGUA'
        ],
        'Glutathione': [
            'VGSH', 'VGSSG', 'VGR', 'VGPX', 'VGST'
        ],
        'Amino Acids': [
            'VASPAT', 'VALAAT', 'VGLNS', 'VGLDH', 'VSER', 
            'VMET', 'VSAHH', 'VCBS'
        ],
        'Transport': [
            'VGLCT', 'VLACT', 'VPYRT', 'VGLNT', 'VGLUT', 
            'VCYST', 'VSERT', 'VURT', 'VADET', 'VINOT', 
            'VHXPT', 'VXANT', 'VCITT', 'VMALT', 'VFUMT'
        ],
        'Other': [
            'VDO', 'VCATAL', 'VNO', 'VNOXB', 'VGLY'
        ]
    }


def plot_pathway_fluxes(flux_tracker: FluxTracker, pathway: str, 
                       reactions: List[str], save_path: str):
    """
    Plot all fluxes in a specific pathway.
    
    Parameters:
    -----------
    flux_tracker : FluxTracker
        Object containing flux data
    pathway : str
        Name of the pathway
    reactions : list
        List of reaction names in this pathway
    save_path : str
        Path to save the plot
    """
    times = np.array(flux_tracker.times)
    
    fig, axes = plt.subplots(len(reactions), 1, 
                            figsize=(12, 2 * len(reactions)),
                            sharex=True)
    
    if len(reactions) == 1:
        axes = [axes]
    
    for idx, reaction in enumerate(reactions):
        if reaction in flux_tracker.fluxes:
            fluxes = np.array(flux_tracker.fluxes[reaction])
            axes[idx].plot(times, fluxes, 'b-', linewidth=2)
            axes[idx].set_ylabel(f'{reaction}\n(mM/h)', fontsize=10)
            axes[idx].grid(True, alpha=0.3)
            axes[idx].axhline(y=0, color='k', linestyle='--', alpha=0.5)
            
            # Add statistics
            mean_flux = np.mean(np.abs(fluxes))
            max_flux = np.max(np.abs(fluxes))
            axes[idx].text(0.02, 0.95, f'Mean: {mean_flux:.2e}\nMax: {max_flux:.2e}',
                          transform=axes[idx].transAxes,
                          verticalalignment='top',
                          bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                          fontsize=8)
        else:
            axes[idx].text(0.5, 0.5, f'{reaction} - No data',
                          transform=axes[idx].transAxes,
                          ha='center', va='center')
    
    axes[-1].set_xlabel('Time (hours)', fontsize=12)
    fig.suptitle(f'{pathway} - Reaction Fluxes', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_flux_heatmap(flux_tracker: FluxTracker, save_path: str,
                     max_reactions: int = 50):
    """
    Create a heatmap of all fluxes over time.
    
    Parameters:
    -----------
    flux_tracker : FluxTracker
        Object containing flux data
    save_path : str
        Path to save the heatmap
    max_reactions : int
        Maximum number of reactions to display
    """
    df = flux_tracker.to_dataframe()
    
    # Select top reactions by variance
    variances = df.var().sort_values(ascending=False)
    top_reactions = variances.head(max_reactions).index.tolist()
    df_subset = df[top_reactions]
    
    # Normalize for better visualization
    df_normalized = (df_subset - df_subset.mean()) / (df_subset.std() + 1e-10)
    
    fig, ax = plt.subplots(figsize=(16, 12))
    im = ax.imshow(df_normalized.T, aspect='auto', cmap='RdBu_r', 
                   vmin=-3, vmax=3, interpolation='nearest')
    
    # Set ticks
    ax.set_xticks(np.arange(0, len(df_subset), max(1, len(df_subset) // 20)))
    ax.set_xticklabels([f'{df.index[i]:.1f}' for i in range(0, len(df_subset), max(1, len(df_subset) // 20))],
                       rotation=45)
    ax.set_yticks(np.arange(len(top_reactions)))
    ax.set_yticklabels(top_reactions, fontsize=8)
    
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Reactions', fontsize=12)
    ax.set_title(f'Reaction Flux Heatmap (Top {len(top_reactions)} by Variance)\nNormalized (z-scores)', 
                fontsize=14, fontweight='bold')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Normalized Flux (σ)', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_flux_distribution(flux_tracker: FluxTracker, save_path: str,
                          timepoint_idx: int = -1):
    """
    Plot distribution of fluxes at a specific timepoint.
    
    Parameters:
    -----------
    flux_tracker : FluxTracker
        Object containing flux data
    save_path : str
        Path to save the plot
    timepoint_idx : int
        Index of timepoint to analyze (default: -1, last point)
    """
    df = flux_tracker.to_dataframe()
    fluxes_at_time = df.iloc[timepoint_idx]
    time_value = df.index[timepoint_idx]
    
    # Categorize fluxes
    pathways = categorize_reactions()
    pathway_fluxes = {}
    
    for pathway, reactions in pathways.items():
        pathway_flux = []
        for rxn in reactions:
            if rxn in fluxes_at_time:
                pathway_flux.append(abs(fluxes_at_time[rxn]))
        if pathway_flux:
            pathway_fluxes[pathway] = np.sum(pathway_flux)
    
    # Create bar plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Pathway totals
    pathways_sorted = sorted(pathway_fluxes.items(), key=lambda x: x[1], reverse=True)
    names = [p[0] for p in pathways_sorted]
    values = [p[1] for p in pathways_sorted]
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(names)))
    ax1.barh(names, values, color=colors)
    ax1.set_xlabel('Total Absolute Flux (mM/h)', fontsize=12)
    ax1.set_title(f'Pathway Flux Distribution at t={time_value:.1f}h', 
                 fontsize=14, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    
    # Top individual reactions
    top_reactions = fluxes_at_time.abs().sort_values(ascending=False).head(20)
    ax2.barh(range(len(top_reactions)), top_reactions.values, 
            color=plt.cm.viridis(np.linspace(0, 1, len(top_reactions))))
    ax2.set_yticks(range(len(top_reactions)))
    ax2.set_yticklabels(top_reactions.index, fontsize=9)
    ax2.set_xlabel('Absolute Flux (mM/h)', fontsize=12)
    ax2.set_title('Top 20 Individual Reactions', fontsize=12, fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()


def generate_all_flux_plots(flux_tracker: FluxTracker, output_dir: str):
    """
    Generate comprehensive flux visualization plots.
    
    Parameters:
    -----------
    flux_tracker : FluxTracker
        Object containing flux data
    output_dir : str
        Directory to save all plots
    """
    flux_dir = Path(output_dir) / 'fluxes'
    flux_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print("GENERATING FLUX VISUALIZATIONS")
    print(f"{'='*60}")
    
    # Save flux data to CSV
    csv_path = flux_dir / 'reaction_fluxes.csv'
    flux_tracker.save_to_csv(str(csv_path))
    
    # Get pathway categories
    pathways = categorize_reactions()
    
    # Plot each pathway
    print("\n[INFO] Generating pathway-specific plots...")
    for pathway, reactions in pathways.items():
        save_path = flux_dir / f'pathway_{pathway.replace(" ", "_")}.png'
        plot_pathway_fluxes(flux_tracker, pathway, reactions, str(save_path))
        print(f"  [OK] {pathway}")
    
    # Flux heatmap
    print("\n[INFO] Generating flux heatmap...")
    heatmap_path = flux_dir / 'flux_heatmap.png'
    plot_flux_heatmap(flux_tracker, str(heatmap_path))
    print(f"  [OK] Heatmap saved")
    
    # Flux distribution at multiple timepoints
    print("\n[INFO] Generating flux distribution plots...")
    n_timepoints = len(flux_tracker.times)
    for idx, label in [(0, 'initial'), (n_timepoints//2, 'midpoint'), (-1, 'final')]:
        dist_path = flux_dir / f'flux_distribution_{label}.png'
        plot_flux_distribution(flux_tracker, str(dist_path), timepoint_idx=idx)
        print(f"  [OK] Distribution at {label}")
    
    print(f"\n{'='*60}")
    print(f"[OK] All flux plots saved to: {flux_dir}")
    print(f"{'='*60}\n")


def create_flux_pdf_report(flux_tracker: FluxTracker, output_dir: str,
                          filename: str = 'Flux_Analysis_Report.pdf'):
    """
    Create a comprehensive PDF report of all flux analyses.
    
    Parameters:
    -----------
    flux_tracker : FluxTracker
        Object containing flux data
    output_dir : str
        Directory containing flux plots
    filename : str
        Name of output PDF file
    """
    from matplotlib.backends.backend_pdf import PdfPages
    import glob
    
    flux_dir = Path(output_dir) / 'fluxes'
    pdf_path = flux_dir / filename
    
    # Define specific order for plots
    # First: pathway plots, then heatmap, then distributions (initial -> midpoint -> final)
    plot_order = []
    
    # Add pathway plots (alphabetically)
    pathway_files = sorted(glob.glob(str(flux_dir / 'pathway_*.png')))
    plot_order.extend(pathway_files)
    
    # Add heatmap
    heatmap_file = str(flux_dir / 'flux_heatmap.png')
    if Path(heatmap_file).exists():
        plot_order.append(heatmap_file)
    
    # Add flux distributions in specific order: initial -> midpoint -> final
    for dist_label in ['initial', 'midpoint', 'final']:
        dist_file = str(flux_dir / f'flux_distribution_{dist_label}.png')
        if Path(dist_file).exists():
            plot_order.append(dist_file)
    
    if not plot_order:
        print("[WARN] No flux plots found to create PDF")
        return
    
    print(f"\n[INFO] Creating flux analysis PDF report...")
    
    with PdfPages(str(pdf_path)) as pdf:
        for png_file in plot_order:
            fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape
            img = plt.imread(png_file)
            plt.imshow(img)
            plt.axis('off')
            plt.title(Path(png_file).stem.replace('_', ' ').title(), 
                     fontsize=16, fontweight='bold', pad=20)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close()
    
    print(f"[OK] Flux PDF report saved: {pdf_path}")
