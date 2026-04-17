"""
Python visualization module for plotting results of the RBC metabolic model.
This module handles the creation of plots similar to those in the original MATLAB code.
"""
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


def plot_metabolite_results(t, x, model, meta_names1=None, meta_names2=None, 
                           metabolites1=None, metabolites2=None, 
                           tempsexp1=None, tempsexp2=None,
                           save_path="html"):
    """
    Plot the results of the metabolic simulation and compare with experimental data.
    Only plots experimental data for metabolites present in Data_Bordbar_et_al_exp.xlsx
    
    Parameters:
    -----------
    t : numpy.ndarray
        Time points from the simulation
    x : numpy.ndarray
        Solution array where each row is a time point and each column a metabolite
    model : dict
        The metabolic model from parse.py
    meta_names1, meta_names2 : list, optional
        Names of metabolites from experimental data sets
    metabolites1, metabolites2 : numpy.ndarray, optional
        Experimental metabolite data (rows are metabolites, columns are time points)
    tempsexp1, tempsexp2 : numpy.ndarray, optional
        Experimental time points
    save_path : str, optional
        Directory to save the figures
    """
    print(f"Plotting metabolite results for {len(model['metab'])} metabolites")
    if metabolites1 is not None:
        print(f"Experimental data 1 shape: {metabolites1.shape}")
    if metabolites2 is not None:
        print(f"Experimental data 2 shape: {metabolites2.shape}")
    
    # Load available experimental metabolites from Data_Bordbar_et_al_exp.xlsx
    available_exp_metabolites = set()
    try:
        import pandas as pd
        df = pd.read_excel('Data_Bordbar_et_al_exp.xlsx')
        available_exp_metabolites = set(df['Conc / mM'].astype(str).str.strip().str.upper().tolist())
        print(f"Found {len(available_exp_metabolites)} metabolites in Data_Bordbar_et_al_exp.xlsx")
    except Exception as e:
        print(f"Warning: Could not load Data_Bordbar_et_al_exp.xlsx: {e}")
        available_exp_metabolites = set()
    
    # Create save directory if it doesn't exist
    Path(save_path).mkdir(parents=True, exist_ok=True)
    
    # Calculate number of pages needed for plotting
    num_metabolites = len(model['metab'])
    plots_per_page = 9  # 3x3 grid
    num_full_pages = num_metabolites // plots_per_page
    
    # Plot full pages
    for i in range(num_full_pages):
        plt.figure(figsize=(15, 12))
        
        for j in range(plots_per_page):
            idx = i * plots_per_page + j
            plt.subplot(3, 3, j+1)
            
            # Plot simulation results with explicit color and label
            plt.plot(t, x[:, idx], 'b-', linewidth=2, label='Simulation', alpha=0.8)
            plt.xlabel('Time')
            plt.ylabel('Concentration (mM)')
            plt.title(model['metab'][idx])
            plt.grid(True, alpha=0.3)
            
            # Plot experimental data if available
            tempsexp = []
            valexp = []
            
            # Check experimental data set 1
            if meta_names1 is not None and metabolites1 is not None:
                try:
                    # Find matching metabolite in experimental data 1
                    metab_name = model['metab'][idx].lower()
                    match_indices = [k for k, name in enumerate(meta_names1) if name.lower() == metab_name]
                    
                    if match_indices:
                        match_idx1 = match_indices[0]  # Take the first match if multiple
                        if match_idx1 < metabolites1.shape[0]:  # Check bounds
                            tempsexp = tempsexp1
                            valexp = metabolites1[match_idx1, :]
                except Exception as e:
                    print(f"Error processing experimental data 1 for {model['metab'][idx]}: {e}")
            
            # Check experimental data set 2 if needed
            if meta_names2 is not None and metabolites2 is not None and len(valexp) == 0:
                try:
                    # Find matching metabolite in experimental data 2
                    metab_name = model['metab'][idx].lower()
                    match_indices = [k for k, name in enumerate(meta_names2) if name.lower() == metab_name]
                    
                    if match_indices:
                        match_idx2 = match_indices[0]  # Take the first match if multiple
                        if match_idx2 < metabolites2.shape[0]:  # Check bounds
                            tempsexp = tempsexp2
                            valexp = metabolites2[match_idx2, :]
                except Exception as e:
                    print(f"Error processing experimental data 2 for {model['metab'][idx]}: {e}")
            
            # Plot experimental points if found
            if len(tempsexp) > 0 and len(valexp) > 0:
                plt.plot(tempsexp, valexp, 'r+', markersize=8, label='Experimental', markeredgewidth=2)
            
            # Add legend if both simulation and experimental data exist
            if len(tempsexp) > 0 and len(valexp) > 0:
                plt.legend(fontsize=8)
        
        plt.tight_layout()
        plt.savefig(f"{save_path}/metabolites_page_{i+1}.png")
        plt.close()
    
    # Plot remaining metabolites
    remaining = num_metabolites - num_full_pages * plots_per_page
    if remaining > 0:
        plt.figure(figsize=(15, 12))
        
        for i in range(remaining):
            idx = num_full_pages * plots_per_page + i
            plt.subplot(3, 3, i+1)
            
            # Plot simulation results with explicit color and label
            plt.plot(t, x[:, idx], 'b-', linewidth=2, label='Simulation', alpha=0.8)
            plt.xlabel('Time')
            plt.ylabel('Concentration (mM)')
            plt.title(model['metab'][idx])
            plt.grid(True, alpha=0.3)
            
            # Plot experimental data if available
            tempsexp = []
            valexp = []
            
            # Check experimental data set 1
            if meta_names1 is not None and metabolites1 is not None:
                try:
                    # Find matching metabolite in experimental data 1
                    metab_name = model['metab'][idx].lower()
                    match_indices = [k for k, name in enumerate(meta_names1) if name.lower() == metab_name]
                    
                    if match_indices:
                        match_idx1 = match_indices[0]  # Take the first match if multiple
                        if match_idx1 < metabolites1.shape[0]:  # Check bounds
                            tempsexp = tempsexp1
                            valexp = metabolites1[match_idx1, :]
                except Exception as e:
                    print(f"Error processing experimental data 1 for {model['metab'][idx]}: {e}")
            
            # Check experimental data set 2 if needed
            if meta_names2 is not None and metabolites2 is not None and len(valexp) == 0:
                try:
                    # Find matching metabolite in experimental data 2
                    metab_name = model['metab'][idx].lower()
                    match_indices = [k for k, name in enumerate(meta_names2) if name.lower() == metab_name]
                    
                    if match_indices:
                        match_idx2 = match_indices[0]  # Take the first match if multiple
                        if match_idx2 < metabolites2.shape[0]:  # Check bounds
                            tempsexp = tempsexp2
                            valexp = metabolites2[match_idx2, :]
                except Exception as e:
                    print(f"Error processing experimental data 2 for {model['metab'][idx]}: {e}")
            
            # Plot experimental points if found
            if len(tempsexp) > 0 and len(valexp) > 0:
                plt.plot(tempsexp, valexp, 'r+', markersize=8, label='Experimental', markeredgewidth=2)
            
            # Add legend if both simulation and experimental data exist
            if len(tempsexp) > 0 and len(valexp) > 0:
                plt.legend(fontsize=8)
        
        # Hide empty subplots
        for i in range(remaining, 9):
            plt.subplot(3, 3, i+1)
            plt.axis('off')
        
        plt.tight_layout()
        plt.savefig(f"{save_path}/metabolites_page_{num_full_pages+1}.png")
        plt.close()
    
    # Create a dedicated pH plot
    plot_ph_results(t, x, save_path)


def plot_ph_results(t, x, save_path="html"):
    """
    Plot intracellular pH (pHi) and extracellular pH (pHe) over time.
    
    Parameters:
    -----------
    t : numpy.ndarray
        Time points from the simulation
    x : numpy.ndarray
        Solution array where each row is a time point and each column a metabolite
    save_path : str, optional
        Directory to save the pH figure
    """
    # Create figure with improved layout
    fig = plt.figure(figsize=(14, 10))
    
    # DEBUG: Print x shape and pH values
    print(f"\n{'='*60}")
    print(f"DEBUG pH PLOT (visualization.py) - x.shape: {x.shape}")
    print(f"{'='*60}")
    
    # Extract dynamic pH values from simulation results
    from equadiff_brodbar import PHI_INDEX, PHE_INDEX, NUM_TOTAL_METABOLITES
    if x.shape[1] > PHE_INDEX:
        # Both pHi and pHe are tracked
        pH_intra = x[:, PHI_INDEX]  # pHi (intracellular)
        pH_extra = x[:, PHE_INDEX]  # pHe (extracellular) - DYNAMIC!
        print(f"[OK] Using {x.shape[1]} metabolites (pHi + pHe tracked)")
        print(f"  pHi range: {np.min(pH_intra):.3f} - {np.max(pH_intra):.3f}")
        print(f"  pHe range: {np.min(pH_extra):.3f} - {np.max(pH_extra):.3f}")
        print(f"  pHi[0]={pH_intra[0]:.3f}, pHi[-1]={pH_intra[-1]:.3f}")
        print(f"  pHe[0]={pH_extra[0]:.3f}, pHe[-1]={pH_extra[-1]:.3f}")
    elif x.shape[1] > PHI_INDEX:
        # Only pHi tracked
        pH_intra = x[:, PHI_INDEX]
        pH_extra = 7.4 * np.ones_like(t)  # Fallback to constant
    else:
        # Old model without pH tracking
        pH_intra = 7.2 * np.ones_like(t)
        pH_extra = 7.4 * np.ones_like(t)
    
    delta_pH = pH_extra - pH_intra
    
    # Create subplot for pH values (top panel)
    ax1 = plt.subplot(3, 1, 1)
    plt.plot(t, pH_intra, 'b-', linewidth=3, label='Intracellular pH (pHi)', marker='o', markersize=4, markevery=5)
    plt.plot(t, pH_extra, 'r-', linewidth=3, label='Extracellular pH (pHe)', marker='s', markersize=4, markevery=5)
    
    # Detect pH perturbation (if pHe varies more than 0.05)
    pHe_variation = np.max(pH_extra) - np.min(pH_extra)
    if pHe_variation > 0.05:
        # Mark perturbation region
        pHe_start_idx = np.where(np.abs(pH_extra - pH_extra[0]) > 0.01)[0]
        if len(pHe_start_idx) > 0:
            t_start = t[pHe_start_idx[0]]
            t_end = t[-1]
            ax1.axvspan(t_start, t_end, alpha=0.2, color='yellow', label='pH Perturbation')
            ax1.axvline(t_start, color='orange', linestyle='--', linewidth=2, alpha=0.7, label=f'Start t={t_start:.1f}h')
    
    plt.xlabel('Time (hours)', fontsize=12)
    plt.ylabel('pH', fontsize=12)
    plt.title('Intracellular and Extracellular pH Over Time', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10, loc='best')
    plt.grid(True, alpha=0.3)
    
    # Dynamic ylim based on actual pH range
    pH_min = min(np.min(pH_intra), np.min(pH_extra)) - 0.1
    pH_max = max(np.max(pH_intra), np.max(pH_extra)) + 0.1
    plt.ylim(pH_min, pH_max)
    ax1.tick_params(axis='both', which='major', labelsize=10)
    
    # Create subplot for pH difference (middle panel)
    ax2 = plt.subplot(3, 1, 2)
    plt.plot(t, delta_pH, 'g-', linewidth=3, label='ΔpH (pHe - pHi)')
    plt.xlabel('Time (hours)', fontsize=12)
    plt.ylabel('ΔpH', fontsize=12)
    plt.title('pH Gradient Across Cell Membrane', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11, loc='upper right')
    plt.grid(True, alpha=0.3)
    ax2.tick_params(axis='both', which='major', labelsize=10)
    
    # Create text analysis panel (bottom panel)
    ax3 = plt.subplot(3, 1, 3)
    ax3.axis('off')  # Hide axes for text panel
    
    # Detect pH perturbation type
    pHe_variation = np.max(pH_extra) - np.min(pH_extra)
    pHi_variation = np.max(pH_intra) - np.min(pH_intra)
    
    if pHe_variation > 0.05:
        if pH_extra[-1] > pH_extra[0] + 0.05:
            perturbation_type = "ALKALOSIS"
        elif pH_extra[-1] < pH_extra[0] - 0.05:
            perturbation_type = "ACIDOSIS"
        else:
            perturbation_type = "pH MODULATION"
    else:
        perturbation_type = "NO PERTURBATION (Control)"
    
    # Calculate response metrics
    pHi_change = pH_intra[-1] - pH_intra[0]
    pHe_change = pH_extra[-1] - pH_extra[0]
    
    # Add comprehensive analysis text in a structured format
    analysis_text = f"""pH ANALYSIS SUMMARY

PERTURBATION TYPE: {perturbation_type}

Quantitative Results:
• Intracellular pH (pHi):  {pH_intra[0]:.3f} → {pH_intra[-1]:.3f} (Δ = {pHi_change:+.3f})
• Extracellular pH (pHe):  {pH_extra[0]:.3f} → {pH_extra[-1]:.3f} (Δ = {pHe_change:+.3f})
• pH Gradient (ΔpH):       {delta_pH[0]:.3f} → {delta_pH[-1]:.3f} (Δ = {delta_pH[-1] - delta_pH[0]:+.3f})
• pHi Range: {np.min(pH_intra):.3f} - {np.max(pH_intra):.3f}
• pHe Range: {np.min(pH_extra):.3f} - {np.max(pH_extra):.3f}

Physiological Interpretation:
• pHi responds to pHe changes via H+ transport (NHE, Band 3, diffusion)
• Intracellular buffering (β = 70 mM/pH) moderates pHi changes
• pH gradient drives ion transport and metabolic regulation
• Enzyme activities modulated by pH (14 pH-sensitive enzymes)
• 2,3-BPG synthesis affected (VDPGM highly pH-sensitive)"""
    
    # Position text in the bottom panel with better formatting
    ax3.text(0.05, 0.95, analysis_text, transform=ax3.transAxes, 
             fontsize=11, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
    
    # Adjust layout to prevent overlap
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.4)  # Add space between subplots
    
    # Save with high quality
    plt.savefig(f"{save_path}/pH_analysis.png", dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    print(f"pH analysis plot saved to {save_path}/pH_analysis.png")


def export_to_pdf(save_path="html", output_filename="Results_Metabolic_Model.pdf", data_source="Bardyn"):
    """
    Combine multiple PNG figures into a single PDF with proper styling.
    
    Parameters:
    -----------
    save_path : str, optional
        Directory with PNG figures
    output_filename : str, optional
        Name of the output PDF file
    data_source : str, optional
        Name of the data source (e.g., 'Bardyn', 'Brodbar')
    """
    try:
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.image as mpimg
        from datetime import datetime
        
        # List all PNG files in proper order
        png_files = sorted([f for f in Path(save_path).glob("*.png")])
        
        if not png_files:
            print(f"No PNG files found in {save_path}")
            return
        
        output_path = Path(save_path) / output_filename
        
        # Create PDF with metadata that matches the Bardyn PDF style
        with PdfPages(str(output_path)) as pdf:
            # Add metadata to match the original PDF
            d = pdf.infodict()
            d['Title'] = f'Results of Metabolic Model - {data_source} Data'
            d['Author'] = 'Jorgelindo da Veiga - Python RBC Metabolic Model'
            d['Subject'] = 'Metabolite simulation results'
            d['Keywords'] = 'metabolites, simulation, RBC model, Jorgelindo da Veiga'
            d['CreationDate'] = datetime.now()
            d['ModDate'] = datetime.now()
            
            # Create a title page
            plt.figure(figsize=(11.69, 8.27))  # A4 size in inches
            plt.text(0.5, 0.7, f'Results of Metabolic Model Simulation', 
                    horizontalalignment='center', fontsize=24, fontweight='bold')
            plt.text(0.5, 0.6, f'{data_source} Data', 
                    horizontalalignment='center', fontsize=20)
            plt.text(0.5, 0.5, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                    horizontalalignment='center', fontsize=14)
            plt.text(0.5, 0.3, 'Python Implementation of the RBC Metabolic Model', 
                    horizontalalignment='center', fontsize=16, fontstyle='italic')
            
            # Add author name
            plt.text(0.5, 0.2, 'Implemented by Jorgelindo da Veiga',
                    horizontalalignment='center', fontsize=14)
            
            # Add a footer with citation information
            plt.text(0.5, 0.1, 'Based on the original MATLAB implementation', 
                    horizontalalignment='center', fontsize=10)
            plt.axis('off')
            pdf.savefig()
            plt.close()
            
            # Add each image to the PDF
            for png_file in png_files:
                # Read PNG
                img = mpimg.imread(png_file)
                
                # Create a figure with appropriate size
                # The division factor is adjusted to fit A4 page nicely
                plt.figure(figsize=(11.69, 8.27))  # A4 size in inches
                
                # Display the image with proper scaling
                plt.imshow(img)
                plt.axis('off')
                
                # Add page number in the footer
                try:
                    # Extract page number from metabolite page files
                    if 'metabolites_page_' in png_file.stem:
                        page_num = int(''.join(filter(str.isdigit, png_file.stem.split('_')[-1])))
                        plt.figtext(0.5, 0.02, f'Page {page_num}', 
                                  horizontalalignment='center', fontsize=8)
                    elif 'pH_analysis' in png_file.stem:
                        plt.figtext(0.5, 0.02, 'pH Analysis', 
                                  horizontalalignment='center', fontsize=8)
                    else:
                        # Generic page numbering for other files
                        plt.figtext(0.5, 0.02, f'{png_file.stem}', 
                                  horizontalalignment='center', fontsize=8)
                except ValueError:
                    # Fallback for files without numeric page numbers
                    plt.figtext(0.5, 0.02, f'{png_file.stem}', 
                              horizontalalignment='center', fontsize=8)
                
                # Add to PDF with proper page margins
                pdf.savefig(bbox_inches='tight', pad_inches=0.25)
                plt.close()
        
        print(f"PDF saved to {output_path}")
        return str(output_path)
    
    except ImportError as e:
        print(f"Could not create PDF. Required packages not installed: {e}")
        print("Install matplotlib with: pip install matplotlib")
        return None


if __name__ == "__main__":
    # Example usage
    import os
    import numpy as np
    from parse import parse
    from parse_initial_conditions import parse_initial_conditions
    from solver import solver
    
    # Load model
    model = parse(os.path.join("RBC", "Rxn_RBC.txt"))
    
    if model:
        # Create example data
        t = np.linspace(0, 10, 100)
        x = np.random.rand(100, len(model['metab']))
        
        # Plot results
        plot_metabolite_results(t, x, model, save_path="html")
