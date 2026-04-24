"""
Standardize Bardyn et al. experimental data for RBC metabolic model.

This script extracts and standardizes:
1. Bardyn Control data (columns Q-V) - equivalent to Bordbar conditions
2. Bardyn Supplemented data (columns W-AB) - UA-AA supplementation

Data source: tests/Data_exp_update_01042020.xlsx
Output:
- tests/bardyn_control_standardized.csv
- tests/bardyn_supplemented_standardized.csv
"""

import pandas as pd
import numpy as np
import os

# Path configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, 'Data_exp_update_01042020.xlsx')
OUTPUT_CONTROL = os.path.join(SCRIPT_DIR, 'bardyn_control_standardized.csv')
OUTPUT_SUPPLEMENTED = os.path.join(SCRIPT_DIR, 'bardyn_supplemented_standardized.csv')

# BRODBAR_METABOLITE_MAP - canonical metabolite names from the model
VALID_METABOLITES = {
    'GLC', 'G6P', 'F6P', 'GL6P', 'GO6P', 'RU5P', 'R5P', 'X5P', 'E4P', 'S7P',
    'GA3P', 'F16BP', 'DHCP', 'B13PG', 'P3G', 'B23PG', 'P2G', 'PEP', 'PYR', 'LAC',
    'MAL', 'OAA', 'CIT', 'COA', 'SUCCOA', 'ADE', 'ADO', 'INO', 'HYPX', 'XAN',
    'URT', 'GUA', 'R1P', 'D2RIBP', 'DEOXYINO', 'ATP', 'ADP', 'AMP', 'GTP', 'GDP',
    'GMP', 'PRPP', 'IMP', 'XMP', 'ADESUC', 'CYSTHIO', 'HCYS', 'METTHF', 'MET',
    'THF', 'ADOMET', 'SAH', 'METCYT', 'ARG', 'ARGSUC', 'CITR', 'ASP', 'SER',
    'ALA', 'AKG', 'GLU', 'GLN', 'NH4', 'GLUAA', 'AA', 'OXOP', 'GLY', 'CYS',
    'CYSGLY', 'GLUCYS', 'GSH', 'GSSG', 'ORN', 'UREA', 'ACCOA', 'NAD', 'NADH',
    'NADP', 'NADPH', 'H2O2', 'O2', 'FUM', 'RIB', 'SUCARG', 'CYT',
    'EGLC', 'ENH4', 'ELAC', 'EADO', 'EADE', 'EINO', 'EGLN', 'EGLU', 'ECYS',
    'EMET', 'EASP', 'EUREA', 'EURT', 'EPYR'
}

def standardize_bardyn_data():
    """Extract and standardize Bardyn et al. experimental data."""

    print(f"Reading data from: {INPUT_FILE}")

    # Read the Excel file
    df = pd.read_excel(INPUT_FILE, sheet_name='Feuil1', header=None)

    print(f"Raw data shape: {df.shape}")

    # Extract header row (row 1 contains timepoints)
    # Row 0 has section labels, Row 1 has "Conc / mM" and timepoints

    # --- CONTROL DATA (columns 16-21, Q-V) ---
    # Column 16: "Conc / mM" header, Column 17: timepoint 2, etc.
    control_metabolites = df.iloc[2:, 16].values  # Metabolite names from column Q (index 16)
    control_timepoints = df.iloc[1, 17:22].values  # Timepoints 2, 8, 15, 29, 43
    control_data = df.iloc[2:, 17:22].values  # Data values

    print(f"\nControl timepoints: {control_timepoints}")
    print(f"Control metabolites (first 10): {control_metabolites[:10]}")

    # Create Control DataFrame
    control_df = pd.DataFrame(control_data, columns=control_timepoints)
    control_df.insert(0, 'Metabolite', control_metabolites)

    # --- SUPPLEMENTED DATA (columns 22-27, W-AB) ---
    # Column 22: "Conc / mM" header, Column 23: timepoint 2, etc.
    supp_metabolites = df.iloc[2:, 22].values  # Metabolite names from column W (index 22)
    supp_timepoints = df.iloc[1, 23:28].values  # Timepoints 2, 8, 15, 29, 43
    supp_data = df.iloc[2:, 23:28].values  # Data values

    print(f"\nSupplemented timepoints: {supp_timepoints}")
    print(f"Supplemented metabolites (first 10): {supp_metabolites[:10]}")

    # Create Supplemented DataFrame
    supp_df = pd.DataFrame(supp_data, columns=supp_timepoints)
    supp_df.insert(0, 'Metabolite', supp_metabolites)

    # Clean and standardize both datasets
    control_df = clean_dataframe(control_df, 'Control')
    supp_df = clean_dataframe(supp_df, 'Supplemented')

    # Save to CSV
    control_df.to_csv(OUTPUT_CONTROL, index=False)
    print(f"\nOK Control data saved to: {OUTPUT_CONTROL}")
    print(f"  Shape: {control_df.shape}")

    supp_df.to_csv(OUTPUT_SUPPLEMENTED, index=False)
    print(f"\nOK Supplemented data saved to: {OUTPUT_SUPPLEMENTED}")
    print(f"  Shape: {supp_df.shape}")

    return control_df, supp_df


def clean_dataframe(df, name):
    """Clean and standardize the dataframe."""

    # Remove rows with NaN metabolite names
    df = df.dropna(subset=['Metabolite'])

    # Convert metabolite names to uppercase and strip whitespace
    df['Metabolite'] = df['Metabolite'].astype(str).str.strip().str.upper()

    # Filter to only valid metabolites that exist in the model
    valid_mask = df['Metabolite'].isin(VALID_METABOLITES)
    df_valid = df[valid_mask].copy()

    # Report invalid metabolites
    invalid = df[~valid_mask]['Metabolite'].unique()
    if len(invalid) > 0:
        print(f"\n{name}: Skipped {len(invalid)} metabolites not in model:")
        print(f"  {list(invalid)[:20]}{'...' if len(invalid) > 20 else ''}")

    # Convert numeric columns to float, replacing non-numeric with NaN
    numeric_cols = [col for col in df_valid.columns if col != 'Metabolite']
    for col in numeric_cols:
        df_valid[col] = pd.to_numeric(df_valid[col], errors='coerce')

    # Remove rows that are all NaN (except Metabolite column)
    df_valid = df_valid.dropna(subset=numeric_cols, how='all')

    # Remove duplicate metabolites (keep first occurrence)
    df_valid = df_valid.drop_duplicates(subset=['Metabolite'], keep='first')

    # Sort by metabolite name for consistency
    df_valid = df_valid.sort_values('Metabolite').reset_index(drop=True)

    print(f"\n{name}: {len(df_valid)} valid metabolites retained")

    return df_valid


if __name__ == '__main__':
    control_df, supp_df = standardize_bardyn_data()

    print("\n" + "="*60)
    print("CONTROL DATA PREVIEW:")
    print("="*60)
    print(control_df.head(15).to_string())

    print("\n" + "="*60)
    print("SUPPLEMENTED DATA PREVIEW:")
    print("="*60)
    print(supp_df.head(15).to_string())
