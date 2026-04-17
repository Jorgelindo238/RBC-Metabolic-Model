"""
Unit tests for parameter calibration module

Author: Jorgelindo da Veiga
Date: 2025-11-22
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "streamlit_app" / "core"))

from parameter_calibration import ParameterCalibrator, CalibrationResult


def create_synthetic_data(true_params, noise_level=0.05):
    """Create synthetic experimental data for testing"""
    time_points = np.linspace(0, 72, 50)
    
    # Simple exponential decay model
    data = {}
    data['time'] = time_points
    
    for param_name, param_value in true_params.items():
        # Synthetic concentration trajectory
        concentration = 10 * np.exp(-param_value * time_points / 72)
        # Add noise
        noise = np.random.normal(0, noise_level * concentration)
        data[param_name] = concentration + noise
    
    return pd.DataFrame(data)


def simple_simulation(params):
    """Simple simulation function for testing"""
    time_points = np.linspace(0, 72, 50)
    
    results = {'time': time_points}
    
    for param_name, param_value in params.items():
        results[param_name] = 10 * np.exp(-param_value * time_points / 72)
    
    return pd.DataFrame(results)


class TestParameterCalibrator:
    """Test suite for ParameterCalibrator"""
    
    def test_initialization(self):
        """Test calibrator initialization"""
        true_params = {'param1': 0.5, 'param2': 1.0}
        exp_data = create_synthetic_data(true_params)
        time_points = exp_data['time'].values
        target_metabolites = ['param1', 'param2']
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=target_metabolites,
            time_points=time_points
        )
        
        assert calibrator is not None
        assert len(calibrator.target_metabolites) == 2
    
    def test_calibration_simple(self):
        """Test calibration on simple problem"""
        # True parameters
        true_params = {'param1': 0.5}
        exp_data = create_synthetic_data(true_params, noise_level=0.01)
        time_points = exp_data['time'].values
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=['param1'],
            time_points=time_points
        )
        
        # Calibrate with wrong initial guess
        params_to_optimize = {
            'param1': (1.0, 0.1, 2.0)  # initial, lower, upper
        }
        
        result = calibrator.calibrate(
            params_to_optimize=params_to_optimize,
            base_params={},
            method='differential_evolution',
            max_iterations=100
        )
        
        assert result.success
        assert result.r_squared > 0.95
        assert abs(result.optimized_params['param1'] - true_params['param1']) < 0.1
    
    def test_multiple_parameters(self):
        """Test calibration with multiple parameters"""
        true_params = {'param1': 0.5, 'param2': 1.0}
        exp_data = create_synthetic_data(true_params, noise_level=0.01)
        time_points = exp_data['time'].values
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=['param1', 'param2'],
            time_points=time_points
        )
        
        params_to_optimize = {
            'param1': (1.0, 0.1, 2.0),
            'param2': (2.0, 0.5, 3.0)
        }
        
        result = calibrator.calibrate(
            params_to_optimize=params_to_optimize,
            base_params={},
            method='differential_evolution',
            max_iterations=200
        )
        
        assert result.success
        assert result.r_squared > 0.90
        assert len(result.optimized_params) == 2
    
    def test_confidence_intervals(self):
        """Test confidence interval calculation"""
        true_params = {'param1': 0.5}
        exp_data = create_synthetic_data(true_params, noise_level=0.05)
        time_points = exp_data['time'].values
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=['param1'],
            time_points=time_points
        )
        
        params_to_optimize = {'param1': (0.5, 0.1, 2.0)}
        
        result = calibrator.calibrate(
            params_to_optimize=params_to_optimize,
            base_params={},
            method='differential_evolution',
            max_iterations=100,
            confidence_level=0.95
        )
        
        assert 'param1' in result.confidence_intervals
        lower, upper = result.confidence_intervals['param1']
        assert lower < result.optimized_params['param1'] < upper
    
    def test_sensitivity_calculation(self):
        """Test parameter sensitivity calculation"""
        true_params = {'param1': 0.5, 'param2': 1.0}
        exp_data = create_synthetic_data(true_params, noise_level=0.01)
        time_points = exp_data['time'].values
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=['param1', 'param2'],
            time_points=time_points
        )
        
        params_to_optimize = {
            'param1': (0.5, 0.1, 2.0),
            'param2': (1.0, 0.5, 3.0)
        }
        
        result = calibrator.calibrate(
            params_to_optimize=params_to_optimize,
            base_params={},
            method='differential_evolution',
            max_iterations=100
        )
        
        assert len(result.sensitivity) == 2
        assert all(v >= 0 for v in result.sensitivity.values())
    
    def test_different_optimization_methods(self):
        """Test all optimization methods"""
        true_params = {'param1': 0.5}
        exp_data = create_synthetic_data(true_params, noise_level=0.01)
        time_points = exp_data['time'].values
        
        calibrator = ParameterCalibrator(
            simulation_function=simple_simulation,
            experimental_data=exp_data,
            target_metabolites=['param1'],
            time_points=time_points
        )
        
        params_to_optimize = {'param1': (1.0, 0.1, 2.0)}
        
        methods = ['differential_evolution', 'minimize', 'least_squares']
        
        for method in methods:
            result = calibrator.calibrate(
                params_to_optimize=params_to_optimize,
                base_params={},
                method=method,
                max_iterations=100
            )
            
            assert result.success or result.objective_value < 10.0
            print(f"{method}: R² = {result.r_squared:.4f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
