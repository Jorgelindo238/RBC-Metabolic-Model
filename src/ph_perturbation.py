"""
pH Perturbation Module for RBC Metabolic Simulations

This module provides functions to simulate various types of extracellular pH
perturbations and their effects on red blood cell metabolism.

Perturbation types:
- Step: Instantaneous change to a new pH
- Ramp: Gradual linear change over time
- Sinusoidal: Oscillating pH (circadian rhythms, etc.)
- Pulse: Temporary pH shock with return to baseline

Author: RBC Metabolic Model Team
Date: 2025-11-15
"""

import numpy as np
from typing import Dict, Union, Tuple


# ============================================================================
# PERTURBATION CONFIGURATION CLASS
# ============================================================================

class PhPerturbation:
    """
    Class to configure and apply extracellular pH perturbations.
    
    Attributes:
    -----------
    perturbation_type : str
        Type of perturbation ('none', 'step', 'ramp', 'sinusoidal', 'pulse')
    params : dict
        Parameters specific to the perturbation type
    """
    
    def __init__(self, perturbation_type: str = 'none', **kwargs):
        """
        Initialize pH perturbation configuration.
        
        Parameters:
        -----------
        perturbation_type : str
            Type of perturbation
        **kwargs : dict
            Perturbation-specific parameters
        """
        self.perturbation_type = perturbation_type.lower()
        self.params = kwargs
        self._validate_params()
    
    def _validate_params(self):
        """Validate that required parameters are present for the perturbation type."""
        required_params = {
            'none': [],
            'step': ['pH_target', 't_start'],
            'ramp': ['pH_initial', 'pH_final', 't_start', 'duration'],
            'sinusoidal': ['pH_mean', 'amplitude', 'period'],
            'pulse': ['pH_shock', 't_start', 'duration']
        }
        
        if self.perturbation_type not in required_params:
            raise ValueError(f"Unknown perturbation type: {self.perturbation_type}")
        
        missing = [p for p in required_params[self.perturbation_type] 
                   if p not in self.params]
        
        if missing:
            raise ValueError(f"Missing parameters for {self.perturbation_type}: {missing}")
    
    def get_pHe(self, t: float) -> float:
        """
        Get extracellular pH at time t according to perturbation configuration.
        
        Parameters:
        -----------
        t : float
            Current time (hours)
        
        Returns:
        --------
        float
            Extracellular pH value
        """
        if self.perturbation_type == 'none':
            return self._no_perturbation(t)
        elif self.perturbation_type == 'step':
            return self._step_perturbation(t)
        elif self.perturbation_type == 'ramp':
            return self._ramp_perturbation(t)
        elif self.perturbation_type == 'sinusoidal':
            return self._sinusoidal_perturbation(t)
        elif self.perturbation_type == 'pulse':
            return self._pulse_perturbation(t)
        else:
            return 7.4  # Default physiological pH
    
    def _no_perturbation(self, t: float) -> float:
        """No perturbation - constant physiological pH."""
        return self.params.get('pH_baseline', 7.4)
    
    def _step_perturbation(self, t: float) -> float:
        """
        Step perturbation: instantaneous change to new pH at t_start.
        
        Parameters in self.params:
        - pH_target: target pH value
        - t_start: time when step occurs (hours)
        - pH_baseline: initial pH (default 7.4)
        """
        pH_baseline = self.params.get('pH_baseline', 7.4)
        pH_target = self.params['pH_target']
        t_start = self.params['t_start']
        
        if t < t_start:
            return pH_baseline
        else:
            return pH_target
    
    def _ramp_perturbation(self, t: float) -> float:
        """
        Ramp perturbation: linear change from pH_initial to pH_final.
        
        Parameters in self.params:
        - pH_initial: starting pH
        - pH_final: ending pH
        - t_start: time when ramp starts (hours)
        - duration: duration of ramp (hours)
        """
        pH_initial = self.params['pH_initial']
        pH_final = self.params['pH_final']
        t_start = self.params['t_start']
        duration = self.params['duration']
        
        if t < t_start:
            return pH_initial
        elif t < t_start + duration:
            # Linear interpolation
            progress = (t - t_start) / duration
            return pH_initial + progress * (pH_final - pH_initial)
        else:
            return pH_final
    
    def _sinusoidal_perturbation(self, t: float) -> float:
        """
        Sinusoidal perturbation: oscillating pH around mean value.
        
        Parameters in self.params:
        - pH_mean: mean pH value
        - amplitude: oscillation amplitude (pH units)
        - period: oscillation period (hours)
        - phase: phase shift (hours, default 0)
        """
        pH_mean = self.params['pH_mean']
        amplitude = self.params['amplitude']
        period = self.params['period']
        phase = self.params.get('phase', 0.0)
        
        # pH(t) = pH_mean + amplitude * sin(2π * (t - phase) / period)
        omega = 2.0 * np.pi / period
        pH = pH_mean + amplitude * np.sin(omega * (t - phase))
        
        return pH
    
    def _pulse_perturbation(self, t: float) -> float:
        """
        Pulse perturbation: temporary pH shock with return to baseline.
        
        Parameters in self.params:
        - pH_shock: pH during pulse
        - t_start: pulse start time (hours)
        - duration: pulse duration (hours)
        - pH_baseline: baseline pH (default 7.4)
        """
        pH_baseline = self.params.get('pH_baseline', 7.4)
        pH_shock = self.params['pH_shock']
        t_start = self.params['t_start']
        duration = self.params['duration']
        
        if t_start <= t < t_start + duration:
            return pH_shock
        else:
            return pH_baseline
    
    def get_description(self) -> str:
        """Get human-readable description of the perturbation."""
        if self.perturbation_type == 'none':
            return f"No perturbation (pH = {self.params.get('pH_baseline', 7.4)})"
        
        elif self.perturbation_type == 'step':
            return (f"Step perturbation: pH {self.params.get('pH_baseline', 7.4)} → "
                   f"{self.params['pH_target']} at t={self.params['t_start']}h")
        
        elif self.perturbation_type == 'ramp':
            return (f"Ramp perturbation: pH {self.params['pH_initial']} → "
                   f"{self.params['pH_final']} over {self.params['duration']}h "
                   f"(starting at t={self.params['t_start']}h)")
        
        elif self.perturbation_type == 'sinusoidal':
            return (f"Sinusoidal perturbation: pH {self.params['pH_mean']} ± "
                   f"{self.params['amplitude']} (period {self.params['period']}h)")
        
        elif self.perturbation_type == 'pulse':
            return (f"Pulse perturbation: pH shock to {self.params['pH_shock']} "
                   f"for {self.params['duration']}h (starting at t={self.params['t_start']}h)")
        
        return "Unknown perturbation"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_step_perturbation(pH_target: float, t_start: float, 
                             pH_baseline: float = 7.4) -> PhPerturbation:
    """
    Create a step perturbation configuration.
    
    Example:
    --------
    >>> pert = create_step_perturbation(pH_target=7.0, t_start=2.0)
    >>> pH_at_3h = pert.get_pHe(3.0)  # Returns 7.0
    """
    return PhPerturbation('step', pH_target=pH_target, t_start=t_start, 
                         pH_baseline=pH_baseline)


def create_ramp_perturbation(pH_initial: float, pH_final: float, 
                             t_start: float, duration: float) -> PhPerturbation:
    """
    Create a ramp perturbation configuration.
    
    Example:
    --------
    >>> pert = create_ramp_perturbation(pH_initial=7.4, pH_final=7.0, 
    ...                                  t_start=2.0, duration=4.0)
    >>> pH_at_4h = pert.get_pHe(4.0)  # Returns 7.2 (midpoint)
    """
    return PhPerturbation('ramp', pH_initial=pH_initial, pH_final=pH_final,
                         t_start=t_start, duration=duration)


def create_sinusoidal_perturbation(pH_mean: float, amplitude: float, 
                                   period: float, phase: float = 0.0) -> PhPerturbation:
    """
    Create a sinusoidal perturbation configuration.
    
    Example:
    --------
    >>> pert = create_sinusoidal_perturbation(pH_mean=7.4, amplitude=0.3, period=12.0)
    >>> pH_at_6h = pert.get_pHe(6.0)  # Returns 7.4 (mean at quarter period)
    """
    return PhPerturbation('sinusoidal', pH_mean=pH_mean, amplitude=amplitude,
                         period=period, phase=phase)


def create_pulse_perturbation(pH_shock: float, t_start: float, 
                              duration: float, pH_baseline: float = 7.4) -> PhPerturbation:
    """
    Create a pulse perturbation configuration.
    
    Example:
    --------
    >>> pert = create_pulse_perturbation(pH_shock=6.8, t_start=2.0, duration=0.5)
    >>> pH_at_2.2h = pert.get_pHe(2.2)  # Returns 6.8 (during pulse)
    >>> pH_at_3h = pert.get_pHe(3.0)    # Returns 7.4 (after pulse)
    """
    return PhPerturbation('pulse', pH_shock=pH_shock, t_start=t_start,
                         duration=duration, pH_baseline=pH_baseline)


def create_no_perturbation(pH_baseline: float = 7.4) -> PhPerturbation:
    """
    Create a configuration with no perturbation (constant pH).
    
    Example:
    --------
    >>> pert = create_no_perturbation(pH_baseline=7.4)
    >>> pH = pert.get_pHe(10.0)  # Returns 7.4 at all times
    """
    return PhPerturbation('none', pH_baseline=pH_baseline)


# ============================================================================
# PREDEFINED PHYSIOLOGICAL SCENARIOS
# ============================================================================

def get_acidosis_scenario(severity: str = 'moderate') -> PhPerturbation:
    """
    Get predefined acidosis scenario.
    
    Parameters:
    -----------
    severity : str
        'mild', 'moderate', or 'severe'
    
    Returns:
    --------
    PhPerturbation
        Configured perturbation
    """
    scenarios = {
        'mild': {'pH_target': 7.2, 'duration': 4.0},
        'moderate': {'pH_target': 7.0, 'duration': 6.0},
        'severe': {'pH_target': 6.8, 'duration': 8.0}
    }
    
    if severity not in scenarios:
        severity = 'moderate'
    
    params = scenarios[severity]
    return create_ramp_perturbation(pH_initial=7.4, pH_final=params['pH_target'],
                                   t_start=2.0, duration=params['duration'])


def get_alkalosis_scenario(severity: str = 'moderate') -> PhPerturbation:
    """
    Get predefined alkalosis scenario.
    
    Parameters:
    -----------
    severity : str
        'mild', 'moderate', or 'severe'
    
    Returns:
    --------
    PhPerturbation
        Configured perturbation
    """
    scenarios = {
        'mild': {'pH_target': 7.6, 'duration': 4.0},
        'moderate': {'pH_target': 7.7, 'duration': 6.0},
        'severe': {'pH_target': 7.8, 'duration': 8.0}
    }
    
    if severity not in scenarios:
        severity = 'moderate'
    
    params = scenarios[severity]
    return create_ramp_perturbation(pH_initial=7.4, pH_final=params['pH_target'],
                                   t_start=2.0, duration=params['duration'])


def get_circadian_scenario() -> PhPerturbation:
    """
    Get circadian rhythm pH oscillation scenario.
    
    Returns:
    --------
    PhPerturbation
        Configured sinusoidal perturbation (period = 24h)
    """
    return create_sinusoidal_perturbation(pH_mean=7.4, amplitude=0.15, period=24.0)


# ============================================================================
# VISUALIZATION HELPER
# ============================================================================

def plot_perturbation(perturbation: PhPerturbation, t_max: float = 48.0, 
                     n_points: int = 500):
    """
    Plot the pH perturbation profile over time.
    
    Parameters:
    -----------
    perturbation : PhPerturbation
        Perturbation configuration to plot
    t_max : float
        Maximum time for plot (hours)
    n_points : int
        Number of points to plot
    
    Returns:
    --------
    matplotlib.figure.Figure
        The generated figure
    """
    import matplotlib.pyplot as plt
    
    times = np.linspace(0, t_max, n_points)
    pHe_values = [perturbation.get_pHe(t) for t in times]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(times, pHe_values, 'b-', linewidth=2, label='Extracellular pH (pHe)')
    ax.axhline(y=7.4, color='green', linestyle='--', alpha=0.5, 
               label='Normal pHe (7.4)')
    ax.axhline(y=7.2, color='orange', linestyle='--', alpha=0.5, 
               label='Normal pHi (7.2)')
    
    # Shade physiological range
    ax.fill_between(times, 7.35, 7.45, color='green', alpha=0.1, 
                    label='Normal pHe range')
    
    ax.set_xlabel('Time (hours)', fontsize=14, fontweight='bold')
    ax.set_ylabel('pH', fontsize=14, fontweight='bold')
    ax.set_title(f'pH Perturbation Profile\n{perturbation.get_description()}',
                fontsize=16, fontweight='bold')
    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(6.5, 8.0)
    
    plt.tight_layout()
    return fig


# ============================================================================
# TESTING
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("pH PERTURBATION MODULE - TEST")
    print("=" * 70)
    
    # Test each perturbation type
    print("\n1. Step Perturbation:")
    print("-" * 70)
    pert_step = create_step_perturbation(pH_target=7.0, t_start=2.0)
    print(pert_step.get_description())
    for t in [0, 1.5, 2.0, 3.0]:
        print(f"  t={t:.1f}h: pHe = {pert_step.get_pHe(t):.2f}")
    
    print("\n2. Ramp Perturbation:")
    print("-" * 70)
    pert_ramp = create_ramp_perturbation(7.4, 7.0, t_start=2.0, duration=4.0)
    print(pert_ramp.get_description())
    for t in [0, 2.0, 4.0, 6.0, 8.0]:
        print(f"  t={t:.1f}h: pHe = {pert_ramp.get_pHe(t):.2f}")
    
    print("\n3. Sinusoidal Perturbation:")
    print("-" * 70)
    pert_sin = create_sinusoidal_perturbation(7.4, 0.2, period=12.0)
    print(pert_sin.get_description())
    for t in [0, 3, 6, 9, 12]:
        print(f"  t={t:.1f}h: pHe = {pert_sin.get_pHe(t):.2f}")
    
    print("\n4. Pulse Perturbation:")
    print("-" * 70)
    pert_pulse = create_pulse_perturbation(6.8, t_start=2.0, duration=0.5)
    print(pert_pulse.get_description())
    for t in [0, 2.0, 2.2, 2.5, 3.0]:
        print(f"  t={t:.1f}h: pHe = {pert_pulse.get_pHe(t):.2f}")
    
    print("\n5. Predefined Scenarios:")
    print("-" * 70)
    for severity in ['mild', 'moderate', 'severe']:
        pert = get_acidosis_scenario(severity)
        print(f"  Acidosis ({severity}): {pert.get_description()}")
    
    print("\n" + "=" * 70)
    print("✓ pH perturbation module loaded successfully!")
    print("=" * 70)
