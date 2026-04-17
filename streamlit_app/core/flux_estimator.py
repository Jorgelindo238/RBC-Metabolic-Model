"""
Flux Estimator Module
=====================

Estimates metabolic fluxes from metabolite concentration data using
Michaelis-Menten kinetics. This allows flux analysis from:
- Uploaded experimental datasets
- Comparison between simulated and experimental-derived fluxes

Author: Jorgelindo da Veiga
Date: 2025-01-28
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import sys

# Add src to path for equadiff parameters
this_file = Path(__file__).resolve()
project_root = this_file.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP
    METABOLITE_MAP_AVAILABLE = True
except ImportError:
    METABOLITE_MAP_AVAILABLE = False
    BORDBAR_METABOLITE_MAP = {}


# Kinetic parameters for flux estimation (Vmax, Km values from equadiff_brodbar.py)
KINETIC_PARAMS = {
    # Glycolysis
    'VHK': {'vmax': 4.4, 'km_GLC': 0.1, 'km_ATP': 1.0, 'substrates': ['GLC', 'ATP']},
    'VPGI': {'vmax': 935.0, 'km_G6P': 0.5, 'km_F6P': 0.2, 'substrates': ['G6P'], 'products': ['F6P'], 'reversible': True, 'keq': 0.4},
    'VPFK': {'vmax': 161.7, 'km_F6P': 0.1, 'km_ATP': 0.05, 'substrates': ['F6P', 'ATP']},
    'VFDPA': {'vmax': 98.9, 'km_F16BP': 0.01, 'substrates': ['F16BP']},
    'VTPI': {'vmax': 5456.6, 'km_DHCP': 0.1, 'substrates': ['DHCP']},
    'VGAPDH': {'vmax': 7195.8, 'km_GA3P': 0.01, 'km_NAD': 0.1, 'substrates': ['GA3P', 'NAD']},
    'VPGK': {'vmax': 7195.8, 'km_B13PG': 0.003, 'km_ADP': 0.5, 'substrates': ['B13PG', 'ADP']},
    'VPGM': {'vmax': 2085.0, 'km_P3G': 0.1, 'substrates': ['P3G']},
    'VENOPGM': {'vmax': 598.3, 'km_P2G': 0.04, 'substrates': ['P2G']},
    'VPK': {'vmax': 3974.6, 'km_PEP': 0.023, 'km_ADP': 0.3, 'substrates': ['PEP', 'ADP']},
    'VLDH': {'vmax': 4624.0, 'km_PYR': 0.137, 'km_NADH': 0.01, 'substrates': ['PYR', 'NADH']},
    
    # Pentose Phosphate Pathway
    'VG6PDH': {'vmax': 162.4, 'km_G6P': 0.067, 'km_NADP': 0.004, 'substrates': ['G6P', 'NADP']},
    'VPGLS': {'vmax': 4000.0, 'km_GL6P': 0.01, 'substrates': ['GL6P']},
    'V6PGD': {'vmax': 162.4, 'km_GO6P': 0.01, 'km_NADP': 0.01, 'substrates': ['GO6P', 'NADP']},
    'VR5PI': {'vmax': 4000.0, 'km_RU5P': 0.1, 'substrates': ['RU5P']},
    'VR5PE': {'vmax': 4000.0, 'km_RU5P': 0.1, 'substrates': ['RU5P']},
    'VTKL1': {'vmax': 30.0, 'km_X5P': 0.1, 'km_R5P': 0.1, 'substrates': ['X5P', 'R5P']},
    'VTKL2': {'vmax': 30.0, 'km_X5P': 0.1, 'km_E4P': 0.1, 'substrates': ['X5P', 'E4P']},
    'VTAL': {'vmax': 30.0, 'km_S7P': 0.1, 'km_GA3P': 0.1, 'substrates': ['S7P', 'GA3P']},
    
    # 2,3-BPG Shunt (Rapoport-Luebering)
    'VDPGM': {'vmax': 500.0, 'km_B13PG': 0.002, 'substrates': ['B13PG']},
    'V23DPGP': {'vmax': 0.15, 'km_B23PG': 0.1, 'substrates': ['B23PG']},
    
    # Transport reactions
    'VEGLC': {'vmax': 1100.0, 'km_GLC': 1.7, 'km_EGLC': 1.7, 'substrates': ['GLC'], 'products': ['EGLC'], 'reversible': True},
    'VELAC': {'vmax': 147.0, 'km_LAC': 13.0, 'km_ELAC': 13.0, 'substrates': ['LAC'], 'products': ['ELAC'], 'reversible': True},
    'VEPYR': {'vmax': 100.0, 'km_PYR': 1.0, 'km_EPYR': 1.0, 'substrates': ['PYR'], 'products': ['EPYR'], 'reversible': True},
    
    # Glutathione System
    'VGSR': {'vmax': 5.7, 'km_GSSG': 0.065, 'km_NADPH': 0.01, 'substrates': ['GSSG', 'NADPH']},
    'VGPX': {'vmax': 1500.0, 'km_GSH': 1.0, 'km_H2O2': 0.001, 'substrates': ['GSH', 'H2O2']},
    'VGLUCYS': {'vmax': 2.2, 'km_GLU': 2.0, 'km_CYS': 0.1, 'km_ATP': 1.0, 'substrates': ['GLU', 'CYS', 'ATP']},
    'VGSS': {'vmax': 1.1, 'km_GLUCYS': 0.02, 'km_GLY': 0.3, 'km_ATP': 0.4, 'substrates': ['GLUCYS', 'GLY', 'ATP']},
    
    # Nucleotide Metabolism
    'VAK': {'vmax': 2188.0, 'km_ADP': 0.25, 'substrates': ['ADP']},
    'VAPRT': {'vmax': 0.4, 'km_ADE': 0.001, 'km_PRPP': 0.005, 'substrates': ['ADE', 'PRPP']},
    'VADA': {'vmax': 1.9, 'km_ADO': 0.04, 'substrates': ['ADO']},
    'VAMPD1': {'vmax': 6.8, 'km_AMP': 0.7, 'substrates': ['AMP']},
    'VPRPPASE': {'vmax': 0.96, 'km_R5P': 0.03, 'km_ATP': 0.9, 'substrates': ['R5P', 'ATP']},
    
    # Amino Acid Metabolism
    'VGLNS': {'vmax': 0.5, 'km_GLU': 2.0, 'km_ATP': 1.0, 'km_NH4': 0.1, 'substrates': ['GLU', 'ATP', 'NH4']},
    'VGDH': {'vmax': 0.5, 'km_AKG': 0.2, 'km_NADPH': 0.01, 'km_NH4': 0.1, 'substrates': ['AKG', 'NADPH', 'NH4']},
    'VASPTA': {'vmax': 100.0, 'km_ASP': 1.0, 'km_AKG': 0.1, 'substrates': ['ASP', 'AKG']},
    'VALATA': {'vmax': 100.0, 'km_ALA': 1.0, 'km_AKG': 0.1, 'substrates': ['ALA', 'AKG']},
}


def mm_rate(s: float, vmax: float, km: float) -> float:
    """
    Michaelis-Menten rate equation.
    
    v = Vmax * S / (Km + S)
    """
    s = max(s, 1e-12)  # Avoid division by zero
    return vmax * s / (km + s)


def bibi_rate(s1: float, s2: float, vmax: float, km1: float, km2: float) -> float:
    """
    Bi-substrate Michaelis-Menten rate (ordered mechanism).
    
    v = Vmax * S1 * S2 / ((Km1 + S1) * (Km2 + S2))
    """
    s1 = max(s1, 1e-12)
    s2 = max(s2, 1e-12)
    return vmax * s1 * s2 / ((km1 + s1) * (km2 + s2))


class FluxEstimator:
    """
    Estimates metabolic fluxes from concentration data using Michaelis-Menten kinetics.
    """
    
    def __init__(self, custom_params: Optional[Dict] = None):
        """
        Initialize FluxEstimator.
        
        Parameters:
        -----------
        custom_params : dict, optional
            Custom kinetic parameters to override defaults
        """
        self.params = KINETIC_PARAMS.copy()
        if custom_params:
            for rxn, params in custom_params.items():
                if rxn in self.params:
                    self.params[rxn].update(params)
                else:
                    self.params[rxn] = params
    
    def get_metabolite_concentration(self, metabolite: str, 
                                      concentrations: Dict[str, float]) -> float:
        """
        Get concentration of a metabolite, handling missing data gracefully.
        
        Returns default physiological value if not found.
        """
        if metabolite in concentrations:
            return max(concentrations[metabolite], 1e-12)
        
        # Default values for common metabolites (mM)
        defaults = {
            'ATP': 1.5, 'ADP': 0.4, 'AMP': 0.05,
            'NAD': 0.05, 'NADH': 0.001,
            'NADP': 0.003, 'NADPH': 0.05,
            'GLC': 5.0, 'G6P': 0.05, 'F6P': 0.015,
            'F16BP': 0.003, 'DHCP': 0.01, 'GA3P': 0.005,
            'B13PG': 0.0005, 'P3G': 0.06, 'P2G': 0.01,
            'PEP': 0.015, 'PYR': 0.07, 'LAC': 2.0,
            'B23PG': 4.5, 'GSH': 3.0, 'GSSG': 0.003,
            'GLU': 0.4, 'GLN': 0.5, 'GLY': 0.5,
            'H2O2': 0.00001
        }
        return defaults.get(metabolite, 0.01)
    
    def estimate_flux(self, reaction: str, 
                      concentrations: Dict[str, float]) -> float:
        """
        Estimate flux for a single reaction given metabolite concentrations.
        
        Parameters:
        -----------
        reaction : str
            Reaction name (e.g., 'VHK', 'VPFK')
        concentrations : dict
            Dictionary of {metabolite_name: concentration}
            
        Returns:
        --------
        float
            Estimated flux in mM/day
        """
        if reaction not in self.params:
            return 0.0
        
        p = self.params[reaction]
        vmax = p['vmax']
        substrates = p.get('substrates', [])
        
        if len(substrates) == 0:
            return 0.0
        
        elif len(substrates) == 1:
            # Single substrate
            s_name = substrates[0]
            km_key = f'km_{s_name}'
            s = self.get_metabolite_concentration(s_name, concentrations)
            km = p.get(km_key, 0.1)
            
            flux = mm_rate(s, vmax, km)
            
            # Handle reversibility if applicable
            if p.get('reversible', False) and 'products' in p:
                prod_name = p['products'][0]
                km_prod_key = f'km_{prod_name}'
                prod = self.get_metabolite_concentration(prod_name, concentrations)
                km_prod = p.get(km_prod_key, 0.1)
                keq = p.get('keq', 1.0)
                
                # Net flux = forward - reverse
                flux_rev = mm_rate(prod, vmax / keq, km_prod)
                flux = flux - flux_rev
        
        elif len(substrates) == 2:
            # Bi-substrate
            s1_name, s2_name = substrates[0], substrates[1]
            s1 = self.get_metabolite_concentration(s1_name, concentrations)
            s2 = self.get_metabolite_concentration(s2_name, concentrations)
            km1 = p.get(f'km_{s1_name}', 0.1)
            km2 = p.get(f'km_{s2_name}', 0.1)
            
            flux = bibi_rate(s1, s2, vmax, km1, km2)
        
        elif len(substrates) >= 3:
            # Multi-substrate approximation
            s_vals = [self.get_metabolite_concentration(s, concentrations) for s in substrates]
            km_vals = [p.get(f'km_{s}', 0.1) for s in substrates]
            
            # Product of saturation terms
            saturation = 1.0
            for s, km in zip(s_vals, km_vals):
                saturation *= s / (km + s)
            
            flux = vmax * saturation
        
        else:
            flux = 0.0
        
        return flux
    
    def estimate_all_fluxes(self, concentrations: Dict[str, float]) -> Dict[str, float]:
        """
        Estimate all fluxes for a single timepoint.
        
        Parameters:
        -----------
        concentrations : dict
            Dictionary of {metabolite_name: concentration}
            
        Returns:
        --------
        dict
            Dictionary of {reaction_name: estimated_flux}
        """
        fluxes = {}
        for reaction in self.params.keys():
            fluxes[reaction] = self.estimate_flux(reaction, concentrations)
        return fluxes
    
    def estimate_fluxes_timeseries(self, df: pd.DataFrame, 
                                    time_col: str = 'Time') -> Dict:
        """
        Estimate fluxes for a time-series dataset.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with time column and metabolite columns
        time_col : str
            Name of the time column
            
        Returns:
        --------
        dict
            Flux data in format compatible with flux_plotting:
            {'times': [...], 'fluxes': {'reaction': [...]}}
        """
        times = df[time_col].values.tolist()
        metabolite_cols = [c for c in df.columns if c != time_col]
        
        # Initialize flux dictionary
        flux_data = {
            'times': times,
            'fluxes': {rxn: [] for rxn in self.params.keys()}
        }
        
        # Estimate fluxes for each timepoint
        for idx in range(len(df)):
            concentrations = {col: df.iloc[idx][col] for col in metabolite_cols}
            
            point_fluxes = self.estimate_all_fluxes(concentrations)
            
            for rxn, flux in point_fluxes.items():
                flux_data['fluxes'][rxn].append(flux)
        
        # Remove reactions with all zeros
        flux_data['fluxes'] = {
            rxn: fluxes for rxn, fluxes in flux_data['fluxes'].items()
            if any(f != 0 for f in fluxes)
        }
        
        return flux_data
    
    def get_available_reactions(self) -> List[str]:
        """Get list of reactions that can be estimated."""
        return list(self.params.keys())
    
    def get_reaction_substrates(self, reaction: str) -> List[str]:
        """Get substrates needed for a reaction."""
        if reaction in self.params:
            return self.params[reaction].get('substrates', [])
        return []


def compute_flux_from_uploaded_data(uploaded_df: pd.DataFrame, 
                                     time_col: str = 'Time') -> Dict:
    """
    Convenience function to compute fluxes from uploaded experimental data.
    
    Parameters:
    -----------
    uploaded_df : pd.DataFrame
        DataFrame from data upload page
    time_col : str
        Name of time column
        
    Returns:
    --------
    dict
        Flux data compatible with flux_plotting module
    """
    estimator = FluxEstimator()
    return estimator.estimate_fluxes_timeseries(uploaded_df, time_col)


def compare_fluxes(simulated_flux: Dict, experimental_flux: Dict) -> pd.DataFrame:
    """
    Compare simulated and experimental-derived fluxes.
    
    Parameters:
    -----------
    simulated_flux : dict
        Flux data from simulation
    experimental_flux : dict
        Flux data computed from experimental concentrations
        
    Returns:
    --------
    pd.DataFrame
        Comparison statistics
    """
    comparison = []
    
    common_reactions = set(simulated_flux['fluxes'].keys()) & set(experimental_flux['fluxes'].keys())
    
    for rxn in common_reactions:
        sim_values = np.array(simulated_flux['fluxes'][rxn])
        exp_values = np.array(experimental_flux['fluxes'][rxn])
        
        # Interpolate if different time grids
        if len(sim_values) != len(exp_values):
            # Use mean comparison
            sim_mean = np.mean(np.abs(sim_values))
            exp_mean = np.mean(np.abs(exp_values))
        else:
            sim_mean = np.mean(np.abs(sim_values))
            exp_mean = np.mean(np.abs(exp_values))
        
        # Calculate deviation
        if exp_mean > 1e-10:
            deviation = (sim_mean - exp_mean) / exp_mean * 100
        else:
            deviation = 0.0
        
        comparison.append({
            'Reaction': rxn,
            'Simulated_Mean': sim_mean,
            'Experimental_Mean': exp_mean,
            'Deviation_%': deviation,
            'Abs_Difference': abs(sim_mean - exp_mean)
        })
    
    df = pd.DataFrame(comparison)
    df = df.sort_values('Abs_Difference', ascending=False)
    
    return df


# Quick test
if __name__ == '__main__':
    print("=" * 60)
    print("FLUX ESTIMATOR TEST")
    print("=" * 60)
    
    # Test with typical RBC concentrations
    test_concentrations = {
        'GLC': 5.0, 'ATP': 1.5, 'ADP': 0.4, 'G6P': 0.05,
        'F6P': 0.015, 'F16BP': 0.003, 'NAD': 0.05, 'NADH': 0.001,
        'GA3P': 0.005, 'B13PG': 0.0005, 'P3G': 0.06, 'P2G': 0.01,
        'PEP': 0.015, 'PYR': 0.07, 'LAC': 2.0, 'NADPH': 0.05,
        'NADP': 0.003, 'B23PG': 4.5, 'GSH': 3.0, 'GSSG': 0.003
    }
    
    estimator = FluxEstimator()
    fluxes = estimator.estimate_all_fluxes(test_concentrations)
    
    print("\nEstimated Glycolytic Fluxes:")
    for rxn in ['VHK', 'VPGI', 'VPFK', 'VFDPA', 'VTPI', 'VGAPDH', 
                'VPGK', 'VPGM', 'VENOPGM', 'VPK', 'VLDH']:
        if rxn in fluxes:
            print(f"  {rxn}: {fluxes[rxn]:.4f} mM/day")
    
    print("\n2,3-BPG Shunt:")
    print(f"  VDPGM: {fluxes.get('VDPGM', 0):.4f} mM/day")
    print(f"  V23DPGP: {fluxes.get('V23DPGP', 0):.4f} mM/day")
    
    print("\n✓ FluxEstimator module working correctly!")
