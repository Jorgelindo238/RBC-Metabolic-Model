"""
Bohr Effect Module - Hemoglobin-O2 Affinity Modulation by pH and 2,3-BPG

Implements the physiological Bohr effect where changes in pH and 2,3-BPG 
concentration affect hemoglobin's oxygen binding affinity.

Features:
---------
1. pH-dependent P50 (half-saturation pressure)
2. 2,3-BPG modulation of oxygen affinity
3. Temperature effects on oxygen binding
4. Hill equation for cooperative binding
5. Oxygen saturation calculations

Key Relationships:
------------------
- Acidosis (↓pH) → ↑P50 → ↓O2 affinity → Enhanced O2 release to tissues
- Alkalosis (↑pH) → ↓P50 → ↑O2 affinity → Reduced O2 release
- ↑[2,3-BPG] → ↑P50 → ↓O2 affinity → Enhanced O2 release
- ↓[2,3-BPG] → ↓P50 → ↑O2 affinity → Reduced O2 release

Author: Jorgelindo da Veiga
Date: 2025-11-15
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional, Dict
import warnings
warnings.filterwarnings('ignore')


# Physiological constants
NORMAL_P50 = 26.8          # mmHg at pH 7.4, 37°C, normal 2,3-BPG
NORMAL_PH = 7.4            # Normal arterial pH
NORMAL_BPG = 5.0           # mM, normal RBC 2,3-BPG concentration
NORMAL_TEMP = 37.0         # °C, body temperature
HILL_COEFFICIENT = 2.8     # Cooperative binding (2.6-3.0)

# Bohr effect coefficient (ΔlogP50/ΔpH)
BOHR_COEFFICIENT = -0.48   # Typical range: -0.4 to -0.5

# 2,3-BPG effect coefficient
BPG_COEFFICIENT = 0.3      # ΔP50 (mmHg) per mM 2,3-BPG change

# Temperature effect (van't Hoff)
TEMP_COEFFICIENT = 0.024   # ΔlogP50/°C


class BohrEffect:
    """
    Models the Bohr effect and hemoglobin-oxygen binding dynamics.
    """
    
    def __init__(self, 
                 bohr_coeff: float = BOHR_COEFFICIENT,
                 bpg_coeff: float = BPG_COEFFICIENT,
                 temp_coeff: float = TEMP_COEFFICIENT,
                 hill_n: float = HILL_COEFFICIENT):
        """
        Initialize Bohr effect model.
        
        Parameters:
        -----------
        bohr_coeff : float
            Bohr coefficient (ΔlogP50/ΔpH), typically -0.48
        bpg_coeff : float
            2,3-BPG coefficient (ΔP50 per mM)
        temp_coeff : float
            Temperature coefficient (ΔlogP50/°C)
        hill_n : float
            Hill coefficient for cooperative binding
        """
        self.bohr_coeff = bohr_coeff
        self.bpg_coeff = bpg_coeff
        self.temp_coeff = temp_coeff
        self.hill_n = hill_n
        
    def calculate_P50(self, 
                     pH: float,
                     bpg_conc: float = NORMAL_BPG,
                     temperature: float = NORMAL_TEMP) -> float:
        """
        Calculate P50 (half-saturation O2 pressure) for given conditions.
        
        The P50 shifts according to:
        - pH (Bohr effect)
        - 2,3-BPG concentration
        - Temperature
        
        Parameters:
        -----------
        pH : float
            Blood pH
        bpg_conc : float
            2,3-BPG concentration (mM)
        temperature : float
            Temperature (°C)
            
        Returns:
        --------
        float : P50 in mmHg
        """
        # pH effect (Bohr)
        delta_pH = pH - NORMAL_PH
        log_P50_pH = np.log10(NORMAL_P50) + self.bohr_coeff * delta_pH
        
        # 2,3-BPG effect (linear approximation)
        delta_BPG = bpg_conc - NORMAL_BPG
        P50_bpg_correction = self.bpg_coeff * delta_BPG
        
        # Temperature effect
        delta_temp = temperature - NORMAL_TEMP
        log_P50_temp = self.temp_coeff * delta_temp
        
        # Combined P50
        P50 = 10**(log_P50_pH + log_P50_temp) + P50_bpg_correction
        
        return max(P50, 1.0)  # Ensure positive P50
    
    def oxygen_saturation(self, 
                         pO2: float,
                         pH: float = NORMAL_PH,
                         bpg_conc: float = NORMAL_BPG,
                         temperature: float = NORMAL_TEMP) -> float:
        """
        Calculate hemoglobin oxygen saturation using Hill equation.
        
        Hill equation: Y = (pO2^n) / (P50^n + pO2^n)
        
        Parameters:
        -----------
        pO2 : float
            Partial pressure of O2 (mmHg)
        pH : float
            Blood pH
        bpg_conc : float
            2,3-BPG concentration (mM)
        temperature : float
            Temperature (°C)
            
        Returns:
        --------
        float : O2 saturation (0-1)
        """
        P50 = self.calculate_P50(pH, bpg_conc, temperature)
        
        # Hill equation
        pO2_n = pO2 ** self.hill_n
        P50_n = P50 ** self.hill_n
        
        saturation = pO2_n / (P50_n + pO2_n)
        
        return np.clip(saturation, 0.0, 1.0)
    
    def oxygen_dissociation_curve(self,
                                  pH: float = NORMAL_PH,
                                  bpg_conc: float = NORMAL_BPG,
                                  temperature: float = NORMAL_TEMP,
                                  pO2_range: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate oxygen dissociation curve (ODC).
        
        Parameters:
        -----------
        pH : float
            Blood pH
        bpg_conc : float
            2,3-BPG concentration (mM)
        temperature : float
            Temperature (°C)
        pO2_range : np.ndarray, optional
            Range of pO2 values (mmHg)
            
        Returns:
        --------
        tuple : (pO2_values, saturation_values)
        """
        if pO2_range is None:
            pO2_range = np.linspace(0, 100, 200)
        
        saturations = np.array([
            self.oxygen_saturation(pO2, pH, bpg_conc, temperature)
            for pO2 in pO2_range
        ])
        
        return pO2_range, saturations
    
    def oxygen_content(self,
                      pO2: float,
                      pH: float = NORMAL_PH,
                      bpg_conc: float = NORMAL_BPG,
                      hemoglobin: float = 15.0) -> float:
        """
        Calculate total oxygen content in blood.
        
        O2 content = (Hb-bound O2) + (Dissolved O2)
        
        Parameters:
        -----------
        pO2 : float
            Partial pressure O2 (mmHg)
        pH : float
            Blood pH
        bpg_conc : float
            2,3-BPG concentration (mM)
        hemoglobin : float
            Hemoglobin concentration (g/dL)
            
        Returns:
        --------
        float : O2 content (mL O2 / dL blood)
        """
        # Hb-bound O2
        saturation = self.oxygen_saturation(pO2, pH, bpg_conc)
        O2_capacity = 1.34 * hemoglobin  # mL O2 per dL blood (Hüfner constant)
        O2_bound = saturation * O2_capacity
        
        # Dissolved O2
        O2_dissolved = 0.003 * pO2  # Henry's law (mL O2/dL blood per mmHg)
        
        return O2_bound + O2_dissolved
    
    def plot_bohr_shift(self,
                       pH_conditions: Dict[str, float],
                       bpg_conc: float = NORMAL_BPG,
                       output_path: Optional[str] = None):
        """
        Plot oxygen dissociation curves showing Bohr shift.
        
        Parameters:
        -----------
        pH_conditions : dict
            Dictionary of {label: pH_value}
        bpg_conc : float
            2,3-BPG concentration (mM)
        output_path : str, optional
            Path to save plot
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Oxygen dissociation curves
        colors = ['blue', 'green', 'red', 'purple', 'orange']
        
        for idx, (label, pH) in enumerate(pH_conditions.items()):
            pO2_vals, sat_vals = self.oxygen_dissociation_curve(pH, bpg_conc)
            P50 = self.calculate_P50(pH, bpg_conc)
            
            color = colors[idx % len(colors)]
            ax1.plot(pO2_vals, sat_vals * 100, linewidth=2.5, 
                    label=f'{label} (pH {pH:.2f}, P50={P50:.1f} mmHg)',
                    color=color, marker='o', markersize=3, markevery=20)
            
            # Mark P50 point
            ax1.plot(P50, 50, 'o', markersize=10, color=color, 
                    markerfacecolor='white', markeredgewidth=2)
        
        ax1.axhline(50, color='gray', linestyle='--', alpha=0.5, label='50% saturation')
        ax1.axvline(40, color='gray', linestyle=':', alpha=0.3, label='Venous pO2')
        ax1.axvline(100, color='gray', linestyle=':', alpha=0.3, label='Arterial pO2')
        
        ax1.set_xlabel('pO2 (mmHg)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('O2 Saturation (%)', fontsize=12, fontweight='bold')
        ax1.set_title('Bohr Effect: O2 Dissociation Curves', fontsize=14, fontweight='bold')
        ax1.legend(loc='lower right', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, 100)
        ax1.set_ylim(0, 100)
        
        # Plot 2: P50 vs pH
        pH_range = np.linspace(6.8, 7.8, 50)
        P50_values = [self.calculate_P50(pH, bpg_conc) for pH in pH_range]
        
        ax2.plot(pH_range, P50_values, 'b-', linewidth=3, label='P50 vs pH')
        ax2.axhline(NORMAL_P50, color='gray', linestyle='--', alpha=0.5, 
                   label=f'Normal P50 ({NORMAL_P50:.1f} mmHg)')
        ax2.axvline(NORMAL_PH, color='gray', linestyle='--', alpha=0.5,
                   label=f'Normal pH ({NORMAL_PH:.1f})')
        
        # Mark specific pH conditions
        for idx, (label, pH) in enumerate(pH_conditions.items()):
            P50 = self.calculate_P50(pH, bpg_conc)
            color = colors[idx % len(colors)]
            ax2.plot(pH, P50, 'o', markersize=12, color=color,
                    markerfacecolor='white', markeredgewidth=3)
            ax2.text(pH, P50 + 1.5, label, fontsize=9, ha='center',
                    bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
        
        ax2.set_xlabel('pH', fontsize=12, fontweight='bold')
        ax2.set_ylabel('P50 (mmHg)', fontsize=12, fontweight='bold')
        ax2.set_title('P50 Shift with pH (Bohr Coefficient)', fontsize=14, fontweight='bold')
        ax2.legend(loc='best', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"[OK] Bohr shift plot saved: {output_path}")
        
        plt.close()
    
    def plot_bpg_effect(self,
                       bpg_conditions: Dict[str, float],
                       pH: float = NORMAL_PH,
                       output_path: Optional[str] = None):
        """
        Plot effect of 2,3-BPG on oxygen dissociation curves.
        
        Parameters:
        -----------
        bpg_conditions : dict
            Dictionary of {label: BPG_concentration}
        pH : float
            Blood pH
        output_path : str, optional
            Path to save plot
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        colors = ['blue', 'green', 'red', 'purple', 'orange']
        
        # Plot 1: Oxygen dissociation curves
        for idx, (label, bpg) in enumerate(bpg_conditions.items()):
            pO2_vals, sat_vals = self.oxygen_dissociation_curve(pH, bpg)
            P50 = self.calculate_P50(pH, bpg)
            
            color = colors[idx % len(colors)]
            ax1.plot(pO2_vals, sat_vals * 100, linewidth=2.5,
                    label=f'{label} ([2,3-BPG]={bpg:.1f} mM, P50={P50:.1f} mmHg)',
                    color=color, marker='s', markersize=3, markevery=20)
            
            # Mark P50
            ax1.plot(P50, 50, 's', markersize=10, color=color,
                    markerfacecolor='white', markeredgewidth=2)
        
        ax1.axhline(50, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel('pO2 (mmHg)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('O2 Saturation (%)', fontsize=12, fontweight='bold')
        ax1.set_title('2,3-BPG Effect on O2 Binding', fontsize=14, fontweight='bold')
        ax1.legend(loc='lower right', fontsize=9)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, 100)
        ax1.set_ylim(0, 100)
        
        # Plot 2: P50 vs 2,3-BPG
        bpg_range = np.linspace(0, 10, 50)
        P50_values = [self.calculate_P50(pH, bpg) for bpg in bpg_range]
        
        ax2.plot(bpg_range, P50_values, 'r-', linewidth=3, label='P50 vs [2,3-BPG]')
        ax2.axhline(NORMAL_P50, color='gray', linestyle='--', alpha=0.5,
                   label=f'Normal P50')
        ax2.axvline(NORMAL_BPG, color='gray', linestyle='--', alpha=0.5,
                   label=f'Normal [2,3-BPG] ({NORMAL_BPG:.1f} mM)')
        
        # Mark specific BPG conditions
        for idx, (label, bpg) in enumerate(bpg_conditions.items()):
            P50 = self.calculate_P50(pH, bpg)
            color = colors[idx % len(colors)]
            ax2.plot(bpg, P50, 's', markersize=12, color=color,
                    markerfacecolor='white', markeredgewidth=3)
            ax2.text(bpg, P50 + 1, label, fontsize=9, ha='center',
                    bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))
        
        ax2.set_xlabel('[2,3-BPG] (mM)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('P50 (mmHg)', fontsize=12, fontweight='bold')
        ax2.set_title('P50 Modulation by 2,3-BPG', fontsize=14, fontweight='bold')
        ax2.legend(loc='best', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"[OK] 2,3-BPG effect plot saved: {output_path}")
        
        plt.close()
    
    def oxygen_delivery_to_tissues(self,
                                   arterial_pO2: float = 100.0,
                                   venous_pO2: float = 40.0,
                                   pH_arterial: float = NORMAL_PH,
                                   pH_venous: float = 7.38,
                                   bpg_conc: float = NORMAL_BPG,
                                   hemoglobin: float = 15.0) -> Dict[str, float]:
        """
        Calculate oxygen delivery considering Bohr effect.
        
        Parameters:
        -----------
        arterial_pO2 : float
            Arterial pO2 (mmHg)
        venous_pO2 : float
            Venous pO2 (mmHg)
        pH_arterial : float
            Arterial pH
        pH_venous : float
            Venous pH (typically 0.02 lower)
        bpg_conc : float
            2,3-BPG concentration (mM)
        hemoglobin : float
            Hemoglobin concentration (g/dL)
            
        Returns:
        --------
        dict : O2 delivery metrics
        """
        # Arterial O2 content
        O2_arterial = self.oxygen_content(arterial_pO2, pH_arterial, bpg_conc, hemoglobin)
        
        # Venous O2 content (with Bohr effect)
        O2_venous = self.oxygen_content(venous_pO2, pH_venous, bpg_conc, hemoglobin)
        
        # O2 extraction
        O2_extracted = O2_arterial - O2_venous
        extraction_fraction = O2_extracted / O2_arterial if O2_arterial > 0 else 0
        
        return {
            'O2_arterial_mL_per_dL': O2_arterial,
            'O2_venous_mL_per_dL': O2_venous,
            'O2_extracted_mL_per_dL': O2_extracted,
            'extraction_fraction': extraction_fraction,
            'sat_arterial': self.oxygen_saturation(arterial_pO2, pH_arterial, bpg_conc),
            'sat_venous': self.oxygen_saturation(venous_pO2, pH_venous, bpg_conc),
            'P50_arterial': self.calculate_P50(pH_arterial, bpg_conc),
            'P50_venous': self.calculate_P50(pH_venous, bpg_conc)
        }


def demonstrate_bohr_effect(output_dir: str = "html/brodbar/bohr_effect"):
    """
    Demonstrate Bohr effect with comprehensive plots.
    
    Parameters:
    -----------
    output_dir : str
        Directory for saving plots
    """
    from pathlib import Path
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*70)
    print("BOHR EFFECT DEMONSTRATION")
    print("="*70 + "\n")
    
    bohr = BohrEffect()
    
    # 1. pH effect (Bohr shift)
    print("1. Generating Bohr shift plots (pH effect)...")
    pH_conditions = {
        'Severe Acidosis': 6.9,
        'Mild Acidosis': 7.2,
        'Normal': 7.4,
        'Mild Alkalosis': 7.6,
        'Severe Alkalosis': 7.7
    }
    
    bohr.plot_bohr_shift(
        pH_conditions,
        output_path=str(output_dir / "bohr_shift_pH.png")
    )
    
    # 2. 2,3-BPG effect
    print("2. Generating 2,3-BPG effect plots...")
    bpg_conditions = {
        'Low 2,3-BPG': 2.0,
        'Normal': 5.0,
        'High 2,3-BPG': 8.0
    }
    
    bohr.plot_bpg_effect(
        bpg_conditions,
        output_path=str(output_dir / "bpg_effect.png")
    )
    
    # 3. O2 delivery analysis
    print("\n3. Analyzing O2 delivery to tissues...")
    
    scenarios = {
        'Normal': {'pH_v': 7.38, 'bpg': 5.0},
        'Acidosis': {'pH_v': 7.30, 'bpg': 8.0},
        'Alkalosis': {'pH_v': 7.46, 'bpg': 3.0}
    }
    
    print(f"\n{'Scenario':<15} {'O2 Art':<10} {'O2 Ven':<10} {'Extracted':<10} {'Fraction':<10}")
    print("-" * 60)
    
    for name, params in scenarios.items():
        delivery = bohr.oxygen_delivery_to_tissues(
            pH_venous=params['pH_v'],
            bpg_conc=params['bpg']
        )
        
        print(f"{name:<15} {delivery['O2_arterial_mL_per_dL']:<10.2f} "
              f"{delivery['O2_venous_mL_per_dL']:<10.2f} "
              f"{delivery['O2_extracted_mL_per_dL']:<10.2f} "
              f"{delivery['extraction_fraction']:<10.2%}")
    
    print("\n" + "="*70)
    print("[OK] BOHR EFFECT DEMONSTRATION COMPLETE")
    print(f"  Plots saved to: {output_dir}")
    print("="*70 + "\n")


if __name__ == "__main__":
    """
    Demonstrate Bohr effect.
    """
    demonstrate_bohr_effect()
