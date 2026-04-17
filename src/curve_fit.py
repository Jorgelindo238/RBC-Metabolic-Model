"""
Python equivalent of the CurvefitJA.m MATLAB function.
This module handles curve fitting of metabolite data.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning
from pathlib import Path
import warnings

# Filter warnings to keep output clean
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=OptimizeWarning)


def polynomial_log_model(x, a, b, c, d, e):
    """
    Model function used for curve fitting metabolite data.
    Equivalent to MATLAB: b(1)+b(2).*x+b(3).*x.^2+b(4).*x.^3+b(5).*log(x)
    
    Parameters:
    -----------
    x : array-like
        The independent variable (time points)
    a, b, c, d, e : float
        The parameters to be optimized
        
    Returns:
    --------
    array-like
        The model output (concentration values)
    """
    # Simple implementation, directly matching the MATLAB version
    # The max function ensures we don't take log of zero or negative numbers
    x_safe = np.maximum(x, 1e-10)
    return a + b * x + c * x**2 + d * x**3 + e * np.log(x_safe)


def calculate_derivative(x, b, c, d, e):
    """
    Calculate the analytical derivative of the polynomial_log_model.
    
    Parameters:
    -----------
    x : array-like
        The independent variable (time points)
    b, c, d, e : float
        The model parameters (excluding the constant term 'a')
    
    Returns:
    --------
    array-like
        The derivative values at the given time points
    """
    # Handle edge cases for the logarithm term
    x_safe = np.maximum(x, 1e-10)  # Prevent division by zero
    
    # The derivative of a + b*x + c*x^2 + d*x^3 + e*log(x) is:
    # b + 2*c*x + 3*d*x^2 + e/x
    return b + 2 * c * x + 3 * d * x**2 + e / x_safe


def curve_fit_ja(data_file_name, option=None, max_metabolites=None, selected_metabolites=None, verbose=True):
    """
    Python equivalent of the CurvefitJA MATLAB function.
    Uses a simpler, more robust implementation that works better with the data.
    
    Parameters:
    -----------
    data_file_name : str
        Name of the Excel file containing the metabolite data
    option : str, optional
        Option flag, set to "no" to skip plotting
    max_metabolites : int, optional
        Maximum number of metabolites to process (for testing)
    selected_metabolites : list, optional
        List of specific metabolite names to process (for testing)
    verbose : bool, optional
        Whether to print detailed output during processing
        
    Returns:
    --------
    meta_names : list
        List of metabolite names
    metabolites : numpy.ndarray
        Array of metabolite data
    matricepara : numpy.ndarray
        Array of curve fit parameters
    tempsexp : numpy.ndarray
        Array of experimental time points
    """
    if verbose:
        print(f"Processing data file: {data_file_name}")
    
    # Load data from Excel file
    file_path = Path(data_file_name)
    if not file_path.exists():
        # Try adding extensions if not provided
        for ext in ['.xlsx', '.xls']:
            if Path(str(file_path) + ext).exists():
                file_path = Path(str(file_path) + ext)
                if verbose:
                    print(f"Found file: {file_path}")
                break
    
    if not file_path.exists():
        print(f"Error: File {data_file_name} not found")
        return None, None, None, None
    
    # Read the Excel file
    try:
        data = pd.read_excel(file_path)
        if verbose:
            print(f"Successfully read data with shape: {data.shape}")
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None, None, None, None
    
    # The data is structured with metabolites in rows and time points in columns
    # First column contains metabolite names and remaining columns contain time series data
    # Column headers (except first) are time points
    
    # Check if data has expected structure
    if data.shape[1] < 2 or data.shape[0] < 1:
        print(f"Error: Unexpected data shape: {data.shape}")
        return None, None, None, None
    
    # Extract metabolite names from the first column
    meta_names = data.iloc[:, 0].values.tolist()
    if verbose:
        print(f"Found {len(meta_names)} metabolites")
    
    try:
        # Extract time points from column headers (skip the first one which is usually 'Conc / mM')
        tempsexp = np.array([float(col) for col in data.columns[1:]], dtype=np.float64)
        if verbose:
            print(f"Time points: {tempsexp}")
    except ValueError as e:
        print(f"Error converting column headers to time points: {e}")
        print(f"Column headers: {data.columns[1:]}")
        return None, None, None, None
        
    # Get the data values (metabolite concentrations over time)
    try:
        # Each row is a different metabolite, each column is a different time point
        # We need to reshape this for our algorithm
        values = data.iloc[:, 1:].values
        
        # Ensure all values are numeric
        values = values.astype(np.float64)
        
        # We want to organize by time point, so we transpose
        # After transpose: each row is a time point, each column is a metabolite
        metabolites = values  # Keep original orientation for now
        
        if verbose:
            print(f"Metabolite data shape: {metabolites.shape}")
    except Exception as e:
        print(f"Error processing metabolite data: {e}")
        return None, None, None, None
    
    # Filter metabolites if subset selection is requested
    meta_indices = list(range(metabolites.shape[0]))  # Default: all metabolites
    if selected_metabolites is not None:
        # Filter by specific metabolite names
        selected_indices = []
        # Keep track of metabolites we've already matched to avoid duplicates
        processed_metabolites = set()
        
        for name in selected_metabolites:
            # Convert to lowercase for case-insensitive matching
            name_lower = name.lower()
            
            # Find all matching metabolites (there could be multiple with same name)
            all_matches = [(i, meta_name.lower()) 
                           for i, meta_name in enumerate(meta_names) 
                           if meta_name.lower() == name_lower]
            
            # Filter out any metabolites we've already processed
            matches = [i for i, lower_name in all_matches 
                      if lower_name not in processed_metabolites]
            
            if matches:
                # Just take the first match for each requested metabolite
                idx = matches[0]
                selected_indices.append(idx)
                processed_metabolites.add(meta_names[idx].lower())
                if verbose:
                    print(f"Found metabolite '{name}' at index {idx}: {meta_names[idx]}")
            else:
                if verbose:
                    print(f"Warning: Metabolite '{name}' not found or already selected")
        
        if selected_indices:
            meta_indices = selected_indices
            print(f"Processing {len(meta_indices)} selected metabolites: {[meta_names[i] for i in meta_indices]}")
        else:
            print("No requested metabolites found, processing all metabolites")
    elif max_metabolites is not None:
        # Limit to max_metabolites (for testing)
        meta_indices = list(range(min(max_metabolites, metabolites.shape[0])))
        if verbose:
            print(f"Processing first {len(meta_indices)} metabolites for testing")
    
    # Prepare arrays for storing model parameters and fitted values
    num_total_metabolites = metabolites.shape[0]  # Total number in the file
    num_metabolites = len(meta_indices)           # Number to process
    
    # Create arrays for all metabolites, but we'll only process the selected ones
    matricepara = np.zeros((num_total_metabolites, 5))  # 5 parameters per model
    matricepara.fill(np.nan)  # Initialize with NaN
    
    # Track warnings and fitting issues
    neg_warnings_count = 0  # Count of metabolites with negative value issues
    
    # Dense time points for smooth curve plotting
    time = np.linspace(1, tempsexp[-1], 100)
    
    # Arrays to store model values and derivatives
    val_model = np.zeros((len(time), num_total_metabolites))
    deriv = np.zeros((len(time), num_total_metabolites))
    
    # Perform curve fitting for each selected metabolite
    for idx, i in enumerate(meta_indices):
        # Get data for this metabolite across all time points
        y = metabolites[i, :]
        
        # Skip if not enough data points for fitting
        if len(tempsexp) < 3 or len(y) < 3:
            print(f"Warning: Not enough data points for metabolite {meta_names[i]} - skipping")
            matricepara[i, :] = np.nan
            continue
            
        # Skip zero or negative time points (needed for log model)
        valid_indices = tempsexp > 0
        if not np.any(valid_indices):
            print(f"Warning: No positive time points for metabolite {meta_names[i]} - skipping")
            matricepara[i, :] = np.nan
            continue
            
        # Use only positive time points for fitting
        valid_tempsexp = tempsexp[valid_indices]
        valid_y = y[valid_indices]
        
        # Simple initial parameters that worked in previous version
        beta0 = [valid_y[0], 0, 0, 0, 0]
            
        if idx == 0 and verbose:
            print("\nStarting curve fitting for selected metabolites...")
        
        # Print a status update for each metabolite only in verbose mode
        if verbose:
            # Format: clear the line and print the status message
            print(f"\rProcessing: {idx+1}/{num_metabolites} - {meta_names[i]:<30}", end="")
        
        # For first few metabolites, print detailed info on separate lines
        if idx < 3 and verbose:  # Only for first 3 metabolites and only when verbose
            print("\n")  # Move to next line with some space
            print(f"  Metabolite {idx+1}/{num_metabolites}: {meta_names[i]}")
            print(f"  - Initial guess: [{beta0[0]:.4f}, {beta0[1]:.4f}, {beta0[2]:.4f}, {beta0[3]:.4f}, {beta0[4]:.4f}]")
            
        # Use the original simple curve fitting approach that worked well
        try:
            # Fit using the default method without bounds
            params, pcov = curve_fit(polynomial_log_model, valid_tempsexp, valid_y, 
                                p0=beta0, maxfev=10000)
            
            # Calculate fit quality (R-squared)
            model_pred = polynomial_log_model(valid_tempsexp, *params)
            r_squared = 1.0
            if np.sum((valid_y - np.mean(valid_y))**2) > 0:  # Avoid division by zero
                r_squared = 1 - np.sum((valid_y - model_pred)**2) / np.sum((valid_y - np.mean(valid_y))**2)
            
            if idx < 3 and verbose:  # Only print detailed info for first 3 metabolites
                print(f"  - Fit quality R²: {r_squared:.4f}")
                print(f"  - Final params: [{params[0]:.4f}, {params[1]:.4f}, {params[2]:.4f}, {params[3]:.4f}, {params[4]:.4f}]")
                print("")
            elif verbose:
                # Just print a dot to show progress for other metabolites
                print(".", end="", flush=True)
                
        except Exception as e:
            if verbose:
                print(f"\nError fitting {meta_names[i]}: {e}")
            # Just set parameters to NaN on failure
            params = np.array([np.nan, np.nan, np.nan, np.nan, np.nan])
            matricepara[i, :] = params
            continue
        # Calculate model values for plotting
        val = polynomial_log_model(time, *params)
        
        # Ensure no negative values (adjust constant term if needed)
        neg_count = 0
        while np.any(val < 0) and neg_count < 1000:
            params[0] += 1e-6
            val = polynomial_log_model(time, *params)
            neg_count += 1
        
        if neg_count >= 1000:
            if idx < 3 and verbose:  # Only print for first 3 metabolites when verbose
                print(f"  - Warning: Could not eliminate negative values")
            neg_warnings_count = neg_warnings_count + 1
        
        # Store results
        val_model[:, i] = val
        
        # Calculate derivatives using the dedicated function
        deriv[:, i] = calculate_derivative(time, params[1], params[2], params[3], params[4])
        
        # Store parameters
        matricepara[i, :] = params
    
    # Print a summary of the fitting process
    print("\n" + "-"*50)
    print(f"Curve fitting completed for {num_metabolites} metabolites")
    if neg_warnings_count > 0:
        print(f"Warnings: Could not eliminate negative values for {neg_warnings_count} metabolites")
    
    # Calculate overall fit quality
    non_nan_count = np.sum(~np.isnan(matricepara[:, 0]))
    success_rate = (non_nan_count / num_metabolites) * 100
    print(f"Successful fits: {non_nan_count}/{num_metabolites} ({success_rate:.1f}%)")
    print("-"*50)
    
    # Generate plots if option is not "no"
    if option != "no":
        print(f"Generating plots for {num_metabolites} metabolites...")
        plot_results(time, tempsexp, metabolites, val_model, deriv, meta_names)
        print(f"Plots saved to the 'html' directory")
    
    return meta_names, metabolites, matricepara, tempsexp


def plot_results(time, tempsexp, metabolites, val_model, deriv, meta_names):
    """
    Plot the results of curve fitting with styling to match the Bardyn PDF.
    
    Parameters:
    -----------
    time : numpy.ndarray
        Time points for model evaluation
    tempsexp : numpy.ndarray
        Experimental time points
    metabolites : numpy.ndarray
        Experimental metabolite data (each row is a metabolite, each column is a time point)
    val_model : numpy.ndarray
        Model predictions (rows are time points, columns are metabolites)
    deriv : numpy.ndarray
        Model derivatives (rows are time points, columns are metabolites)
    meta_names : list
        Metabolite names
    """
    num_metabolites = metabolites.shape[0]  # Number of rows (metabolites)
    
    # Create output directory if it doesn't exist
    Path('html').mkdir(parents=True, exist_ok=True)
    
    # Set matplotlib style to match the Bardyn PDF
    plt.rcParams.update({
        'font.size': 9,           # Smaller font size as in the PDF
        'lines.linewidth': 1.5,   # Slightly thicker lines
        'axes.titlesize': 11,     # Title size
        'axes.labelsize': 9,      # Axis label size
        'xtick.labelsize': 8,     # X-tick label size
        'ytick.labelsize': 8,     # Y-tick label size
        'legend.fontsize': 8,     # Legend font size
        'figure.figsize': (15, 10)  # Figure size
    })
    
    # Calculate number of pages needed for plotting (9 plots per page)
    num_full_pages = num_metabolites // 9
    remaining = num_metabolites % 9
    
    # Plot full pages
    for j in range(num_full_pages):
        fig, axs = plt.subplots(3, 3, figsize=(15, 10))
        axs = axs.flatten()
        
        for i in range(9):
            idx = j * 9 + i
            ax = axs[i]
            
            if idx < num_metabolites:
                # Calculate appropriate y-axis range for the derivative
                deriv_max = np.max(np.abs(deriv[:, idx]))
                deriv_scale = 10 ** np.floor(np.log10(deriv_max)) if deriv_max > 0 else 1
                
                # Primary y-axis: Concentration
                # Plot experimental points
                ax.plot(tempsexp, metabolites[idx, :], '*r', markersize=6, label='Pts Exp.')
                
                # Plot model curve
                ax.plot(time, val_model[:, idx], 'b-', linewidth=1.5, label='Val. modèle')
                
                # Set x-axis limit to match PDF (starting from 0)
                ax.set_xlim([0, np.max(time)])
                
                # Secondary y-axis: Derivative
                ax2 = ax.twinx()
                
                # Plot derivative as dotted line
                ax2.plot(time, deriv[:, idx], 'k:', linewidth=1.2, label='dM/dt (Axe secondaire)')
                
                # Set axes labels and title
                ax.set_xlabel('Time (days)')
                ax.set_title(meta_names[idx], fontweight='bold')
                
                # Add scientific notation for the secondary y-axis if needed
                if deriv_scale != 1:
                    ax2.yaxis.set_major_formatter(plt.FuncFormatter(
                        lambda x, pos: f'{x/deriv_scale:.1f}'))
                    ax2.set_title(f'×10$^{{{int(np.log10(deriv_scale))}}}$', 
                                  loc='right', fontsize=8, color='grey')
                    
                # Remove y-axis label to match the PDF style
                ax.set_ylabel('')
                ax2.set_ylabel('')
                
                # Add grid lines (light grey) to match the PDF
                ax.grid(True, linestyle=':', alpha=0.3, color='grey')
            else:
                ax.axis('off')  # Hide if beyond number of metabolites
        
        # Add common legend to the figure, outside plots, similar to the PDF
        legend_items = [
            plt.Line2D([0], [0], color='r', marker='*', linestyle='', markersize=6, label='Pts Exp.'),
            plt.Line2D([0], [0], color='b', linestyle='-', linewidth=1.5, label='Val. modèle'),
            plt.Line2D([0], [0], color='k', linestyle=':', linewidth=1.2, label='dM/dt')
        ]
        fig.legend(handles=legend_items, loc='upper right', bbox_to_anchor=(0.98, 0.98))
        
        plt.tight_layout(rect=[0, 0, 0.95, 0.95])
        plt.savefig(f'html/curve_fit_page_{j+1}.png', dpi=300)
    
    # Plot remaining metabolites
    if remaining > 0:
        fig, axs = plt.subplots(3, 3, figsize=(15, 10))
        axs = axs.flatten()
        
        for i in range(9):  # Always loop through all subplot positions
            ax = axs[i]
            
            if i < remaining:
                idx = num_full_pages * 9 + i
                
                # Calculate appropriate y-axis range for the derivative
                deriv_max = np.max(np.abs(deriv[:, idx]))
                deriv_scale = 10 ** np.floor(np.log10(deriv_max)) if deriv_max > 0 else 1
                
                # Primary y-axis: Concentration
                # Plot experimental points
                ax.plot(tempsexp, metabolites[idx, :], '*r', markersize=6, label='Pts Exp.')
                
                # Plot model curve
                ax.plot(time, val_model[:, idx], 'b-', linewidth=1.5, label='Val. modèle')
                
                # Set x-axis limit to match PDF (starting from 0)
                ax.set_xlim([0, np.max(time)])
                
                # Secondary y-axis: Derivative
                ax2 = ax.twinx()
                
                # Plot derivative as dotted line
                ax2.plot(time, deriv[:, idx], 'k:', linewidth=1.2, label='dM/dt (Axe secondaire)')
                
                # Set axes labels and title
                ax.set_xlabel('Time (days)')
                ax.set_title(meta_names[idx], fontweight='bold')
                
                # Add scientific notation for the secondary y-axis if needed
                if deriv_scale != 1:
                    ax2.yaxis.set_major_formatter(plt.FuncFormatter(
                        lambda x, pos: f'{x/deriv_scale:.1f}'))
                    ax2.set_title(f'×10$^{{{int(np.log10(deriv_scale))}}}$', 
                                  loc='right', fontsize=8, color='grey')
                    
                # Remove y-axis label to match the PDF style
                ax.set_ylabel('')
                ax2.set_ylabel('')
                
                # Add grid lines (light grey) to match the PDF
                ax.grid(True, linestyle=':', alpha=0.3, color='grey')
            else:
                ax.axis('off')  # Hide unused subplots
        
        # Add common legend
        legend_items = [
            plt.Line2D([0], [0], color='r', marker='*', linestyle='', markersize=6, label='Pts Exp.'),
            plt.Line2D([0], [0], color='b', linestyle='-', linewidth=1.5, label='Val. modèle'),
            plt.Line2D([0], [0], color='k', linestyle=':', linewidth=1.2, label='dM/dt')
        ]
        fig.legend(handles=legend_items, loc='upper right', bbox_to_anchor=(0.98, 0.98))
        
        plt.tight_layout(rect=[0, 0, 0.95, 0.95])
        plt.savefig(f'html/curve_fit_page_{num_full_pages+1}.png', dpi=300)
    
    plt.close('all')


def export_to_pdf(save_path="html", output_filename="Results_Curvefit_Bardyn.pdf", data_source="Bardyn"):
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
        png_files = sorted([f for f in Path(save_path).glob("curve_fit_page_*.png")])
        
        if not png_files:
            print(f"No PNG files found in {save_path}")
            return
        
        output_path = Path(save_path) / output_filename
        
        # Create PDF with metadata that matches the Bardyn PDF style
        with PdfPages(str(output_path)) as pdf:
            # Add metadata to match the original PDF
            d = pdf.infodict()
            d['Title'] = f'Results of Curve Fitting - {data_source} Data'
            d['Author'] = 'Jorgelindo da Veiga - Python RBC Metabolic Model'
            d['Subject'] = 'Metabolite curve fitting results'
            d['Keywords'] = 'metabolites, curve fitting, RBC model, Jorgelindo da Veiga'
            d['CreationDate'] = datetime.now()
            d['ModDate'] = datetime.now()
            
            # Create a title page
            plt.figure(figsize=(11.69, 8.27))  # A4 size in inches
            plt.text(0.5, 0.7, f'Results of Curve Fitting', 
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
                page_num = int(png_file.stem.split('_')[-1])
                plt.figtext(0.5, 0.02, f'Page {page_num}', 
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


def compare_datasets(data_bardyn="Data_Bardyn_et_al_ctrl", data_brodbar="Data_Bordbar_et_al_exp", 
                  selected_metabolites=None, max_metabolites=None, generate_plots=True, verbose=False):
    """
    Process both Bardyn and Brodbar datasets and compare the results.
    
    Parameters:
    -----------
    data_bardyn : str
        Bardyn dataset filename
    data_brodbar : str
        Brodbar dataset filename
    selected_metabolites : list
        List of metabolites to process
    max_metabolites : int
        Maximum number of metabolites to process
    generate_plots : bool
        Whether to generate plots
    """
    print("\n" + "="*50)
    print("Comparing Bardyn and Brodbar datasets")
    print("="*50)
    
    # Clear the screen of any previous output to prevent formatting issues
    print("\n" * 2)  # Add extra spacing
    print("1. Processing Bardyn dataset...")
    meta_names_bardyn, metabolites_bardyn, matricepara_bardyn, tempsexp_bardyn = curve_fit_ja(
        data_bardyn,
        option="no" if not generate_plots else None,
        max_metabolites=max_metabolites,
        selected_metabolites=selected_metabolites,
        verbose=verbose
    )
    
    # Add clear spacing between datasets
    print("\n" * 3)  # Add extra spacing
    print("2. Processing Brodbar dataset...")
    meta_names_brodbar, metabolites_brodbar, matricepara_brodbar, tempsexp_brodbar = curve_fit_ja(
        data_brodbar,
        option="no" if not generate_plots else None,
        max_metabolites=max_metabolites,
        selected_metabolites=selected_metabolites,
        verbose=verbose
    )
    
    # Count successfully fitted metabolites
    fitted_bardyn = np.sum(~np.isnan(matricepara_bardyn[:, 0]))
    fitted_brodbar = np.sum(~np.isnan(matricepara_brodbar[:, 0]))
    
    print("\n" + "="*50)
    print("Curve Fitting Results Summary")
    print("="*50)
    print(f"Bardyn dataset: {fitted_bardyn} metabolites successfully fitted")
    print(f"Brodbar dataset: {fitted_brodbar} metabolites successfully fitted")
    
    # Find common metabolites between the two datasets
    bardyn_successful = [meta_names_bardyn[i] for i in np.where(~np.isnan(matricepara_bardyn[:, 0]))[0]]
    brodbar_successful = [meta_names_brodbar[i] for i in np.where(~np.isnan(matricepara_brodbar[:, 0]))[0]]
    
    bardyn_successful_lower = [m.lower() for m in bardyn_successful]
    brodbar_successful_lower = [m.lower() for m in brodbar_successful]
    
    common_metabolites = set(bardyn_successful_lower) & set(brodbar_successful_lower)
    
    # Print results with clear separation
    print(f"\nCommon metabolites between datasets: {len(common_metabolites)}/{len(bardyn_successful)} (Bardyn) and {len(common_metabolites)}/{len(brodbar_successful)} (Brodbar)")
    
    # Count metabolites that are in one dataset but not the other
    bardyn_only = set(bardyn_successful_lower) - set(brodbar_successful_lower)
    brodbar_only = set(brodbar_successful_lower) - set(bardyn_successful_lower)
    
    # Print information about unique metabolites
    if len(bardyn_only) > 0:
        print(f"\nMetabolites unique to Bardyn: {len(bardyn_only)}")
        if len(bardyn_only) > 0:
            for i, metabolite in enumerate(sorted(list(bardyn_only))[:3]):  # Show first 3
                print(f"  - {metabolite.upper()}")
    
    if len(brodbar_only) > 0:
        print(f"\nMetabolites unique to Brodbar: {len(brodbar_only)}")
        if len(brodbar_only) > 0:
            for i, metabolite in enumerate(sorted(list(brodbar_only))[:3]):  # Show first 3
                print(f"  - {metabolite.upper()}")
    
    # Print common metabolites information
    if len(common_metabolites) > 0:
        print("\nCommon metabolites (examples): ")
        common_metabolites_list = sorted(list(common_metabolites))
        for i, metabolite in enumerate(common_metabolites_list[:5]):  # Show first 5
            print(f"  - {metabolite.upper()}")
        
        # Compare parameters for common metabolites
        if selected_metabolites is not None and len(selected_metabolites) > 0:
            # Only do detailed comparison when specific metabolites are selected
            print("\nParameter comparison for selected common metabolites:")
            print("-" * 70)
            print(f"{'Metabolite':<10} {'Dataset':<10} {'a':>10} {'b':>10} {'c':>10} {'d':>10} {'e':>10}")
            print("-" * 70)
            
            for metabolite_name in selected_metabolites:
                metabolite_lower = metabolite_name.lower()
                if metabolite_lower in common_metabolites:
                    # Find indices in both datasets
                    bardyn_idx = next((i for i, name in enumerate(meta_names_bardyn) 
                                     if name.lower() == metabolite_lower), None)
                    brodbar_idx = next((i for i, name in enumerate(meta_names_brodbar) 
                                      if name.lower() == metabolite_lower), None)
                    
                    if bardyn_idx is not None and brodbar_idx is not None:
                        # Get parameters
                        bardyn_params = matricepara_bardyn[bardyn_idx]
                        brodbar_params = matricepara_brodbar[brodbar_idx]
                        
                        # Print parameters
                        print(f"{metabolite_name:<10} {'Bardyn':<10} {bardyn_params[0]:10.4f} {bardyn_params[1]:10.4f} {bardyn_params[2]:10.4f} {bardyn_params[3]:10.4f} {bardyn_params[4]:10.4f}")
                        print(f"{'':10} {'Brodbar':<10} {brodbar_params[0]:10.4f} {brodbar_params[1]:10.4f} {brodbar_params[2]:10.4f} {brodbar_params[3]:10.4f} {brodbar_params[4]:10.4f}")
                        
                        # Calculate and print parameter differences
                        diff = brodbar_params - bardyn_params
                        print(f"{'':10} {'Diff':<10} {diff[0]:10.4f} {diff[1]:10.4f} {diff[2]:10.4f} {diff[3]:10.4f} {diff[4]:10.4f}")
                        print("-" * 70)
    
    # Generate PDFs if plots were created
    if generate_plots:
        bardyn_pdf = export_to_pdf(save_path="html", output_filename="Results_Curvefit_Bardyn.pdf", data_source="Bardyn")
        brodbar_pdf = export_to_pdf(save_path="html", output_filename="Results_Curvefit_Brodbar.pdf", data_source="Brodbar")
        
        if bardyn_pdf and brodbar_pdf:
            print("\nPDF results saved:")
            print(f"  - Bardyn results: {bardyn_pdf}")
            print(f"  - Brodbar results: {brodbar_pdf}")
    
    return {
        "bardyn": {
            "meta_names": meta_names_bardyn,
            "metabolites": metabolites_bardyn,
            "matricepara": matricepara_bardyn,
            "tempsexp": tempsexp_bardyn,
            "fitted_count": fitted_bardyn
        },
        "brodbar": {
            "meta_names": meta_names_brodbar,
            "metabolites": metabolites_brodbar,
            "matricepara": matricepara_brodbar,
            "tempsexp": tempsexp_brodbar,
            "fitted_count": fitted_brodbar
        },
        "common_metabolites": common_metabolites
    }


if __name__ == "__main__":
    # Example usage
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='RBC Metabolic Model Curve Fitting')
    parser.add_argument('--data', type=str, default="Data_Bardyn_et_al_ctrl", 
                       help='Input data file (Excel format)')
    parser.add_argument('--no-plots', action='store_true', 
                       help='Skip generating plots')
    parser.add_argument('--no-pdf', action='store_true', 
                       help='Skip generating PDF output')
    parser.add_argument('--max', type=int, 
                       help='Maximum number of metabolites to process')
    parser.add_argument('--metabolites', type=str, nargs='+', 
                       help='Specific metabolites to process (e.g., "ATP ADP GLU")')
    parser.add_argument('--compare', action='store_true',
                       help='Compare Bardyn and Brodbar datasets')
    parser.add_argument('--quiet', action='store_true',
                       help='Reduce output verbosity')
    args = parser.parse_args()
    
    if args.compare:
        # Run comparison mode
        compare_datasets(
            selected_metabolites=args.metabolites,
            max_metabolites=args.max,
            generate_plots=not args.no_plots,
            verbose=not args.quiet
        )
    else:
        # Run single dataset mode
        print(f"Processing data from: {args.data}")
        
        # Extract base name for the output files
        data_source = args.data.split('_')[1] if '_' in args.data else args.data
        
        # Run curve fitting
        meta_names, metabolites, matricepara, tempsexp = curve_fit_ja(
            args.data, 
            # Set to "no" to skip plots if requested
            option="no" if args.no_plots else None,
            # Pass subset selection arguments
            max_metabolites=args.max,
            selected_metabolites=args.metabolites,
            # Control output verbosity
            verbose=not args.quiet
        )
        
        # Count non-NaN values in matricepara to get number of fitted metabolites
        fitted_count = np.sum(~np.isnan(matricepara[:, 0]))
        print(f"\nProcessed {fitted_count} metabolites successfully")
        
        # Generate PDF if not disabled
        if not args.no_pdf and not args.no_plots:
            pdf_path = export_to_pdf(
                save_path="html", 
                output_filename=f"Results_Curvefit_{data_source}.pdf",
                data_source=data_source
            )
            if pdf_path:
                print(f"To view the curve fitting results, open: {pdf_path}")
                
        # Provide a summary of the fitted parameters
        if fitted_count > 0:
            print("\nExample of fitted parameters (first 3 metabolites):")
            for i in range(min(3, fitted_count)):
                idx = np.where(~np.isnan(matricepara[:, 0]))[0][i]
                print(f"  {meta_names[idx]}: {matricepara[idx, :].tolist()}")
        else:
            print("No metabolites were successfully fitted.")
    
    # Display command examples for testing
    print("\nUsage examples:")
    print(f"  python src/curve_fit.py --max 5  # Process only first 5 metabolites")
    print(f"  python src/curve_fit.py --metabolites ATP ADP GLU  # Process specific metabolites")
    print(f"  python src/curve_fit.py --compare  # Compare Bardyn and Brodbar datasets")
    print(f"  python src/curve_fit.py --compare --metabolites ATP ADP GLU  # Compare specific metabolites")
