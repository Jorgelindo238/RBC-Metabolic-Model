"""
Parameter Calibration Module
Automatic calibration of enzyme parameters against experimental data

Author: Jorgelindo da Veiga
Date: 2025-11-22
"""

import numpy as np
from scipy.optimize import minimize, differential_evolution, least_squares
from scipy.stats import t as t_distribution
from typing import Dict, List, Tuple, Optional, Callable
import pandas as pd
from dataclasses import dataclass
import warnings

@dataclass
class CalibrationResult:
    """Results from parameter calibration"""
    optimized_params: Dict[str, float]
    initial_params: Dict[str, float]
    objective_value: float
    success: bool
    message: str
    iterations: int
    confidence_intervals: Dict[str, Tuple[float, float]]
    sensitivity: Dict[str, float]
    residuals: np.ndarray
    r_squared: float


class ParameterCalibrator:
    """
    Automatic calibration of model parameters using experimental data
    
    Uses multiple optimization algorithms and statistical methods to find
    optimal parameter values that minimize discrepancy with experimental data.
    """
    
    def __init__(self, 
                 simulation_function: Callable,
                 experimental_data: pd.DataFrame,
                 target_metabolites: List[str],
                 time_points: np.ndarray,
                 time_unit: str = 'days'):
        """
        Initialize calibrator
        
        Args:
            simulation_function: Function that runs simulation with given parameters
            experimental_data: DataFrame with experimental measurements
            target_metabolites: List of metabolite names to calibrate against
            time_points: Time points for comparison
            time_unit: Time unit for simulation/experimental alignment ('days' or 'hours')
        """
        self.simulation_function = simulation_function
        if 'time' not in experimental_data.columns:
            raise ValueError("experimental_data must contain a 'time' column")

        # Canonicalize experimental time axis to numeric, monotonic values
        exp_df = experimental_data.copy()
        exp_df['time'] = pd.to_numeric(exp_df['time'], errors='coerce')
        exp_df = exp_df.dropna(subset=['time']).sort_values('time').reset_index(drop=True)
        self.experimental_data = exp_df

        self.target_metabolites = target_metabolites
        self.time_points = np.asarray(time_points, dtype=float)
        if self.time_points.ndim != 1:
            raise ValueError("time_points must be a 1D array")
        self.time_points = np.sort(np.unique(self.time_points))
        self.time_unit = time_unit
        
        # Extract experimental values for target metabolites
        self.experimental_values = self._extract_experimental_values()

    @staticmethod
    def _interp_to_times(target_times: np.ndarray,
                         source_times: np.ndarray,
                         source_values: np.ndarray) -> np.ndarray:
        """Interpolate source_values(source_times) onto target_times safely."""
        source_times = np.asarray(source_times, dtype=float)
        source_values = np.asarray(source_values, dtype=float)

        valid = np.isfinite(source_times) & np.isfinite(source_values)
        if np.count_nonzero(valid) < 2:
            return np.zeros(len(target_times), dtype=float)

        source_times = source_times[valid]
        source_values = source_values[valid]
        order = np.argsort(source_times)
        source_times = source_times[order]
        source_values = source_values[order]

        # np.interp expects strictly increasing xp
        unique_times, unique_idx = np.unique(source_times, return_index=True)
        unique_values = source_values[unique_idx]
        if len(unique_times) < 2:
            return np.full(len(target_times), unique_values[0], dtype=float)

        return np.interp(target_times, unique_times, unique_values)
    
    def _extract_experimental_values(self) -> np.ndarray:
        """Extract experimental values for target metabolites"""
        values = []
        exp_times = self.experimental_data['time'].values
        for metabolite in self.target_metabolites:
            if metabolite in self.experimental_data.columns:
                # Interpolate to match simulation time points
                exp_values = pd.to_numeric(self.experimental_data[metabolite], errors='coerce').values
                interp_values = self._interp_to_times(self.time_points, exp_times, exp_values)
                values.append(interp_values)
            else:
                # If metabolite not found, use zeros (will be excluded from optimization)
                values.append(np.zeros(len(self.time_points)))
        
        return np.array(values)
    
    def _objective_function(self, 
                           params: np.ndarray, 
                           param_names: List[str],
                           base_params: Dict) -> float:
        """
        Objective function to minimize: sum of squared residuals
        
        Args:
            params: Array of parameter values to optimize
            param_names: Names corresponding to params array
            base_params: Dictionary of all parameters (will be updated)
            
        Returns:
            Sum of squared residuals
        """
        # Update parameters
        updated_params = base_params.copy()
        for i, name in enumerate(param_names):
            updated_params[name] = params[i]
        
        try:
            # Run simulation with updated parameters
            sim_results = self.simulation_function(updated_params)
            
            # Extract simulated values for target metabolites
            sim_values = self._extract_simulation_values(sim_results)
            
            # Calculate residuals (weighted by experimental uncertainty if available)
            residuals = (sim_values - self.experimental_values).flatten()
            
            # Sum of squared residuals (SSR)
            ssr = np.sum(residuals ** 2)
            
            return ssr
            
        except Exception as e:
            # Return large penalty if simulation fails
            warnings.warn(f"Simulation failed: {str(e)}")
            return 1e10
    
    def _extract_simulation_values(self, sim_results: pd.DataFrame) -> np.ndarray:
        """Extract simulation values for target metabolites"""
        values = []
        sim_times = pd.to_numeric(sim_results['time'], errors='coerce').values
        for metabolite in self.target_metabolites:
            if metabolite in sim_results.columns:
                # Interpolate to match time points
                sim_values = pd.to_numeric(sim_results[metabolite], errors='coerce').values
                interp_values = self._interp_to_times(self.time_points, sim_times, sim_values)
                values.append(interp_values)
            else:
                values.append(np.zeros(len(self.time_points)))
        
        return np.array(values)
    
    def calibrate(self,
                  params_to_optimize: Dict[str, Tuple[float, float, float]],
                  base_params: Dict,
                  method: str = 'differential_evolution',
                  max_iterations: int = 1000,
                  confidence_level: float = 0.95,
                  compute_confidence_intervals: bool = True,
                  compute_sensitivity: bool = True) -> CalibrationResult:
        """
        Calibrate parameters using optimization
        
        Args:
            params_to_optimize: Dict of {param_name: (initial, lower_bound, upper_bound)}
            base_params: Dictionary of all simulation parameters
            method: Optimization method ('differential_evolution', 'minimize', 'least_squares')
            max_iterations: Maximum number of iterations
            confidence_level: Confidence level for intervals (e.g., 0.95 for 95%)
            compute_confidence_intervals: Whether to compute confidence intervals (expensive)
            compute_sensitivity: Whether to compute sensitivity scores (expensive)
            
        Returns:
            CalibrationResult object with optimization results
        """
        param_names = list(params_to_optimize.keys())
        initial_values = np.array([v[0] for v in params_to_optimize.values()])
        bounds = [(v[1], v[2]) for v in params_to_optimize.values()]
        
        # Store initial parameters
        initial_params = {name: initial_values[i] for i, name in enumerate(param_names)}
        
        # Run optimization
        if method == 'differential_evolution':
            result = self._optimize_differential_evolution(
                param_names, bounds, base_params, max_iterations
            )
        elif method == 'minimize':
            result = self._optimize_minimize(
                param_names, initial_values, bounds, base_params, max_iterations
            )
        elif method == 'least_squares':
            result = self._optimize_least_squares(
                param_names, initial_values, bounds, base_params, max_iterations
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Extract optimized parameters
        optimized_params = {name: result.x[i] for i, name in enumerate(param_names)}
        
        # Optional post-optimization statistics (can be disabled for fast iterations)
        confidence_intervals = {
            name: (float(result.x[i]), float(result.x[i]))
            for i, name in enumerate(param_names)
        }
        if compute_confidence_intervals:
            confidence_intervals = self._calculate_confidence_intervals(
                result.x, param_names, base_params, confidence_level
            )

        sensitivity = {name: 0.0 for name in param_names}
        if compute_sensitivity:
            sensitivity = self._calculate_sensitivity(
                result.x, param_names, base_params
            )
        
        # Calculate residuals and R²
        residuals = self._calculate_residuals(result.x, param_names, base_params)
        r_squared = self._calculate_r_squared(residuals)

        message = result.message if hasattr(result, 'message') else 'Success'
        skipped_stats = []
        if not compute_confidence_intervals:
            skipped_stats.append('confidence intervals')
        if not compute_sensitivity:
            skipped_stats.append('sensitivity')
        if skipped_stats:
            message = f"{message} (skipped {', '.join(skipped_stats)})"
        
        return CalibrationResult(
            optimized_params=optimized_params,
            initial_params=initial_params,
            objective_value=result.fun,
            success=result.success,
            message=message,
            iterations=result.nit if hasattr(result, 'nit') else result.nfev,
            confidence_intervals=confidence_intervals,
            sensitivity=sensitivity,
            residuals=residuals,
            r_squared=r_squared
        )
    
    def _optimize_differential_evolution(self, 
                                        param_names: List[str],
                                        bounds: List[Tuple[float, float]],
                                        base_params: Dict,
                                        max_iterations: int):
        """Optimize using differential evolution (global optimizer)"""
        return differential_evolution(
            func=lambda p: self._objective_function(p, param_names, base_params),
            bounds=bounds,
            maxiter=max_iterations,
            popsize=15,
            strategy='best1bin',
            tol=1e-7,
            mutation=(0.5, 1),
            recombination=0.7,
            seed=42,
            workers=1,
            polish=True
        )
    
    def _optimize_minimize(self,
                          param_names: List[str],
                          initial_values: np.ndarray,
                          bounds: List[Tuple[float, float]],
                          base_params: Dict,
                          max_iterations: int):
        """Optimize using local minimization"""
        return minimize(
            fun=lambda p: self._objective_function(p, param_names, base_params),
            x0=initial_values,
            method='L-BFGS-B',
            bounds=bounds,
            options={'maxiter': max_iterations, 'ftol': 1e-9}
        )
    
    def _optimize_least_squares(self,
                                param_names: List[str],
                                initial_values: np.ndarray,
                                bounds: List[Tuple[float, float]],
                                base_params: Dict,
                                max_iterations: int):
        """Optimize using nonlinear least squares"""
        def residual_function(params):
            # Update parameters
            updated_params = base_params.copy()
            for i, name in enumerate(param_names):
                updated_params[name] = params[i]
            
            try:
                sim_results = self.simulation_function(updated_params)
                sim_values = self._extract_simulation_values(sim_results)
                residuals = (sim_values - self.experimental_values).flatten()
                return residuals
            except Exception:
                return np.ones(len(self.target_metabolites) * len(self.time_points)) * 1e5
        
        # Separate lower and upper bounds
        lower_bounds = [b[0] for b in bounds]
        upper_bounds = [b[1] for b in bounds]
        
        return least_squares(
            fun=residual_function,
            x0=initial_values,
            bounds=(lower_bounds, upper_bounds),
            max_nfev=max_iterations,
            ftol=1e-9,
            method='trf'
        )
    
    def _calculate_confidence_intervals(self,
                                       optimized_params: np.ndarray,
                                       param_names: List[str],
                                       base_params: Dict,
                                       confidence_level: float) -> Dict[str, Tuple[float, float]]:
        """
        Calculate confidence intervals using Fisher information matrix
        
        Uses finite differences to estimate Hessian and compute confidence intervals
        """
        n_params = len(optimized_params)
        epsilon = 1e-6
        
        # Estimate Hessian using finite differences
        hessian = np.zeros((n_params, n_params))
        
        f0 = self._objective_function(optimized_params, param_names, base_params)
        
        for i in range(n_params):
            for j in range(i, n_params):
                # Perturbations
                params_pp = optimized_params.copy()
                params_pp[i] += epsilon
                params_pp[j] += epsilon
                
                params_pm = optimized_params.copy()
                params_pm[i] += epsilon
                params_pm[j] -= epsilon
                
                params_mp = optimized_params.copy()
                params_mp[i] -= epsilon
                params_mp[j] += epsilon
                
                params_mm = optimized_params.copy()
                params_mm[i] -= epsilon
                params_mm[j] -= epsilon
                
                # Calculate second derivative
                f_pp = self._objective_function(params_pp, param_names, base_params)
                f_pm = self._objective_function(params_pm, param_names, base_params)
                f_mp = self._objective_function(params_mp, param_names, base_params)
                f_mm = self._objective_function(params_mm, param_names, base_params)
                
                hessian[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4 * epsilon ** 2)
                hessian[j, i] = hessian[i, j]
        
        try:
            # Covariance matrix (inverse of Hessian)
            # Estimate variance of residuals
            residuals = self._calculate_residuals(optimized_params, param_names, base_params)
            n_data = len(residuals)
            var_residuals = np.var(residuals)
            
            # Covariance matrix
            cov_matrix = var_residuals * np.linalg.inv(hessian)
            
            # Standard errors
            std_errors = np.sqrt(np.diag(cov_matrix))
            
            # t-statistic for confidence level
            alpha = 1 - confidence_level
            dof = n_data - n_params  # degrees of freedom
            t_stat = t_distribution.ppf(1 - alpha/2, dof)
            
            # Confidence intervals
            confidence_intervals = {}
            for i, name in enumerate(param_names):
                margin = t_stat * std_errors[i]
                lower = optimized_params[i] - margin
                upper = optimized_params[i] + margin
                confidence_intervals[name] = (lower, upper)
            
            return confidence_intervals
            
        except np.linalg.LinAlgError:
            # If Hessian is singular, return wide intervals
            warnings.warn("Could not compute confidence intervals (singular Hessian)")
            return {name: (optimized_params[i] * 0.5, optimized_params[i] * 2.0) 
                   for i, name in enumerate(param_names)}
    
    def _calculate_sensitivity(self,
                              optimized_params: np.ndarray,
                              param_names: List[str],
                              base_params: Dict) -> Dict[str, float]:
        """
        Calculate parameter sensitivity (normalized gradient)
        
        Sensitivity = |∂objective/∂param| * param / objective
        """
        epsilon = 1e-6
        f0 = self._objective_function(optimized_params, param_names, base_params)
        
        sensitivity = {}
        for i, name in enumerate(param_names):
            params_perturbed = optimized_params.copy()
            params_perturbed[i] += epsilon
            
            f1 = self._objective_function(params_perturbed, param_names, base_params)
            
            # Normalized gradient
            gradient = (f1 - f0) / epsilon
            normalized_sensitivity = abs(gradient * optimized_params[i] / (f0 + 1e-10))
            
            sensitivity[name] = normalized_sensitivity
        
        return sensitivity
    
    def _calculate_residuals(self,
                            params: np.ndarray,
                            param_names: List[str],
                            base_params: Dict) -> np.ndarray:
        """Calculate residuals for optimized parameters"""
        updated_params = base_params.copy()
        for i, name in enumerate(param_names):
            updated_params[name] = params[i]
        
        sim_results = self.simulation_function(updated_params)
        sim_values = self._extract_simulation_values(sim_results)
        
        return (sim_values - self.experimental_values).flatten()
    
    def _calculate_r_squared(self, residuals: np.ndarray) -> float:
        """Calculate R² (coefficient of determination)"""
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((self.experimental_values.flatten() - 
                        np.mean(self.experimental_values)) ** 2)
        
        r_squared = 1 - (ss_res / (ss_tot + 1e-10))
        return r_squared
    
    def cross_validate(self,
                      params_to_optimize: Dict[str, Tuple[float, float, float]],
                      base_params: Dict,
                      k_folds: int = 5) -> Dict[str, any]:
        """
        Perform k-fold cross-validation
        
        Args:
            params_to_optimize: Parameters to calibrate
            base_params: Base parameters
            k_folds: Number of folds
            
        Returns:
            Dictionary with CV results
        """
        n_points = len(self.time_points)
        fold_size = n_points // k_folds
        
        cv_scores = []
        cv_params = []
        
        for fold in range(k_folds):
            # Split data
            test_indices = range(fold * fold_size, (fold + 1) * fold_size)
            train_indices = [i for i in range(n_points) if i not in test_indices]
            
            # Create training calibrator
            train_times = self.time_points[train_indices]
            # ... implement training/testing split logic
            
            # Calibrate on training data
            # Validate on test data
            # Store scores
        
        return {
            'mean_score': np.mean(cv_scores),
            'std_score': np.std(cv_scores),
            'fold_scores': cv_scores,
            'fold_params': cv_params
        }
