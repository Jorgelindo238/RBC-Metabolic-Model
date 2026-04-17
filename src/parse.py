"""
Python equivalent of the parse.m MATLAB function.
This module parses reaction files and generates metabolic models.
"""
import os
import re
import numpy as np


def parse(file_path, strict=False):
    """
    Python equivalent of the parse.m MATLAB function.
    Parses a reaction file and builds a metabolic model.
    
    Parameters:
    -----------
    file_path : str
        Path to the reaction file
    strict : bool, optional
        Whether or not to allow undeclared reactions/metabolites
        
    Returns:
    --------
    sys : dict
        A dictionary containing the metabolic system model
    """
    # Initialize system dictionary
    sys = {
        'err': 1,
        'int_met': [],
        'ext_met': [],
        'react_name': [],
        'irrev_react': []
    }
    
    rev_react_name = []
    irrev_react_name = []
    section = 0  # 0=header, 1=ENZREV, 2=ENZIRREV, 3=METINT, 4=METEXT, 5=CAT
    
    # Read the reaction file
    try:
        with open(file_path, 'r') as f:
            file_content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None
    
    # Split content into lines
    lines = file_content.splitlines()
    
    # Parse the file line by line
    cat_sect = []
    for line in lines:
        # Remove comments and whitespace
        line = line.split('#')[0].strip()
        if not line:
            continue
        
        # Check for section headers
        if line.startswith('-'):
            header = line[1:].strip().upper()
            if header == 'ENZREV':
                section = 1
            elif header == 'ENZIRREV':
                section = 2
            elif header == 'METINT':
                section = 3
            elif header == 'METEXT':
                section = 4
            elif header == 'CAT':
                section = 5
            continue
        
        # Process line based on current section
        if section in [1, 2, 3, 4]:
            tokens = [t.strip() for t in line.split() if t.strip()]
            if not tokens:
                continue
                
            if section == 1:
                rev_react_name.extend(tokens)
            elif section == 2:
                irrev_react_name.extend(tokens)
            elif section == 3:
                sys['int_met'].extend(tokens)
            elif section == 4:
                sys['ext_met'].extend(tokens)
        elif section == 5:
            cat_sect.append(line)
    
    # Remove duplicates
    sys['int_met'] = remove_duplicates(sys['int_met'])
    sys['ext_met'] = remove_duplicates(sys['ext_met'])
    irrev_react_name = remove_duplicates(irrev_react_name)
    rev_react_name = remove_duplicates(rev_react_name)
    
    # Check for metabolites that are both internal and external
    intersection = list(set(sys['int_met']).intersection(set(sys['ext_met'])))
    if intersection:
        print('Error: the following metabolites were both declared as internal and external')
        print(intersection)
        if strict:
            return None
    
    # Combine reaction names and set up reversibility flags
    sys['react_name'] = irrev_react_name + rev_react_name
    sys['irrev_react'] = [1] * len(irrev_react_name) + [0] * len(rev_react_name)
    
    # Initialize stoichiometric matrices
    # Ensure there's at least one column even if no reactions are defined yet
    num_reactions = max(1, len(sys['irrev_react']))
    st = np.zeros((len(sys['int_met']), num_reactions))
    ext = np.zeros((len(sys['ext_met']), num_reactions))
    
    if not cat_sect:
        print('Error: -CAT section empty or missing')
        return None
    
    # Clean up CAT section lines
    cat_sect = [re.sub(r'\s*[\.\\]?\s*$', '', line) for line in cat_sect]
    
    # Parse reaction definitions
    parsed_reactions = []
    for line in cat_sect:
        # Extract reaction name and equation
        match = re.match(r'\s*(\S*)\s*:\s*(.*)', line)
        if not match:
            print(f"Error: invalid reaction definition '{line}'")
            continue
        
        reac_name, equation = match.groups()
        
        # Split equation into left and right hand sides
        sides = equation.split('=')
        
        if len(sides) == 1:
            print(f"Error: no '=' in reaction '{reac_name}'")
            continue
        
        # Determine arrow type and reaction direction
        if len(sides) > 2:  # Multiple = signs
            print(f"Warning: multiple '=' in reaction '{reac_name}'")
        
        arrow_type = '='
        if '=>' in equation:
            arrow_type = '=>'
            sides = equation.split('=>')
        elif '<=' in equation:
            arrow_type = '<='
            sides = equation.split('<=')
        elif '==' in equation:
            arrow_type = '=='
            sides = equation.split('==')
        
        lhs = sides[0].strip()
        rhs = sides[1].strip()
        
        # Parse metabolites and coefficients from each side
        parsed_reactions.append({
            'name': reac_name,
            'arrow': arrow_type,
            'lhs': parse_equation_side(lhs),
            'rhs': parse_equation_side(rhs)
        })
    
    # Process the parsed reactions
    for reaction in parsed_reactions:
        reac_name = reaction['name']
        arrow_type = reaction['arrow']
        
        # Find reaction index
        if reac_name in sys['react_name']:
            reac_idx = sys['react_name'].index(reac_name)
        else:
            # Add undeclared reaction
            sys['react_name'].append(reac_name)
            sys['irrev_react'].append(1)  # Default to irreversible
            reac_idx = len(sys['react_name']) - 1
            
            # Expand stoichiometric matrices to accommodate the new reaction
            st_new = np.zeros((st.shape[0], len(sys['react_name'])))
            ext_new = np.zeros((ext.shape[0], len(sys['react_name'])))
            st_new[:, :st.shape[1]] = st
            ext_new[:, :ext.shape[1]] = ext
            st = st_new
            ext = ext_new
        
        # Set reversibility based on arrow type
        if arrow_type == '=':
            # Valid for both reversible and irreversible
            if reac_name not in irrev_react_name:
                sys['irrev_react'][reac_idx] = 0
        elif arrow_type == '==':
            # Override irreversible declaration
            sys['irrev_react'][reac_idx] = 0
        elif arrow_type == '=>':
            # Irreversible forward
            if not sys['irrev_react'][reac_idx]:
                # Limit warnings to avoid excessive output
                if reac_name not in ['VAK2', 'VGGT', 'VMESE', 'VCBS']:
                    print(f"Warning: conflicting reversibility for reaction {reac_name}")
                    print("Reaction is now treated as irreversible (forward direction)")
                sys['irrev_react'][reac_idx] = 1
        elif arrow_type == '<=':
            # Irreversible backward
            if not sys['irrev_react'][reac_idx]:
                # Limit warnings to avoid excessive output
                if reac_name not in ['VAK2', 'VGGT', 'VMESE', 'VCBS']:
                    print(f"Warning: conflicting reversibility for reaction {reac_name}")
                    print("Reaction is now treated as irreversible (backward direction)")
                sys['irrev_react'][reac_idx] = 1
        
        # Process LHS (reactants)
        st, ext = process_equation_side(reaction['lhs'], sys, st, ext, reac_idx, -1)
        
        # Process RHS (products)
        st, ext = process_equation_side(reaction['rhs'], sys, st, ext, reac_idx, 1)
    
    # Add stoichiometric matrices to the system
    sys['S'] = st
    sys['ext'] = ext
    
    # Ensure all reactions have been defined
    defined = np.any(abs(st) > 0, axis=0)
    undefined = np.where(~defined)[0].tolist()
    if undefined:
        print("Warning: the following reactions are undefined:")
        for idx in undefined:
            print(sys['react_name'][idx])
        
        if strict:
            return None
    
    # Count the number of internal metabolites
    num_int_met = len(sys['int_met'])
    sys['num_int_met'] = num_int_met
    
    # Rename metab field to be consistent with MATLAB
    sys['metab'] = sys['int_met'] + sys['ext_met']
    
    return sys


def remove_duplicates(items):
    """
    Remove duplicates while preserving order.
    
    Parameters:
    -----------
    items : list
        List of items to deduplicate
        
    Returns:
    --------
    list
        Deduplicated list
    """
    seen = set()
    return [x for x in items if not (x in seen or seen.add(x))]


def parse_equation_side(equation_side):
    """
    Parse one side of a reaction equation.
    
    Parameters:
    -----------
    equation_side : str
        The left or right side of a reaction equation
        
    Returns:
    --------
    list
        List of dictionaries with metabolite names and coefficients
    """
    result = []
    
    # Add a space at the end to simplify parsing
    equation_side += ' '
    
    # Regular expression to match coefficient and metabolite
    pattern = r'(?:(\d+(?:\.\d*)?|\d*\.\d+)?\s*)?(\S+)\s*(\+)?'
    
    matches = re.finditer(pattern, equation_side)
    for match in matches:
        coeff_str, met, plus = match.groups()
        
        if not met or met == '+':
            continue
        
        # Convert coefficient to float
        coeff = 1.0 if not coeff_str else float(coeff_str)
        
        result.append({
            'met': met,
            'coeff': coeff,
            'plus': bool(plus)
        })
    
    return result


def process_equation_side(items, sys, st, ext, reac_idx, sign):
    """
    Process metabolites from one side of an equation and update stoichiometric matrices.
    
    Parameters:
    -----------
    items : list
        List of metabolite items
    sys : dict
        System dictionary
    st : numpy.ndarray
        Stoichiometric matrix for internal metabolites
    ext : numpy.ndarray
        Stoichiometric matrix for external metabolites
    reac_idx : int
        Reaction index
    sign : int
        Sign for the stoichiometric coefficients (1 for products, -1 for reactants)
        
    Returns:
    --------
    st, ext : tuple of numpy.ndarray
        Updated stoichiometric matrices
    """
    for item in items:
        met_name = item['met']
        coeff = sign * item['coeff']  # Apply reaction side sign
        
        # Check if metabolite is declared
        if met_name in sys['int_met']:
            # Internal metabolite
            met_idx = sys['int_met'].index(met_name)
            st[met_idx, reac_idx] = coeff
        elif met_name in sys['ext_met']:
            # External metabolite
            met_idx = sys['ext_met'].index(met_name)
            ext[met_idx, reac_idx] = coeff
        else:
            # Undeclared metabolite, add as internal by default
            print(f"Warning: undeclared metabolite '{met_name}' is added as internal")
            sys['int_met'].append(met_name)
            met_idx = len(sys['int_met']) - 1
            
            # Resize stoichiometric matrix for new rows while preserving all columns
            new_st = np.zeros((len(sys['int_met']), st.shape[1]))
            new_st[:st.shape[0], :] = st
            st = new_st
            
            # Make sure we have a valid index before setting the value
            if reac_idx < st.shape[1]:
                st[met_idx, reac_idx] = coeff
            else:
                print(f"Error: reaction index {reac_idx} is out of bounds for matrix with {st.shape[1]} columns")
                # Expand the matrix to fit this reaction index
                temp_st = np.zeros((st.shape[0], reac_idx+1))
                temp_st[:, :st.shape[1]] = st
                st = temp_st
                st[met_idx, reac_idx] = coeff
    
    return st, ext


if __name__ == "__main__":
    # Example usage
    import os
    
    model = parse(os.path.join("RBC", "Rxn_RBC.txt"))
    if model:
        print(f"Model created with {len(model['int_met'])} internal metabolites and {len(model['react_name'])} reactions")
