"""
Metabolite Mapper Module
========================

Intelligent mapping of column names to RBC metabolites using:
- Exact matching
- Synonym database
- Fuzzy string matching
- Pattern recognition

Author: Jorgelindo da Veiga
Date: 2025-11-17
"""

import json
import os
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import re


class MetaboliteMapper:
    """
    Intelligent metabolite name mapper with synonym database and fuzzy matching.
    """
    
    def __init__(self, synonyms_path: Optional[str] = None):
        """
        Initialize the mapper with synonym database.
        
        Parameters:
        -----------
        synonyms_path : str, optional
            Path to synonyms JSON file. If None, uses default location.
        """
        if synonyms_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            synonyms_path = os.path.join(base_dir, '..', 'data', 'metabolite_synonyms.json')
        
        self.synonyms_path = synonyms_path
        self.synonyms_db = self._load_synonyms()
        self.metabolite_list = list(self.synonyms_db.keys())
        
        # Build reverse lookup (synonym -> canonical)
        self.synonym_to_canonical = {}
        for canonical, data in self.synonyms_db.items():
            for synonym in data.get('synonyms', []):
                self.synonym_to_canonical[synonym.lower()] = canonical
    
    def _load_synonyms(self) -> Dict:
        """Load synonyms database from JSON file."""
        try:
            with open(self.synonyms_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('metabolite_synonyms', {})
        except FileNotFoundError:
            print(f"Warning: Synonyms file not found at {self.synonyms_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Warning: Error decoding synonyms JSON: {e}")
            return {}
    
    def map_column_name(self, column_name: str, threshold: float = 0.7) -> Dict:
        """
        Map a column name to RBC metabolite with confidence score.
        
        Parameters:
        -----------
        column_name : str
            Column name to map
        threshold : float
            Minimum similarity threshold (0-1) for fuzzy matching
            
        Returns:
        --------
        dict
            Mapping result with keys:
            - 'matched': bool
            - 'metabolite': str (canonical name if matched)
            - 'confidence': float (0-1)
            - 'method': str (exact, synonym, fuzzy, none)
            - 'alternatives': list of tuples (metabolite, score)
        """
        result = {
            'matched': False,
            'metabolite': None,
            'confidence': 0.0,
            'method': 'none',
            'alternatives': []
        }
        
        if not column_name:
            return result
        
        # Convert to string (handles numeric column names)
        column_name = str(column_name)
        
        # Clean and normalize column name
        cleaned = self._clean_column_name(column_name)
        
        # 1. Try exact match
        if cleaned.upper() in self.metabolite_list:
            result['matched'] = True
            result['metabolite'] = cleaned.upper()
            result['confidence'] = 1.0
            result['method'] = 'exact'
            return result
        
        # 2. Try synonym lookup
        canonical = self.synonym_to_canonical.get(cleaned.lower())
        if canonical:
            result['matched'] = True
            result['metabolite'] = canonical
            result['confidence'] = 0.95
            result['method'] = 'synonym'
            return result
        
        # 3. Try fuzzy matching
        scores = []
        for metabolite in self.metabolite_list:
            # Compare with canonical name
            score = self._similarity_score(cleaned, metabolite)
            scores.append((metabolite, score))
            
            # Compare with synonyms
            for synonym in self.synonyms_db[metabolite].get('synonyms', []):
                syn_score = self._similarity_score(cleaned, synonym)
                if syn_score > score:
                    score = syn_score
            
            # Compare with full name
            full_name = self.synonyms_db[metabolite].get('full_name', '')
            full_score = self._similarity_score(cleaned, full_name)
            if full_score > score:
                score = full_score
            
            scores.append((metabolite, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Remove duplicates and keep top 5
        seen = set()
        unique_scores = []
        for met, score in scores:
            if met not in seen and score > 0.3:  # Minimum score threshold
                seen.add(met)
                unique_scores.append((met, score))
                if len(unique_scores) >= 5:
                    break
        
        result['alternatives'] = unique_scores
        
        # If best match is above threshold, accept it
        if unique_scores and unique_scores[0][1] >= threshold:
            result['matched'] = True
            result['metabolite'] = unique_scores[0][0]
            result['confidence'] = unique_scores[0][1]
            result['method'] = 'fuzzy'

        return result

    def find_match(self, column_name: str, threshold: float = 0.7) -> Dict:
        """
        Backward-compatible alias for older callers that expect find_match().

        The newer API uses map_column_name(), but some legacy upload/mapping
        paths still call find_match(). Keep both entrypoints aligned so the
        data-upload flow can run without depending on the older Streamlit-era
        contract.
        """
        return self.map_column_name(column_name, threshold)

    def map_dataframe_columns(self, columns: List[str],
                             threshold: float = 0.7,
                             exclude_time: bool = True) -> Dict[str, Dict]:
        """
        Map all columns in a dataframe.
        
        Parameters:
        -----------
        columns : list
            List of column names
        threshold : float
            Minimum similarity threshold for fuzzy matching
        exclude_time : bool
            If True, automatically identify and exclude time columns
            
        Returns:
        --------
        dict
            Dictionary mapping column names to mapping results
        """
        mappings = {}
        
        for col in columns:
            # Check if it's a time column
            if exclude_time and self._is_time_column(col):
                mappings[col] = {
                    'matched': False,
                    'metabolite': None,
                    'confidence': 0.0,
                    'method': 'time_column',
                    'alternatives': []
                }
                continue
            
            mappings[col] = self.map_column_name(col, threshold)
        
        return mappings
    
    def _clean_column_name(self, name: str) -> str:
        """Clean and normalize column name."""
        # Convert to string and remove common prefixes/suffixes
        name = str(name)
        cleaned = name.strip()
        
        # Remove units in brackets/parentheses
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned)
        
        # Remove underscores and replace with spaces for matching
        cleaned = cleaned.replace('_', ' ').strip()
        
        return cleaned
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings.
        Uses SequenceMatcher for fuzzy matching.
        """
        if not str1 or not str2:
            return 0.0
        
        # Convert to strings and normalize for comparison
        s1 = str(str1).lower().strip()
        s2 = str(str2).lower().strip()
        
        # Exact match
        if s1 == s2:
            return 1.0
        
        # Substring match
        if s1 in s2 or s2 in s1:
            return 0.9
        
        # Fuzzy match
        return SequenceMatcher(None, s1, s2).ratio()
    
    def _is_time_column(self, column_name: str) -> bool:
        """Check if column name appears to be a time column."""
        name_lower = str(column_name).lower().strip()
        normalized = re.sub(r'[\s_\-]+', ' ', name_lower)

        exact_time_labels = {
            't',
            'time',
            'time day',
            'time days',
            'time hour',
            'time hours',
            'time min',
            'time minutes',
            'time sec',
            'time seconds',
            'day',
            'days',
            'hour',
            'hours',
            'hr',
            'hrs',
            'min',
            'mins',
            'minute',
            'minutes',
            'sec',
            'secs',
            'second',
            'seconds',
        }

        if normalized in exact_time_labels:
            return True

        return bool(
            re.fullmatch(
                r'(time|day|days|hour|hours|hr|hrs|min|mins|minute|minutes|sec|secs|second|seconds)\s*\d*',
                normalized,
            )
        )
    
    def get_metabolite_info(self, metabolite: str) -> Optional[Dict]:
        """
        Get detailed information about a metabolite.
        
        Parameters:
        -----------
        metabolite : str
            Canonical metabolite name
            
        Returns:
        --------
        dict or None
            Metabolite information including full name, synonyms, description
        """
        return self.synonyms_db.get(metabolite)
    
    def suggest_corrections(self, column_name: str, max_suggestions: int = 5) -> List[Tuple[str, float, str]]:
        """
        Suggest possible metabolite matches for a column name.
        
        Parameters:
        -----------
        column_name : str
            Column name to match
        max_suggestions : int
            Maximum number of suggestions
            
        Returns:
        --------
        list of tuples
            Each tuple contains (metabolite, confidence, full_name)
        """
        result = self.map_column_name(column_name, threshold=0.0)
        suggestions = []
        
        for met, score in result['alternatives'][:max_suggestions]:
            info = self.get_metabolite_info(met)
            full_name = info.get('full_name', met) if info else met
            suggestions.append((met, score, full_name))
        
        return suggestions
    
    def export_mapping_template(self, columns: List[str]) -> str:
        """
        Export a mapping template CSV for manual correction.
        
        Parameters:
        -----------
        columns : list
            List of column names
            
        Returns:
        --------
        str
            CSV string with suggested mappings
        """
        mappings = self.map_dataframe_columns(columns)
        
        lines = ["Column Name,Suggested Metabolite,Confidence,Method"]
        
        for col, mapping in mappings.items():
            if mapping['method'] == 'time_column':
                lines.append(f'"{col}",TIME_COLUMN,1.0,time')
            elif mapping['matched']:
                lines.append(f'"{col}",{mapping["metabolite"]},{mapping["confidence"]:.2f},{mapping["method"]}')
            else:
                alternatives = ", ".join([f"{m}({s:.2f})" for m, s in mapping.get('alternatives', [])[:3]])
                lines.append(f'"{col}",UNMAPPED,0.0,none,{alternatives}')
        
        return "\n".join(lines)
    
    def get_all_metabolites(self) -> List[str]:
        """Get list of all available metabolites."""
        return self.metabolite_list.copy()
    
    def search_metabolites(self, query: str, max_results: int = 10) -> List[Tuple[str, str, float]]:
        """
        Search metabolites by name.
        
        Parameters:
        -----------
        query : str
            Search query
        max_results : int
            Maximum number of results
            
        Returns:
        --------
        list of tuples
            Each tuple contains (canonical_name, full_name, score)
        """
        results = []
        query_lower = query.lower()
        
        for metabolite in self.metabolite_list:
            info = self.synonyms_db[metabolite]
            full_name = info.get('full_name', '')
            
            # Calculate scores
            canonical_score = self._similarity_score(query, metabolite)
            full_name_score = self._similarity_score(query, full_name)
            
            # Check synonyms
            synonym_score = 0
            for syn in info.get('synonyms', []):
                syn_score = self._similarity_score(query, syn)
                synonym_score = max(synonym_score, syn_score)
            
            best_score = max(canonical_score, full_name_score, synonym_score)
            
            if best_score > 0.3:  # Minimum threshold
                results.append((metabolite, full_name, best_score))
        
        # Sort by score
        results.sort(key=lambda x: x[2], reverse=True)
        
        return results[:max_results]


# Convenience function for quick mapping
def quick_map(column_name: str, threshold: float = 0.7) -> Optional[str]:
    """
    Quick mapping of a single column name.
    
    Parameters:
    -----------
    column_name : str
        Column name to map
    threshold : float
        Minimum similarity threshold
        
    Returns:
    --------
    str or None
        Canonical metabolite name if matched, None otherwise
    """
    mapper = MetaboliteMapper()
    result = mapper.map_column_name(column_name, threshold)
    return result['metabolite'] if result['matched'] else None
