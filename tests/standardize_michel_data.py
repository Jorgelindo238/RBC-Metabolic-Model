"""
Standardize Michel experimental dataset for flux analysis.
Converts donnees_michel_nom_commun.xls to the format expected by the flux estimator.
"""

import pandas as pd
from pathlib import Path

# Mapping from Michel dataset names to model metabolite names
MICHEL_TO_MODEL_MAP = {
    # Direct matches (already correct)
    'ATP': 'ATP',
    'ADP': 'ADP',
    'AMP': 'AMP',
    'NAD': 'NAD',
    'NADH': 'NADH',
    'NADP': 'NADP',
    'NADPH': 'NADPH',
    'PYR': 'PYR',
    'G6P': 'G6P',
    'F6P': 'F6P',
    'R5P': 'R5P',
    'URT': 'URT',
    'LAC': 'LAC',
    'GLN': 'GLN',
    'MET': 'MET',
    'ALA': 'ALA',
    'GLY': 'GLY',
    'SER': 'SER',
    'GLU': 'GLU',
    'ARG': 'ARG',
    'CITR': 'CITR',
    'ARGSUC': 'ARGSUC',
    'ORN': 'ORN',
    
    # Mappings requiring conversion
    'AcCoA': 'ACCOA',
    'UDPG': None,  # Not in model, skip
    'X5P&Ru5P': 'X5P',  # Map to X5P (or could split)
    'Gly1P': None,  # Glycerol-1-P, not directly in model
    'GA3P DHAP': 'GA3P',  # Map to GA3P (triose phosphates combined)
    'G1P': None,  # Glucose-1-P, not directly in model
    'Hypo': 'HYPX',  # Hypoxanthine
    'Urea': 'UREA',
    
    # Amino acids with full names - map to model abbreviations
    'Threonine': None,  # THR not in model
    'Phenylalanine': None,  # PHE not in model
    'Isoleucine': None,  # ILE not in model
    'Leucine': None,  # LEU not in model
    'Tyrosine': None,  # TYR not in model
    'Valine': None,  # VAL not in model
    'Proline': None,  # PRO not in model
    'Asparagine': None,  # ASN not in model (ASP is aspartate)
    'Lysine': None,  # LYS not in model
    'Histidine': None,  # HIS not in model
    'Kynutenine': None,  # Kynurenine not in model
    'Tryptophane': None,  # TRP not in model
    'Creatinine': None,  # Not in model
}

def standardize_michel_data(input_path: str, output_path: str = None) -> pd.DataFrame:
    """
    Convert Michel dataset to standardized format for flux analysis.
    
    Args:
        input_path: Path to donnees_michel_nom_commun.xls
        output_path: Path for output CSV (optional)
    
    Returns:
        Standardized DataFrame
    """
    # Read the Excel file
    df = pd.read_excel(input_path, sheet_name=0)
    
    # Rename first column to 'Metabolite'
    df = df.rename(columns={'Time / Days': 'Metabolite'})
    
    # Drop 'Matlab fonction' column if present
    if 'Matlab fonction' in df.columns:
        df = df.drop(columns=['Matlab fonction'])
    
    # Map metabolite names
    mapped_rows = []
    skipped = []
    
    for idx, row in df.iterrows():
        original_name = row['Metabolite']
        
        if original_name in MICHEL_TO_MODEL_MAP:
            model_name = MICHEL_TO_MODEL_MAP[original_name]
            if model_name is not None:
                new_row = row.copy()
                new_row['Metabolite'] = model_name
                mapped_rows.append(new_row)
            else:
                skipped.append(original_name)
        else:
            # Try direct match (uppercase)
            upper_name = str(original_name).upper()
            if upper_name in ['ATP', 'ADP', 'AMP', 'NAD', 'NADH', 'NADP', 'NADPH', 
                             'PYR', 'G6P', 'F6P', 'R5P', 'URT', 'LAC', 'GLN', 
                             'MET', 'ALA', 'GLY', 'SER', 'GLU', 'ARG', 'CITR', 
                             'ARGSUC', 'ORN', 'HYPX', 'UREA', 'ACCOA', 'X5P', 'GA3P']:
                new_row = row.copy()
                new_row['Metabolite'] = upper_name
                mapped_rows.append(new_row)
            else:
                skipped.append(original_name)
    
    # Create standardized DataFrame
    result_df = pd.DataFrame(mapped_rows)
    
    # Ensure Metabolite is first column
    cols = ['Metabolite'] + [c for c in result_df.columns if c != 'Metabolite']
    result_df = result_df[cols]
    
    # Print summary
    print(f"Standardization complete:")
    print(f"  - Mapped: {len(mapped_rows)} metabolites")
    print(f"  - Skipped: {len(skipped)} metabolites (not in model)")
    if skipped:
        print(f"  - Skipped names: {skipped}")
    print(f"\nMapped metabolites: {result_df['Metabolite'].tolist()}")
    
    # Save if output path provided
    if output_path:
        result_df.to_csv(output_path, index=False)
        print(f"\nSaved to: {output_path}")
    
    return result_df


if __name__ == "__main__":
    # Paths
    script_dir = Path(__file__).parent
    input_file = script_dir / "donnees_michel_nom_commun.xls"
    output_file = script_dir / "donnees_michel_standardized.csv"
    
    # Run standardization
    df = standardize_michel_data(str(input_file), str(output_file))
    
    # Display result
    print("\n" + "="*60)
    print("Standardized Data Preview:")
    print("="*60)
    print(df.to_string(index=False))
