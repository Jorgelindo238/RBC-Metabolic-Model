"""
Sensitivity Analysis Engine - Compare experimental data impact on simulation
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import streamlit as st


class SensitivityAnalyzer:
    """
    Analyze sensitivity of simulation to different experimental datasets.
    
    NEW APPROACH: Since the ODE simulation doesn't change with different experimental data
    (it's governed by kinetic laws), we instead analyze:
    1. How well simulation fits Bordbar data vs Custom data (residuals analysis)
    2. Which metabolites show the biggest discrepancies
    3. Statistical validation metrics
    """
    
    def __init__(self, brodbar_results: Dict, custom_results: Dict):
        """
        Initialize analyzer with simulation results.
        
        NOTE: Both simulations will be similar since they use same ODE system.
        The real analysis compares simulation predictions against different experimental datasets.
        
        Parameters:
        -----------
        brodbar_results : dict
            Simulation results (will be same as custom due to ODE nature)
        custom_results : dict
            Simulation results (will be same as brodbar due to ODE nature)
        """
        self.brodbar = brodbar_results
        self.custom = custom_results
        
        # Extract common info
        self.metabolites = brodbar_results.get('metabolite_names', [])
        self.time_sim = brodbar_results.get('t', np.array([]))  # Simulation time
        
        # Concentrations from simulation (will be nearly identical)
        self.conc_sim = brodbar_results.get('x', np.array([]))  # (timepoints, metabolites)
        
        # Experimental data
        self.exp_brodbar = brodbar_results.get('experimental_data', {})
        self.exp_custom = custom_results.get('custom_validation_data', {})
        
        # Flux data
        self.flux_data = brodbar_results.get('flux_data', {})
    
    def compare_metabolite_concentrations(self) -> pd.DataFrame:
        """
        Compare EXPERIMENTAL datasets (Bordbar vs Custom) directly.
        
        Returns:
        --------
        pd.DataFrame
            Comparison of experimental measurements
        """
        if not self.exp_brodbar or not self.exp_custom:
            return pd.DataFrame()
        
        exp_b_mets = self.exp_brodbar.get('metabolites', [])
        exp_b_values = self.exp_brodbar.get('values', np.array([]))
        
        exp_c_mets = self.exp_custom.get('metabolites', [])
        exp_c_values = self.exp_custom.get('values', np.array([]))
        
        if len(exp_b_mets) == 0 or len(exp_c_mets) == 0:
            return pd.DataFrame()
        
        results = []
        
        # Compare common metabolites
        common_mets = set(exp_b_mets).intersection(set(exp_c_mets))
        
        for met_name in common_mets:
            idx_b = exp_b_mets.index(met_name)
            idx_c = exp_c_mets.index(met_name)
            
            vals_b = exp_b_values[idx_b, :]
            vals_c = exp_c_values[idx_c, :]
            
            # Calculate statistics
            mean_b = np.mean(vals_b)
            mean_c = np.mean(vals_c)
            std_b = np.std(vals_b)
            std_c = np.std(vals_c)
            
            # Direct difference
            if len(vals_b) == len(vals_c):
                diff = vals_c - vals_b
                max_diff = np.max(np.abs(diff))
                mean_diff = np.mean(diff)
                rmse = np.sqrt(np.mean(diff**2))
            else:
                max_diff = abs(mean_c - mean_b)
                mean_diff = mean_c - mean_b
                rmse = abs(mean_c - mean_b)
            
            # Percent change
            if mean_b != 0:
                pct_change = ((mean_c - mean_b) / mean_b) * 100
            else:
                pct_change = 0
            
            results.append({
                'Metabolite': met_name,
                'Bordbar_Mean': mean_b,
                'Custom_Mean': mean_c,
                'Bordbar_Std': std_b,
                'Custom_Std': std_c,
                'Mean_Difference': mean_diff,
                'Max_Difference': max_diff,
                'RMSE': rmse,
                'Percent_Change': pct_change,
                'Abs_Pct_Change': abs(pct_change)
            })
        
        df = pd.DataFrame(results)
        return df.sort_values('Abs_Pct_Change', ascending=False) if not df.empty else df
    
    def compare_flux_profiles(self) -> pd.DataFrame:
        """
        Compare flux profiles - Returns empty since fluxes are identical.
        
        NOTE: Fluxes are determined by the ODE system, not experimental data.
        Both simulations produce identical fluxes since they use the same kinetic model.
        
        Returns:
        --------
        pd.DataFrame
            Empty DataFrame (fluxes don't change with different experimental data)
        """
        # Fluxes are computed from the same ODE system, so they will be nearly identical
        # The experimental data doesn't change the flux dynamics
        return pd.DataFrame()
    
    def get_pathway_impact(self) -> Dict[str, Dict]:
        """
        Analyze impact by metabolic pathway.
        
        Returns:
        --------
        dict
            Impact statistics grouped by pathway
        """
        from core.flux_plotting import REACTION_INFO
        
        flux_comparison = self.compare_flux_profiles()
        
        if flux_comparison.empty:
            return {}
        
        # Group reactions by pathway
        pathway_stats = {}
        
        for rxn in flux_comparison.itertuples():
            rxn_info = REACTION_INFO.get(rxn.Reaction, {})
            pathway = rxn_info.get('pathway', 'Other')
            
            if pathway not in pathway_stats:
                pathway_stats[pathway] = {
                    'reactions': [],
                    'mean_pct_changes': [],
                    'max_impacts': []
                }
            
            pathway_stats[pathway]['reactions'].append(rxn.Reaction)
            pathway_stats[pathway]['mean_pct_changes'].append(rxn.Percent_Change)
            pathway_stats[pathway]['max_impacts'].append(rxn.Max_Difference)
        
        # Calculate summary statistics for each pathway
        pathway_summary = {}
        for pathway, stats in pathway_stats.items():
            pathway_summary[pathway] = {
                'n_reactions': len(stats['reactions']),
                'mean_pct_change': np.mean(stats['mean_pct_changes']),
                'max_pct_change': np.max(np.abs(stats['mean_pct_changes'])),
                'total_impact': np.sum(np.abs(stats['max_impacts']))
            }
        
        return pathway_summary
    
    def get_top_sensitive_metabolites(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N most different metabolites between datasets.
        
        Parameters:
        -----------
        n : int
            Number of top metabolites to return
        
        Returns:
        --------
        list of tuples
            (metabolite_name, percent_change)
        """
        comparison = self.compare_metabolite_concentrations()
        
        if comparison.empty:
            return []
        
        top_n = comparison.nlargest(n, 'Abs_Pct_Change')
        return list(zip(top_n['Metabolite'], top_n['Percent_Change']))
    
    def get_top_sensitive_fluxes(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N most sensitive fluxes.
        
        Parameters:
        -----------
        n : int
            Number of top fluxes to return
        
        Returns:
        --------
        list of tuples
            (reaction_name, percent_change)
        """
        comparison = self.compare_flux_profiles()
        
        if comparison.empty:
            return []
        
        top_n = comparison.nlargest(n, 'Absolute_Pct_Change')
        return list(zip(top_n['Reaction'], top_n['Percent_Change']))
    
    def calculate_validation_metrics(self) -> Dict[str, Dict]:
        """
        Calculate validation metrics comparing custom data to simulation.
        
        Returns:
        --------
        dict
            Validation metrics for metabolites in custom dataset
        """
        # Get custom experimental data
        custom_exp = self.custom.get('custom_validation_data')
        
        if not custom_exp or custom_exp.get('metabolites') is None:
            return {}
        
        exp_metabolites = custom_exp['metabolites']
        exp_time = custom_exp['time']
        exp_values = custom_exp['values']  # (n_metabolites, n_timepoints)
        
        # Get simulation results
        sim_time = self.time_sim
        sim_conc = self.conc_sim  # (n_timepoints, n_metabolites)
        
        metrics = {}
        
        for idx, met_name in enumerate(exp_metabolites):
            if met_name not in self.metabolites:
                continue
            
            met_idx = self.metabolites.index(met_name)
            
            # Get experimental values
            exp_vals = exp_values[idx, :]
            
            # Interpolate simulation to experimental timepoints
            sim_vals = np.interp(exp_time, sim_time, sim_conc[:, met_idx])
            
            # Calculate metrics
            residuals = exp_vals - sim_vals
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((exp_vals - np.mean(exp_vals))**2)
            
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            rmse = np.sqrt(np.mean(residuals**2))
            mae = np.mean(np.abs(residuals))
            
            metrics[met_name] = {
                'R2': r2,
                'RMSE': rmse,
                'MAE': mae,
                'n_points': len(exp_vals)
            }
        
        return metrics


def run_comparative_simulation() -> Optional[Dict]:
    """
    Run simulation and ensure both datasets are available for comparison.
    
    Returns:
    --------
    dict or None
        Simulation results with both experimental datasets
    """
    from core.simulation_engine import SimulationEngine
    
    # Temporarily set to use Bordbar data (default)
    original_mode = st.session_state.get('uploaded_data_mode', None)
    original_active = st.session_state.get('uploaded_data_active', False)
    
    # Always use Bordbar for simulation (ODE doesn't change anyway)
    st.session_state['uploaded_data_active'] = False
    
    try:
        # Reuse cached simulation results if available (avoids redundant ODE integration)
        cached = st.session_state.get('simulation_results')
        if cached and cached.get('success', False):
            results = cached
        else:
            # No cached results - run a fresh simulation
            engine = SimulationEngine()
            results = engine.run_simulation(
                t_max=42,
                curve_fit_strength=0.5,
                solver_method='LSODA',
                ph_perturbation_type=None,
                progress_callback=None
            )
        
        # Manually add custom validation data to results if available
        # Check original_active, not current state (we just set it to False)
        if 'uploaded_data' in st.session_state and original_active:
            custom_df = st.session_state['uploaded_data']
            
            if custom_df is not None and hasattr(custom_df, 'columns'):
                # Extract custom data
                if 'Time' in custom_df.columns:
                    custom_time = custom_df['Time'].values
                    custom_mets = [col for col in custom_df.columns if col != 'Time']
                    custom_values = np.array([custom_df[met].values for met in custom_mets])
                    
                    results['custom_validation_data'] = {
                        'time': custom_time,
                        'metabolites': custom_mets,
                        'values': custom_values
                    }
                else:
                    # Try alternative format (Metabolite column)
                    if 'Metabolite' in custom_df.columns:
                        custom_mets = custom_df['Metabolite'].tolist()
                        time_cols = [col for col in custom_df.columns if col != 'Metabolite']
                        custom_time = np.array([float(col) for col in time_cols])
                        custom_values = custom_df[time_cols].values
                        
                        results['custom_validation_data'] = {
                            'time': custom_time,
                            'metabolites': custom_mets,
                            'values': custom_values
                        }
        
        return results
    
    finally:
        # Restore original mode
        if original_mode:
            st.session_state['uploaded_data_mode'] = original_mode
        st.session_state['uploaded_data_active'] = original_active
