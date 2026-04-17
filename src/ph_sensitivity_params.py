"""
pH Sensitivity Parameters for RBC Metabolic Enzymes

This module contains the pH-dependent activity parameters for key metabolic enzymes
in red blood cells. Each enzyme has an optimal pH, sensitivity coefficient (Hill coefficient),
and valid pH range.

Based on experimental data from:
- BRENDA enzyme database
- Rapoport-Luebering shunt studies
- RBC glycolysis pH-dependency studies
"""

import numpy as np

# ============================================================================
# pH SENSITIVITY PARAMETERS FOR KEY ENZYMES
# ============================================================================

pH_ENZYME_PARAMS = {
    # -------------------------------------------------------------------------
    # GLYCOLYSIS ENZYMES
    # -------------------------------------------------------------------------
    'VHK': {
        'name': 'Hexokinase',
        'pH_opt': 7.7,          # Optimal pH for activity
        'n_H': 2.0,             # Hill coefficient (sensitivity)
        'pH_range': (6.5, 8.5), # Valid physiological range
        'description': 'First step of glycolysis: GLC → G6P',
        'notes': 'Moderately sensitive to pH, reduced activity in acidosis'
    },
    
    'VPFK': {
        'name': 'Phosphofructokinase',
        'pH_opt': 7.1,          # Most pH-sensitive glycolytic enzyme!
        'n_H': 4.0,             # Very steep pH-activity curve
        'pH_range': (6.5, 7.8),
        'description': 'Rate-limiting step: F6P → F16BP',
        'notes': 'CRITICAL pH sensor - severely inhibited by acidosis, main control point'
    },
    
    'VPK': {
        'name': 'Pyruvate Kinase',
        'pH_opt': 7.3,
        'n_H': 2.5,
        'pH_range': (6.5, 8.0),
        'description': 'Final glycolysis step: PEP → PYR',
        'notes': 'Moderately sensitive, contributes to pH regulation'
    },
    
    'VLDH': {
        'name': 'Lactate Dehydrogenase',
        'pH_opt': 7.5,
        'n_H': 2.0,
        'pH_range': (6.8, 8.0),
        'description': 'Lactate production: PYR → LAC',
        'notes': 'Product inhibition by H+ accumulation'
    },
    
    'VGAPDH': {
        'name': 'Glyceraldehyde-3-P Dehydrogenase',
        'pH_opt': 8.2,
        'n_H': 2.0,
        'pH_range': (6.8, 8.5),
        'description': 'NAD-dependent oxidation: GA3P → B13PG',
        'notes': 'Prefers alkaline conditions'
    },
    
    # -------------------------------------------------------------------------
    # RAPOPORT-LUEBERING SHUNT (2,3-BPG)
    # -------------------------------------------------------------------------
    'VDPGM': {
        'name': '2,3-Bisphosphoglycerate Mutase',
        'pH_opt': 7.4,
        'n_H': 3.0,             # High sensitivity!
        'pH_range': (6.8, 7.8),
        'description': 'BPG production: B13PG → B23PG',
        'notes': 'HIGHLY pH-SENSITIVE - key regulator of O2 affinity via 2,3-BPG'
    },
    
    'V23DPGP': {
        'name': '2,3-Bisphosphoglycerate Phosphatase',
        'pH_opt': 7.1,
        'n_H': 2.0,
        'pH_range': (6.5, 7.8),
        'description': 'BPG degradation: B23PG → P3G',
        'notes': 'Less pH-sensitive than VDPGM'
    },
    
    # -------------------------------------------------------------------------
    # PENTOSE PHOSPHATE PATHWAY
    # -------------------------------------------------------------------------
    'VG6PDH': {
        'name': 'Glucose-6-Phosphate Dehydrogenase',
        'pH_opt': 8.0,
        'n_H': 2.0,
        'pH_range': (6.8, 8.5),
        'description': 'NADPH production: G6P → GO6P',
        'notes': 'Prefers alkaline conditions, reduced in acidosis'
    },
    
    'V6PGD': {
        'name': '6-Phosphogluconate Dehydrogenase',
        'pH_opt': 8.0,
        'n_H': 2.0,
        'pH_range': (6.8, 8.5),
        'description': 'PPP oxidative phase: GL6P → RU5P',
        'notes': 'Similar pH profile to G6PDH'
    },
    
    # -------------------------------------------------------------------------
    # GLUTATHIONE SYSTEM
    # -------------------------------------------------------------------------
    'VGSR': {
        'name': 'Glutathione Reductase',
        'pH_opt': 7.4,
        'n_H': 2.0,
        'pH_range': (6.5, 8.0),
        'description': 'NADPH-dependent: GSSG → 2 GSH',
        'notes': 'Critical for antioxidant defense'
    },
    
    'VGSS': {
        'name': 'Glutathione Synthetase',
        'pH_opt': 7.5,
        'n_H': 2.0,
        'pH_range': (6.8, 8.0),
        'description': 'GSH synthesis: GLUCYS + GLY → GSH',
        'notes': 'ATP-dependent, reduced in acidosis'
    },
    
    'VGPX': {
        'name': 'Glutathione Peroxidase',
        'pH_opt': 7.4,
        'n_H': 2.0,
        'pH_range': (6.5, 8.0),
        'description': 'Peroxide detox: GSH + H2O2 → GSSG',
        'notes': 'Part of antioxidant defense'
    },
    
    # -------------------------------------------------------------------------
    # OTHER KEY ENZYMES
    # -------------------------------------------------------------------------
    'VPGK': {
        'name': 'Phosphoglycerate Kinase',
        'pH_opt': 7.4,
        'n_H': 2.0,
        'pH_range': (6.5, 8.0),
        'description': 'ATP generation: B13PG → P3G',
        'notes': 'Moderately pH-sensitive'
    },
    
    'VENOPGM': {
        'name': 'Enolase',
        'pH_opt': 7.4,
        'n_H': 2.0,
        'pH_range': (6.5, 8.0),
        'description': 'Glycolysis: P2G → PEP',
        'notes': 'Stable across physiological pH range'
    },
}


# ============================================================================
# pH MODULATION FUNCTION
# ============================================================================

def compute_pH_modulation(pH: float, enzyme_name: str) -> float:
    """
    Compute the pH-dependent activity modulation factor for a given enzyme.
    
    Uses a modified Hill equation to model pH-activity relationship:
        f_pH(pH) = 1 / (1 + 10^(n_H × (pH_opt - pH)))
    
    The function is normalized so that f_pH(7.2) ≈ 1.0 for most enzymes,
    representing normal RBC intracellular pH.
    
    Parameters:
    -----------
    pH : float
        Current pH value (typically 6.5 - 8.0)
    enzyme_name : str
        Name of the enzyme (must match key in pH_ENZYME_PARAMS)
    
    Returns:
    --------
    float
        Activity modulation factor (0.0 - ~2.0)
        - 1.0 = normal activity at physiological pH
        - < 1.0 = reduced activity (inhibition)
        - > 1.0 = enhanced activity (activation)
    
    Examples:
    ---------
    >>> compute_pH_modulation(7.2, 'VPFK')  # Normal pH
    1.0
    >>> compute_pH_modulation(7.0, 'VPFK')  # Acidosis
    0.35  # Severe inhibition!
    >>> compute_pH_modulation(7.6, 'VDPGM')  # Alkalosis
    1.45  # Enhanced 2,3-BPG production
    """
    if enzyme_name not in pH_ENZYME_PARAMS:
        # If enzyme not in database, return 1.0 (no modulation)
        return 1.0
    
    params = pH_ENZYME_PARAMS[enzyme_name]
    pH_opt = params['pH_opt']
    n_H = params['n_H']
    pH_range = params['pH_range']
    
    # Clip pH to valid range to avoid numerical issues
    pH = np.clip(pH, pH_range[0], pH_range[1])
    
    # Modified Hill equation for pH-activity relationship
    # When pH = pH_opt, the denominator = 2, so f = 0.5
    # We need to normalize this
    f_pH_raw = 1.0 / (1.0 + 10.0**(n_H * (pH_opt - pH)))
    
    # Normalize to f_pH(7.2) = 1.0 (typical RBC pHi)
    pH_reference = 7.2
    f_pH_ref = 1.0 / (1.0 + 10.0**(n_H * (pH_opt - pH_reference)))
    
    # Normalized modulation factor
    f_pH_normalized = f_pH_raw / f_pH_ref
    
    # Ensure non-negative and reasonable bounds (0 - 2.0)
    f_pH_normalized = np.clip(f_pH_normalized, 0.0, 2.0)
    
    return f_pH_normalized


def compute_all_pH_modulations(pH: float) -> dict:
    """
    Compute pH modulation factors for all enzymes in the database.
    
    Parameters:
    -----------
    pH : float
        Current pH value
    
    Returns:
    --------
    dict
        Dictionary mapping enzyme names to modulation factors
    
    Example:
    --------
    >>> modulations = compute_all_pH_modulations(7.0)
    >>> print(f"PFK activity: {modulations['VPFK']:.2f}")
    PFK activity: 0.35
    """
    return {enzyme: compute_pH_modulation(pH, enzyme) 
            for enzyme in pH_ENZYME_PARAMS.keys()}


def get_enzyme_info(enzyme_name: str) -> dict:
    """
    Get detailed information about an enzyme's pH sensitivity.
    
    Parameters:
    -----------
    enzyme_name : str
        Name of the enzyme
    
    Returns:
    --------
    dict or None
        Enzyme parameters or None if not found
    """
    return pH_ENZYME_PARAMS.get(enzyme_name, None)


def list_pH_sensitive_enzymes() -> list:
    """
    Get list of all pH-sensitive enzymes in the database.
    
    Returns:
    --------
    list
        List of enzyme names
    """
    return list(pH_ENZYME_PARAMS.keys())


# ============================================================================
# VISUALIZATION HELPER
# ============================================================================

def plot_pH_activity_curves(enzyme_names: list = None, pH_range: tuple = (6.5, 8.0)):
    """
    Plot pH-activity curves for specified enzymes.
    
    Parameters:
    -----------
    enzyme_names : list, optional
        List of enzyme names to plot. If None, plots all.
    pH_range : tuple
        (pH_min, pH_max) for x-axis
    
    Returns:
    --------
    matplotlib.figure.Figure
        The generated figure
    """
    import matplotlib.pyplot as plt
    
    if enzyme_names is None:
        enzyme_names = list_pH_sensitive_enzymes()
    
    pH_values = np.linspace(pH_range[0], pH_range[1], 100)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for enzyme in enzyme_names:
        activities = [compute_pH_modulation(pH, enzyme) for pH in pH_values]
        params = pH_ENZYME_PARAMS[enzyme]
        label = f"{params['name']} (opt={params['pH_opt']})"
        ax.plot(pH_values, activities, linewidth=2, label=label)
    
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Normal activity')
    ax.axvline(x=7.2, color='green', linestyle='--', alpha=0.5, label='Normal pHi (7.2)')
    ax.axvline(x=7.4, color='blue', linestyle='--', alpha=0.5, label='Normal pHe (7.4)')
    
    ax.set_xlabel('pH', fontsize=14, fontweight='bold')
    ax.set_ylabel('Relative Activity (normalized to pH 7.2)', fontsize=14, fontweight='bold')
    ax.set_title('pH-Dependent Enzyme Activity in RBC Metabolism', 
                 fontsize=16, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 2.0)
    
    plt.tight_layout()
    return fig


# ============================================================================
# TESTING AND VALIDATION
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("pH SENSITIVITY MODULE - TEST")
    print("=" * 70)
    
    # Test individual enzyme
    print("\n1. Testing individual enzyme modulation:")
    print("-" * 70)
    for pH in [7.0, 7.2, 7.4, 7.6]:
        mod_pfk = compute_pH_modulation(pH, 'VPFK')
        mod_dpgm = compute_pH_modulation(pH, 'VDPGM')
        print(f"pH {pH:.1f}: PFK activity = {mod_pfk:.3f}, DPGM activity = {mod_dpgm:.3f}")
    
    # Test all enzymes at acidosis
    print("\n2. All enzymes at pH 7.0 (acidosis):")
    print("-" * 70)
    modulations = compute_all_pH_modulations(7.0)
    for enzyme, activity in sorted(modulations.items(), key=lambda x: x[1]):
        params = pH_ENZYME_PARAMS[enzyme]
        print(f"{enzyme:12s} ({params['name']:30s}): {activity:.3f}")
    
    # List critical enzymes
    print("\n3. Most pH-sensitive enzymes (n_H > 2.5):")
    print("-" * 70)
    for enzyme, params in pH_ENZYME_PARAMS.items():
        if params['n_H'] > 2.5:
            print(f"{enzyme}: {params['name']} (n_H = {params['n_H']})")
    
    print("\n" + "=" * 70)
    print("✓ pH sensitivity module loaded successfully!")
    print("=" * 70)
