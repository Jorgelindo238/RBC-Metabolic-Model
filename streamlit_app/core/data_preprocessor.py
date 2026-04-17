"""
Data Preprocessing Module
=========================

Preprocessing utilities for uploaded metabolite data.

Features:
- Auto-detect transposed format
- Transpose data if needed
- Clean column names
- Handle different time units

Author: Jorgelindo da Veiga
Date: 2025-11-17
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


class DataPreprocessor:
    """
    Preprocessor for metabolite concentration data.
    Handles various data formats and orientations.
    """
    
    def __init__(self):
        self.time_keywords = [
            'time', 'hours', 'days', 'minutes', 'seconds',
            't', 'hr', 'day', 'min', 'sec', 'hour', 'h', 'd'
        ]
    
    def detect_format(self, df: pd.DataFrame) -> dict:
        """
        Detect if data is in standard or transposed format.
        
        Standard format:
        Time | GLC | LAC | ATP
        0.0  | 5.0 | 2.0 | 2.5
        
        Transposed format:
        Conc/mM | 2   | 8   | 15
        GLC     | 5.0 | 4.5 | 4.0
        
        Returns:
        --------
        dict with keys:
            - 'format': 'standard' or 'transposed'
            - 'needs_transpose': bool
            - 'first_column_type': 'time' or 'metabolite'
            - 'confidence': float
        """
        result = {
            'format': 'standard',
            'needs_transpose': False,
            'first_column_type': 'unknown',
            'confidence': 0.0
        }
        
        if df.empty:
            return result
        
        # Get first column name and values
        first_col_name = str(df.columns[0])
        first_col_values = df.iloc[:, 0]
        
        # Check if first column is time-like
        is_time_column = self._is_time_like(first_col_name)
        
        # Check if first row (header) contains numeric values (time points)
        numeric_headers = 0
        for col in df.columns[1:]:  # Skip first column
            try:
                float(col)
                numeric_headers += 1
            except (ValueError, TypeError):
                pass
        
        header_numeric_ratio = numeric_headers / max(len(df.columns) - 1, 1)
        
        # Check if first column values are strings (metabolite names)
        string_values = sum(isinstance(val, str) for val in first_col_values)
        string_ratio = string_values / max(len(first_col_values), 1)
        
        # Decision logic
        if header_numeric_ratio > 0.5 and string_ratio > 0.5:
            # Headers are numbers, first column is strings → transposed
            result['format'] = 'transposed'
            result['needs_transpose'] = True
            result['first_column_type'] = 'metabolite'
            result['confidence'] = min(header_numeric_ratio + string_ratio, 1.0) / 2
        elif is_time_column:
            # First column is time → standard
            result['format'] = 'standard'
            result['needs_transpose'] = False
            result['first_column_type'] = 'time'
            result['confidence'] = 0.9
        else:
            # Default to standard format with lower confidence
            result['format'] = 'standard'
            result['needs_transpose'] = False
            result['first_column_type'] = 'time'
            result['confidence'] = 0.5
        
        return result
    
    def transpose_data(self, df: pd.DataFrame, 
                       metabolite_col: Optional[str] = None) -> pd.DataFrame:
        """
        Transpose data from wide to long format.
        
        Input (transposed):
        Conc/mM | 2   | 8   | 15
        GLC     | 5.0 | 4.5 | 4.0
        LAC     | 2.0 | 2.5 | 3.0
        
        Output (standard):
        Time | GLC | LAC
        2    | 5.0 | 2.0
        8    | 4.5 | 2.5
        15   | 4.0 | 3.0
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe
        metabolite_col : str, optional
            Name of column containing metabolite names (default: first column)
            
        Returns:
        --------
        pd.DataFrame
            Transposed dataframe
        """
        df_copy = df.copy()
        
        # Identify metabolite column (first column if not specified)
        if metabolite_col is None:
            metabolite_col = df_copy.columns[0]
        
        # Set metabolite names as index
        df_copy = df_copy.set_index(metabolite_col)
        
        # Transpose
        df_transposed = df_copy.T
        
        # Reset index to make time a column
        df_transposed = df_transposed.reset_index()
        df_transposed = df_transposed.rename(columns={'index': 'Time'})
        
        # Try to convert time to numeric
        try:
            df_transposed['Time'] = pd.to_numeric(df_transposed['Time'])
        except (ValueError, TypeError):
            pass
        
        return df_transposed
    
    def auto_process(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
        """
        Automatically detect format and process data.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe
            
        Returns:
        --------
        tuple
            (processed_df, metadata_dict)
        """
        # Detect format
        format_info = self.detect_format(df)
        
        # Process based on format
        if format_info['needs_transpose']:
            processed_df = self.transpose_data(df)
            metadata = {
                'original_format': 'transposed',
                'action_taken': 'transposed to standard format',
                'confidence': format_info['confidence']
            }
        else:
            processed_df = df.copy()
            metadata = {
                'original_format': 'standard',
                'action_taken': 'no transformation needed',
                'confidence': format_info['confidence']
            }
        
        return processed_df, metadata
    
    def _is_time_like(self, column_name: str) -> bool:
        """Check if column name suggests it's a time column."""
        name_lower = str(column_name).lower()
        return any(keyword in name_lower for keyword in self.time_keywords)
    
    def clean_metabolite_names(self, df: pd.DataFrame, 
                               exclude_time_col: bool = True) -> pd.DataFrame:
        """
        Clean metabolite names (remove spaces, special chars, etc.).
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe
        exclude_time_col : bool
            If True, skip the first time-like column
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with cleaned column names
        """
        df_clean = df.copy()
        
        new_columns = []
        for i, col in enumerate(df_clean.columns):
            if i == 0 and exclude_time_col and self._is_time_like(col):
                # Keep time column as is
                new_columns.append(col)
            else:
                # Clean metabolite name
                clean_name = str(col).strip()
                clean_name = clean_name.replace(' ', '_')
                clean_name = clean_name.replace('-', '_')
                new_columns.append(clean_name)
        
        df_clean.columns = new_columns
        return df_clean
    
    def convert_time_units(self, df: pd.DataFrame, 
                          time_col: str,
                          from_unit: str = 'days',
                          to_unit: str = 'days') -> pd.DataFrame:
        """
        Convert time units.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Input dataframe
        time_col : str
            Name of time column
        from_unit : str
            Original unit ('hours', 'days', 'minutes', 'seconds')
        to_unit : str
            Target unit
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with converted time
        """
        df_conv = df.copy()
        
        # Conversion factors to days
        to_days = {
            'seconds': 1/86400,
            'minutes': 1/1440,
            'hours': 1/24,
            'days': 1
        }
        
        if from_unit == to_unit:
            return df_conv
        
        # Convert to days first, then to target
        factor = to_days[from_unit] / to_days[to_unit]
        df_conv[time_col] = df_conv[time_col] * factor
        
        return df_conv
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, list]:
        """
        Validate that data is suitable for simulation.
        
        Returns:
        --------
        tuple
            (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for empty dataframe
        if df.empty:
            issues.append("DataFrame is empty")
            return False, issues
        
        # Check for missing values
        null_counts = df.isnull().sum()
        null_cols = null_counts[null_counts > 0]
        if len(null_cols) > 0:
            issues.append(f"Missing values in columns: {', '.join(null_cols.index.tolist())}")
        
        # Check for non-numeric values (except first column if it's time)
        for col in df.columns[1:]:
            if not pd.api.types.is_numeric_dtype(df[col]):
                issues.append(f"Column '{col}' contains non-numeric values")
        
        # Check for negative concentrations
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if (df[col] < 0).any():
                issues.append(f"Column '{col}' contains negative values")
        
        is_valid = len(issues) == 0
        return is_valid, issues


def quick_preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Quick preprocessing function for convenience.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Input dataframe
        
    Returns:
    --------
    pd.DataFrame
        Processed dataframe
    """
    preprocessor = DataPreprocessor()
    processed_df, _ = preprocessor.auto_process(df)
    return processed_df
