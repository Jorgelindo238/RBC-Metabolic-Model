"""
Python equivalent of the solver.m MATLAB function.
This module handles numerical integration of the system of ODEs.

DEPRECATED: This module is not used by the Streamlit app (which uses SimulationEngine).
It is kept for CLI/legacy reference. The ODE function is now in equadiff_brodbar.py.
"""
import numpy as np
from scipy.integrate import solve_ivp


def solver(x0, time_range, model):
    """
    Python equivalent of the solver.m MATLAB function.
    Performs numerical integration of the system of ODEs.
    
    Parameters:
    -----------
    x0 : numpy.ndarray
        Initial conditions vector
    time_range : tuple or list
        Time range for integration [start_time, end_time]
    model : dict
        The metabolic model from parse.py
        
    Returns:
    --------
    t : numpy.ndarray
        Time points
    x : numpy.ndarray
        Solution array where each row corresponds to a time point
        and each column corresponds to a metabolite
    """
    # Set up integration options
    # Equivalent to MATLAB's odeset('AbsTol', 1e-9, 'RelTol', 1e-6, 'NonNegative', 1:44)
    atol = 1e-9
    rtol = 1e-6
    
    # Calculate the indices for nonnegative variables
    # In the original MATLAB code, it's set to 1:44, but we'll make it more general
    non_negative = list(range(min(44, len(x0))))
    
    # Define the ODE function
    def equadiff(t, x):
        # Import here to avoid circular imports
        from model import calculate_derivatives
        
        # Calculate derivatives
        dxdt = calculate_derivatives(t, x, model)
        
        # Print progress (equivalent to disp(t) in MATLAB)
        if int(t) == t:  # Only print at integer time points to avoid too much output
            print(f"t = {t}")
        
        return dxdt
    
    # Use solve_ivp (equivalent to MATLAB's ode15s)
    # solve_ivp is more modern than odeint and offers similar functionality to MATLAB's solvers
    solution = solve_ivp(
        fun=equadiff,
        t_span=(time_range[0], time_range[1]),
        y0=x0,
        method='LSODA',  # LSODA method is similar to ode15s for stiff problems
        atol=atol,
        rtol=rtol,
        # Ensure non-negative values (equivalent to 'NonNegative' option)
        # SciPy doesn't have a direct equivalent, so we'll clip values in the ODE function
        dense_output=True,  # Generates a continuous solution
        events=None,
        vectorized=False
    )
    
    # Extract solution
    t = solution.t
    x = solution.y.T  # Transpose to match MATLAB's output format
    
    # Ensure non-negative values for specified variables
    # This is a workaround since SciPy doesn't have a direct 'NonNegative' option
    for i in non_negative:
        if i < x.shape[1]:  # Make sure the index is valid
            x[:, i] = np.maximum(0, x[:, i])
    
    return t, x


if __name__ == "__main__":
    # Example usage
    import os
    from parse import parse
    from parse_initial_conditions import parse_initial_conditions
    
    # Load model
    model = parse(os.path.join("RBC", "Rxn_RBC.txt"))
    
    if model:
        # Load initial conditions
        x0, _ = parse_initial_conditions(model, "Initial_conditions_JA_Final.xls")
        
        # Solve over a time range
        if x0 is not None:
            time_range = [0, 10]  # Example time range
            t, x = solver(x0, time_range, model)
            print(f"Solved system over {len(t)} time points")
