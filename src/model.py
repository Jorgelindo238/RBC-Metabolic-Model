"""
Python equivalent of the equadiff.m MATLAB function.
This module defines the metabolic model and differential equations.
"""
import os
import numpy as np
from parse import parse


def mm(substrate, km, n=1):
    """
    Michaelis-Menten kinetic function.
    
    Parameters:
    -----------
    substrate : float
        Substrate concentration
    km : float
        Michaelis-Menten constant
    n : int, optional
        Hill coefficient
        
    Returns:
    --------
    float
        Reaction rate
    """
    return substrate ** n / (km ** n + substrate ** n)


def activation(activator, k_act, n=1):
    """
    Activation function for enzyme regulation.
    
    Parameters:
    -----------
    activator : float
        Activator concentration
    k_act : float
        Activation constant
    n : int, optional
        Hill coefficient
        
    Returns:
    --------
    float
        Activation factor
    """
    return activator ** n / (k_act ** n + activator ** n)


def inhibition(inhibitor, k_inh, n=1):
    """
    Inhibition function for enzyme regulation.
    
    Parameters:
    -----------
    inhibitor : float
        Inhibitor concentration
    k_inh : float
        Inhibition constant
    n : int, optional
        Hill coefficient
        
    Returns:
    --------
    float
        Inhibition factor
    """
    return k_inh ** n / (k_inh ** n + inhibitor ** n)


def calculate_derivatives(t, x, model):
    """
    Calculate the derivatives for all metabolites at a given time and state.
    This is the Python equivalent of the equadiff.m MATLAB function.
    
    Parameters:
    -----------
    t : float
        Current time
    x : numpy.ndarray
        Current state vector
    model : dict
        Metabolic model from parse.py
        
    Returns:
    --------
    numpy.ndarray
        Derivatives for all metabolites
    """
    # Initialize derivatives vector
    dxdt = np.zeros(len(model['metab']))
    
    # Define parameter values (equivalent to the MATLAB code)
    # Maximum reaction rates (vmax values)
    vmax = {}
    for i in range(1, 97):
        vmax_name = f'vmax_V{i}'
        vmax[vmax_name] = 0.0001
    
    # Special cases
    vmax['vmax_V23DPGP'] = 0.0001
    vmax['vmax_V6PGD'] = 0.0001
    vmax['vmax_VACLY'] = 0.0001
    vmax['vmax_VADA'] = 0.0001
    vmax['vmax_VADSL'] = 0.0001
    vmax['vmax_VADSS'] = 0.0001
    vmax['vmax_VAHCY'] = 0.0001
    vmax['vmax_VAK'] = 0.0001
    vmax['vmax_VAK2'] = 0.0001
    vmax['vmax_VALATA'] = 0.0001
    vmax['vmax_VAMPD1'] = 0.0001
    vmax['vmax_VAPRT'] = 0.0001
    vmax['vmax_VASL'] = 0.0001
    vmax['vmax_VASPTA'] = 0.0001
    vmax['vmax_VASS'] = 0.0001
    vmax['vmax_VASTA'] = 0.0001
    vmax['vmax_VCBS'] = 0.0001
    vmax['vmax_VCSE'] = 0.0001
    vmax['vmax_VCYSGLY'] = 0.0001
    vmax['vmax_VDPGM'] = 0.0001
    vmax['vmax_VEADE'] = 0.0001
    vmax['vmax_VEADO'] = 0.0001
    vmax['vmax_VEALA'] = 0.0001
    vmax['vmax_VEASP'] = 0.0001
    vmax['vmax_VECIT'] = 0.0001
    vmax['vmax_VECYS'] = 0.0001
    vmax['vmax_VECYT'] = 0.0001
    vmax['vmax_VEFUM'] = 0.0001
    vmax['vmax_VEGLC'] = 0.0001
    vmax['vmax_VEGLN'] = 0.0001
    vmax['vmax_VEGLU'] = 0.0001
    vmax['vmax_VEHYPX'] = 0.0001
    vmax['vmax_VEINO'] = 0.0001
    vmax['vmax_VELAC'] = 0.0001
    vmax['vmax_VEMAL'] = 0.0001
    vmax['vmax_VEMET'] = 0.0001
    vmax['vmax_VENH4'] = 0.0001
    vmax['vmax_VENOPGM'] = 0.0001
    vmax['vmax_VEPYR'] = 0.0001
    vmax['vmax_VEUREA'] = 0.0001
    vmax['vmax_VEURT'] = 0.0001
    vmax['vmax_VEXAN'] = 0.0001
    vmax['vmax_VFDPA'] = 0.0001
    vmax['vmax_VFUM'] = 0.0001
    vmax['vmax_VG6PDH'] = 0.0001
    vmax['vmax_VGAPDH'] = 0.0001
    vmax['vmax_VGDH'] = 0.0001
    vmax['vmax_VGENASP'] = 0.0001
    vmax['vmax_VGGCT'] = 0.0001
    vmax['vmax_VGGT'] = 0.0001
    vmax['vmax_VGLNS'] = 0.0001
    vmax['vmax_VGLUCYS'] = 0.0001
    vmax['vmax_VGLUS'] = 0.0001
    vmax['vmax_VGMPS'] = 0.0001
    vmax['vmax_VGSR'] = 0.0001
    vmax['vmax_VGSS'] = 0.0001
    vmax['vmax_VHGPRT1'] = 0.0001
    vmax['vmax_VHGPRT2'] = 0.0001
    vmax['vmax_VHK'] = 0.0001
    vmax['vmax_VIMPH'] = 0.0001
    vmax['vmax_VLDH'] = 0.0001
    vmax['vmax_VME'] = 0.0001
    vmax['vmax_VMESE'] = 0.0001
    vmax['vmax_VMLD'] = 0.0001
    vmax['vmax_Vnucleo2'] = 0.0001
    vmax['vmax_VOPRIBT'] = 0.0001
    vmax['vmax_VORN'] = 0.0001
    vmax['vmax_VPC'] = 0.0001
    vmax['vmax_VPFK'] = 0.0001
    vmax['vmax_VPGI'] = 0.0001
    vmax['vmax_VPGK'] = 0.0001
    vmax['vmax_VPGLS'] = 0.0001
    vmax['vmax_VPGM'] = 0.0001
    vmax['vmax_VPK'] = 0.0001
    vmax['vmax_VPNPase1'] = 0.0001
    vmax['vmax_Vpolyam'] = 0.0001
    vmax['vmax_VPRPPASe'] = 0.0001
    vmax['vmax_VR5PE'] = 0.0001
    vmax['vmax_VR5PI'] = 0.0001
    vmax['vmax_VRKa'] = 0.0001
    vmax['vmax_VRKb'] = 0.0001
    vmax['vmax_VSAH'] = 0.0001
    vmax['vmax_VSAM'] = 0.0001
    vmax['vmax_VTAL'] = 0.0001
    vmax['vmax_VTKL1'] = 0.0001
    vmax['vmax_VTKL2'] = 0.0001
    vmax['vmax_VTPI'] = 0.0001
    vmax['vmax_VXAO'] = 0.0001
    vmax['vmax_VXAO2'] = 0.0001
    vmax['vmax_VH2O2'] = 0.0001
    
    # Reverse reaction rates
    vmaxr = {}
    for reaction in ['VACLY', 'VADSL', 'VAHCY', 'VAK', 'VAK2', 'VALATA', 'VAMPD1', 'VASL', 
                    'VASPTA', 'VASTA', 'VCBS', 'VCSE', 'VCYSGLY', 'VDPGM', 'VEALA', 'VEASP', 
                    'VEGLN', 'VEGLU', 'VEMAL', 'VENOPGM', 'VFDPA', 'VFUM', 'VG6PDH', 'VGAPDH', 
                    'VGDH', 'VGGT', 'VGLNS', 'VGLUS', 'VGSR', 'VHK', 'VLDH', 'VME', 'VMLD', 
                    'VPC', 'VPFK', 'VPGI', 'VPGK', 'VPGLS', 'VPGM', 'VPK', 'VR5PE', 'VR5PI', 
                    'VSAH', 'VTAL', 'VTKL1', 'VTKL2', 'VTPI', 'VRKb']:
        vmaxr[f'vmaxr_{reaction}'] = 1e-06
    
    # Michaelis-Menten constants (km values) - all set to 0.2
    km = {}
    for metabolite in ['AA', 'ACCOA', 'ADE', 'ADESUC', 'ADO', 'ADOMET', 'ADP', 'ADP_ATP ', 
                      'AKG', 'ALA', 'AMP', 'ARG', 'ARGSUC', 'ASP', 'ATP', 'ATP_ADP', 'B13PG', 
                      'B23PG', 'CIT', 'CITR', 'COA', 'CYS', 'CYSGLY', 'CYSTHIO', 'CYT', 'D2RIBP', 
                      'DEOXYINO', 'DHCP', 'E4P', 'EADE', 'EADO', 'EALA', 'EASP', 'ECIT', 'ECYS', 
                      'ECYT', 'EFUM', 'EGLC', 'EGLN', 'EGLU', 'EHYPX', 'EINO', 'ELAC', 'EMAL', 
                      'EMET', 'ENH4', 'EPYR', 'EUREA', 'EURT', 'EXAN', 'F16BP', 'F6P', 'FUM', 
                      'G6P', 'GA3P', 'GDP', 'GL6P', 'GLC', 'GLN', 'GLU', 'GLUAA', 'GLUCYS', 
                      'GLY', 'GMP', 'GO6P', 'GSH', 'GSSG', 'GTP', 'GUA', 'H2O2', 'HCYS', 'HYPX', 
                      'IMP', 'INO', 'LAC', 'MAL', 'MET', 'METCYT', 'METTHF', 'NAD', 'NAD_NADH ', 
                      'NADH', 'NADH_NAD ', 'NADP', 'NADPH_NADP', 'NADP_NADPH', 'NADPH ', 'NH4', 
                      'OAA', 'ORN', 'OXOP', 'P2G', 'P3G', 'PEP', 'PRPP', 'PYR', 'R1P', 'R5P', 
                      'RIB', 'RU5P', 'S7P', 'SAH', 'SER', 'SUCARG', 'SUCCOA', 'THF', 'UREA', 
                      'URT', 'X5P', 'XAN', 'XMP', 'O2']:
        km[f'km_{metabolite}'] = 0.2
    
    # Implement the differential equations based on the equadiff.m MATLAB file
    # In the original MATLAB file, this is done using a series of equations
    # Here, we'll use a more generic approach using the stoichiometric matrix
    
    # Get metabolite indices
    metab_indices = {name: i for i, name in enumerate(model['metab'])}
    
    # Define rate laws for each reaction
    # These are simplified examples and would need to be expanded based on the actual model
    
    # Example rate laws (simplified version based on the equadiff.m file)
    # In a complete implementation, you would add all the rate laws from equadiff.m
    
    # Example for hexokinase (HK)
    # VHK = vmax_VHK * mm(x(14)/x(7), km_ATP_ADP, 1) * mm(x(35), km_GLC, 1)
    if 'ATP' in metab_indices and 'ADP' in metab_indices and 'GLC' in metab_indices:
        idx_atp = metab_indices['ATP']
        idx_adp = metab_indices['ADP']
        idx_glc = metab_indices['GLC']
        
        if idx_atp < len(x) and idx_adp < len(x) and idx_glc < len(x):
            VHK = vmax['vmax_VHK'] * mm(x[idx_atp]/x[idx_adp], km['km_ATP_ADP']) * mm(x[idx_glc], km['km_GLC'])
        else:
            VHK = 0
    else:
        VHK = 0
    
    # Apply time-dependent expressions for specific metabolites (from equadiff.m)
    # These are simplified and would need to be expanded based on the actual equations in equadiff.m
    
    # Example: xt3 = 0.0008*2*t - 0.0533 for ADE
    if 'ADE' in metab_indices:
        idx = metab_indices['ADE']
        if idx < len(dxdt):
            dxdt[idx] = 0.0008*2*t - 0.0533
    
    # Example: xt7 = 0.0003*2*t - 0.0357 for ADP
    if 'ADP' in metab_indices:
        idx = metab_indices['ADP']
        if idx < len(dxdt):
            dxdt[idx] = 0.0003*2*t - 0.0357
    
    # In the complete implementation, you would add all the differential equations from equadiff.m
    # This is just a simplified example to show the structure
    
    # For a more complete implementation, you would need to:
    # 1. Define all reaction rates based on the kinetic laws in equadiff.m
    # 2. Apply the stoichiometric matrix to calculate the net change for each metabolite
    # 3. Add the time-dependent expressions for specific metabolites
    
    return dxdt


def load_model():
    """
    Load the metabolic model from the reaction file.
    
    Returns:
    --------
    dict
        Metabolic model
    """
    # Get the path to the reaction file
    reaction_file = os.path.join("RBC", "Rxn_RBC.txt")
    
    # Parse the reaction file
    model = parse(reaction_file)
    
    return model


if __name__ == "__main__":
    # Example usage
    model = load_model()
    if model:
        print(f"Model loaded with {len(model['metab'])} metabolites")
        
        # Example state vector
        x0 = np.ones(len(model['metab']))
        
        # Calculate derivatives at time 0
        dxdt = calculate_derivatives(0, x0, model)
        print(f"Calculated derivatives for {len(dxdt)} metabolites")
