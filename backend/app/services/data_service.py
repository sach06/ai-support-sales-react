"""
Data ingestion service for loading and merging Excel/CSV files
"""
import hashlib
import time
import pandas as pd
import duckdb
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.services.mapping_service import mapping_service
from app.services.enrichment_service import enrichment_service

# ---------------------------------------------------------------------------
# Module-level in-memory query cache  (survives Streamlit reruns in same process)
# Cleared whenever create_unified_view() runs so stale results are never served.
# ---------------------------------------------------------------------------
_QUERY_CACHE: Dict[str, object] = {}
_QUERY_CACHE_TTL: Dict[str, float] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_get(key: str):
    """Return cached value or None if missing / expired"""
    if key not in _QUERY_CACHE:
        return None
    if time.monotonic() - _QUERY_CACHE_TTL.get(key, 0) > _CACHE_TTL_SECONDS:
        del _QUERY_CACHE[key]
        return None
    return _QUERY_CACHE[key]


def _cache_set(key: str, value):
    _QUERY_CACHE[key] = value
    _QUERY_CACHE_TTL[key] = time.monotonic()


def _cache_clear():
    """Invalidate all cached query results"""
    _QUERY_CACHE.clear()
    _QUERY_CACHE_TTL.clear()


class DataIngestionService:
    """Service for loading and managing customer data from Excel files"""
    
    def __init__(self):
        self.db_path = settings.DB_PATH
        self.data_dir = settings.DATA_DIR
        self.conn = None
        self.logs = []
        self._schema_migrated = False  # track one-time schema migration
        
    def add_log(self, message: str):
        """Add a log message for the UI"""
        self.logs.append(message)
        print(message)
        
    def get_conn(self):
        """Helper to get connection, initializing if needed"""
        if not self.conn:
            self.initialize_database()
        return self.conn

    def get_logs(self) -> List[str]:
        """Retrieve logs for the UI"""
        return self.logs
        
    def clear_logs(self):
        """Clear the logs"""
        self.logs = []
        
    def initialize_database(self):
        """Initialize DuckDB database"""
        try:
            # Try to connect in read-write mode first
            self.conn = duckdb.connect(str(self.db_path))
            self.add_log(f"Database initialized at {self.db_path}")
        except Exception as e:
            if "used by another process" in str(e).lower() or "IO Error" in str(e):
                self.add_log("Database is locked by another process. Attempting read-only connection...")
                try:
                    self.conn = duckdb.connect(str(self.db_path), read_only=True)
                    self.add_log("Connected in READ-ONLY mode. (Data loading will be disabled)")
                except Exception as inner_e:
                    self.add_log(f"Failed to connect: {inner_e}")
                    raise inner_e
            else:
                self.add_log(f"Database error: {e}")
                raise e
    
    def list_available_files(self) -> List[str]:
        """List all supported files in the data directory"""
        if not self.data_dir.exists():
            self.add_log(f"Data directory created: {self.data_dir}")
            self.data_dir.mkdir(parents=True, exist_ok=True)
            return []
            
        extensions = ['*.xlsx', '*.csv', '*.xls', '*.json']
        files = []
        for ext in extensions:
            files.extend([f.name for f in self.data_dir.glob(ext) if not f.name.startswith('~$')])
            
        return sorted(list(set(files)))
        
    def get_excel_sheets(self, filename: str) -> List[str]:
        """Get list of sheet names from an Excel file"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if filepath.suffix == '.csv':
            return ['CSV File']
        
        excel_file = pd.ExcelFile(filepath)
        return excel_file.sheet_names
    
    def load_excel_file(self, filename: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """Load an Excel file from the data directory with cleaning"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if filepath.suffix == '.csv':
            df = pd.read_csv(filepath)
        else:
            if sheet_name is None:
                excel_file = pd.ExcelFile(filepath)
                sheet_name = excel_file.sheet_names[0]
            df = pd.read_excel(filepath, sheet_name=sheet_name)
        
        # Data Cleaning: Remove unnamed columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
        
        # Remove columns with no name (None or empty string)
        df = df.loc[:, [c for c in df.columns if c and str(c).strip()]]
        
        self.add_log(f"Loaded {filename} (sheet: {sheet_name}): {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def load_crm_data(self, filename: str = "crm_export.xlsx") -> pd.DataFrame:
        """Load CRM data with column normalization"""
        df = self.load_excel_file(filename)
        
        # Standardize CRM columns
        column_mapping = {
            'Company': 'name',
            'Company Name': 'name',
            'Customer': 'name',
            'Customer Name': 'name',
            'Account Name': 'name',
            'Industry': 'industry',
            'Region': 'region',
            'Country': 'country',
            'Country (Territory)': 'country',
            'Rating': 'rating',
            'CRM Rating': 'rating',
            'CEO': 'company_ceo',
            'Chief Executive Officer': 'company_ceo',
            'FTE': 'fte_count',
            'Number of Employees': 'fte_count',
            'Employees': 'fte_count'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        # Ensure 'name' exists
        if 'name' not in df.columns:
            # Try to find a column that looks like a name if still missing
            potential_name_cols = [c for c in df.columns if 'name' in str(c).lower() or 'company' in str(c).lower()]
            if potential_name_cols:
                df.rename(columns={potential_name_cols[0]: 'name'}, inplace=True)
            else:
                # Fallback to the first column if everything fails
                df.rename(columns={df.columns[0]: 'name'}, inplace=True)

        # Ensure required columns for Dashboard and Smart Joint exist
        required_cols = [
            'industry', 'country', 'region', 'rating', 'status', 
            'fte', 'revenue', 'latitude', 'longitude',
            'company_ceo', 'fte_count'
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        
        # Fix DuckDB type mismatch: Convert all columns to consistent types
        for col in df.columns:
            if df[col].dtype == 'object':
                # Convert object columns to string, but preserve None for actual NaN values
                df[col] = df[col].fillna('__NULL__')
                df[col] = df[col].astype(str)
                df[col] = df[col].replace('__NULL__', None)
                df[col] = df[col].replace('nan', None)
                df[col] = df[col].replace('None', None)
            elif pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype('float64')
        
        # Store in DuckDB
        if self.conn:
            # Filter for Europe and Australia/Oceania specifically
            europe_vars = [r.lower() for r in self.REGION_MAPPING["Europe"]]
            aus_vars = ["australia", "oceania", "nz", "new zealand"]
            
            target_vars = europe_vars + aus_vars
            
            if 'region' in df.columns or 'country' in df.columns:
                target_regions = ["europe", "oceania"]
                
                def matches_target(row):
                    reg = str(row.get('region', '') or '').lower()
                    cnt = str(row.get('country', '') or '').lower()
                    
                    # 1. Direct match on region name
                    if any(v in reg for v in target_vars) or reg in target_vars:
                        return True
                    
                    # 2. Direct match on country name (e.g. "Australia")
                    if any(v in cnt for v in target_vars) or cnt in target_vars:
                        # Try to fill region if empty
                        return True
                        
                    # 3. Check country-to-region map
                    mapped_reg = self.COUNTRY_TO_REGION_MAP.get(cnt, "").lower()
                    if mapped_reg in target_regions:
                        return True
                        
                    return False
                
                # Apply filter
                df = df[df.apply(matches_target, axis=1)].copy()
                
                # IMPORTANT: Fill missing regions
                def fill_region(row):
                    reg = str(row.get('region', '') or '').strip()
                    if not reg or reg.lower() == 'nan':
                        cnt = str(row.get('country', '') or '').lower()
                        return self.COUNTRY_TO_REGION_MAP.get(cnt, reg)
                    return reg
                
                if 'region' in df.columns:
                    df['region'] = df.apply(fill_region, axis=1)
                else:
                    df['region'] = df['country'].str.lower().map(self.COUNTRY_TO_REGION_MAP)
            
            self.conn.execute("DROP TABLE IF EXISTS crm_data")
            self.conn.execute("CREATE TABLE crm_data AS SELECT * FROM df")
            self.add_log(f"CRM data loaded (filtered for Europe): {len(df)} records")
        
        return df
    
    def clean_company_name(self, name: any) -> str:
        """Clean company name by removing legal suffixes and extra whitespace"""
        if pd.isna(name) or name is None:
            return ""
        
        name = str(name).strip()
        # Remove common legal suffixes (order matters - longer first)
        suffixes = [
            ' GMBH & CO. KG', ' GMBH & CO KG', ' GMBH & CO.', ' GMBH & CO',
            ' GMBH', ' S.P.A.', ' S.P.A', ' SPA', ' LTD.', ' LTD', ' CORP.', ' CORP',
            ' INC.', ' INC', ' AG', ' S.A.', ' SA', ' SAS', ' PTY LTD', ' PTY. LTD.',
            ' CO.', ' CO', ' LIMITED', ' CORPORATION', ' GROUP'
        ]
        
        # Iteratively remove suffixes from the end (case-insensitive)
        clean_name = name
        upper_name = clean_name.upper()
        
        for suffix in suffixes:
            if upper_name.endswith(suffix):
                clean_name = clean_name[:len(clean_name)-len(suffix)].strip()
                upper_name = clean_name.upper()
        
        # Remove any trailing commas or dots after cleaning
        clean_name = clean_name.rstrip(',. ')
        
        return clean_name

    def fuzzy_column_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map problematic column names to standard internal names"""
        mapping = {
            'company': ['company', 'company name', 'customer', 'customer name', 'parent company', 'owner'],
            'name': ['name', 'plant name', 'company/plant'],
            'country': ['country', 'country (territory)', 'nation'],
            'latitude': ['lat', 'latitude', 'north'],
            'longitude': ['lon', 'longitude', 'long', 'east'],
            'start_year': ['start year', 'year of startup', 'year of start up', 'startup year', 'year', 'commissions'],
            'capacity': ['capacity', 'nominal capacity', 't/y', 'tons per year']
        }
        
        cols = {str(c).lower(): c for c in df.columns}
        new_cols = {}
        
        for standard, variations in mapping.items():
            for var in variations:
                if var in cols:
                    new_cols[cols[var]] = standard
                    break
        
        if new_cols:
            df.rename(columns=new_cols, inplace=True)
            
        # Clean company names if 'name' or 'company' or 'company_internal' exists
        for col in ['name', 'company', 'company_internal']:
            if col in df.columns:
                df[col] = df[col].apply(self.clean_company_name)
                
        return df

    FIXED_EQUIPMENT_LIST = [
        "AC-Electric Arc Furnace", "Batch Annealing Plant", "Billet-/heavy Bar Mill", "Blast Furnace",
        "Blooming And Slabbing Mill", "BOF Shop", "Coking Plant", "Continuous Annealing Line",
        "Continuous Billet Caster", "Continuous Bloom Caster", "Continuous Slab Caster",
        "DC-Electric Arc Furnace", "Direct or Smelting Reduction Plant", "Electrolytic Metal Coating Line",
        "Heavy Section Mill", "Hot Dip Metal Coating Line", "Hot Strip Mill", "Induction Melt Furnace",
        "Ladle Furnace", "Light Section And Bar Mill", "Medium Section Mill", "Open Hearth Meltshop",
        "Organic Coating Line", "Pelletizing Plant", "Pickling Line", "Plate Mill",
        "Reversing Cold Rolling Mill", "Sintering Plant", "Special Converter Processes",
        "Steel Remelting Furnace", "Tandem Mill", "Temper- / Skin Pass Mill (CR)",
        "Temper- / Skin Pass Mill (HR)", "Thin-Slab Caster", "Thin-Slab Rolling Mill",
        "Vacuum Degassing Plant", "Wire Rod Mill", "Wire Rod Mill In Bar Mill"
    ]

    # Mapping from user-facing labels to actual sheet names
    EQUIPMENT_MAP = {
        "Direct or Smelting Reduction Plant": "Direct or Smelting Reduction P",
        "Billet-/heavy Bar Mill": "Billet-heavy Bar Mill",
        "Electrolytic Metal Coating Line": "Electrolytic Metal Coating Lin",
        "Temper- / Skin Pass Mill (CR)": "Temper-  Skin Pass Mill (CR)",
        "Temper- / Skin Pass Mill (HR)": "Temper-  Skin Pass Mill (HR)"
    }

    REGION_OPTIONS = ["Americas", "APAC & MEA", "China", "Commonwealth", "Europe", "Not assigned"]

    REGION_MAPPING = {
        "Europe": ["Europe", "EU", "Western Europe", "Eastern Europe", "Southeastern Europe", "Northern Europe", "Southern Europe"],
        "Americas": ["Americas", "North America", "South America", "Central America", "USA", "Canada", "Brazil", "Mexico"],
        "APAC & MEA": ["APAC", "MEA", "Middle East", "Africa", "South Asia", "Southeast Asia", "Oceania", "Australia", "India", "Asean"],
        "China": ["China", "Greater China"],
        "Commonwealth": ["CIS", "Russia", "Kazakhstan", "Ukraine", "Uzbekistan", "Belarus"]
    }

    def load_bcg_installed_base(self, filename: str = "bcg_data.xlsx") -> pd.DataFrame:
        """
        Load BCG installed base data from all sheets
        """
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        excel_file = pd.ExcelFile(filepath)
        all_equipment = []
        
        self.add_log(f"Loading BCG Installed Base from {len(excel_file.sheet_names)} sheets...")
        
        for sheet_name in excel_file.sheet_names:
            if sheet_name == "Master Sorting List":
                continue
            try:
                df = self.load_excel_file(filename, sheet_name=sheet_name)
                df = self.fuzzy_column_mapping(df)
                df['equipment_type'] = sheet_name
                
                # Internal mapping for logic, but keep original columns for UI
                internal_mapping = {
                    'name': 'company_internal',
                    'country': 'country_internal',
                    'latitude': 'latitude_internal',
                    'longitude': 'longitude_internal',
                    'start_year': 'start_year_internal',
                    'capacity': 'capacity_internal'
                }
                
                for old_col, new_col in internal_mapping.items():
                    if old_col in df.columns:
                        df[new_col] = df[old_col]
                
                # Ensure 'company' exists for mapping
                if 'company_internal' not in df.columns:
                    potential_comp_cols = [c for c in df.columns if 'company' in str(c).lower() or 'customer' in str(c).lower()]
                    if potential_comp_cols:
                        df['company_internal'] = df[potential_comp_cols[0]]
                
                # Filter for Europe and Australia/Oceania specifically
                europe_vars = [r.lower() for r in self.REGION_MAPPING["Europe"]]
                aus_vars = ["australia", "oceania", "nz", "new zealand"]
                
                target_vars = europe_vars + aus_vars
                
                if 'region' in df.columns or 'country' in df.columns:
                    target_regions = ["europe", "oceania"]
                    def matches_target(row):
                        reg = str(row.get('region', '') or '').lower()
                        cnt = str(row.get('country', '') or '').lower()
                        # 1. Direct match on region name
                        if any(v in reg for v in target_vars) or reg in target_vars:
                            return True
                        # 2. Direct match on country name
                        if any(v in cnt for v in target_vars) or cnt in target_vars:
                            return True
                        # 3. Check mapping
                        mapped_reg = self.COUNTRY_TO_REGION_MAP.get(cnt, "").lower()
                        if mapped_reg in target_regions:
                            return True
                        return False
                    
                    df = df[df.apply(matches_target, axis=1)].copy()
                    
                    # Fill missing regions to ensure filtering works correctly in unified view
                    def fill_region_bcg(row):
                        reg = str(row.get('region', '') or '').strip()
                        if not reg or reg.lower() == 'nan':
                            cnt = str(row.get('country', '') or '').lower()
                            return self.COUNTRY_TO_REGION_MAP.get(cnt, reg)
                        return reg
                    
                    df['region'] = df.apply(fill_region_bcg, axis=1)
                
                if not df.empty:
                    all_equipment.append(df)
                    self.add_log(f"  Processed {sheet_name} (Europe): {len(df)} records")
                else:
                    self.add_log(f"  Skipped {sheet_name}: No Europe records found")
                
            except Exception as e:
                self.add_log(f"  Error loading sheet '{sheet_name}': {e}")
                continue
        
        if not all_equipment:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_equipment, ignore_index=True)
        
        # Numeric conversion for internal logic columns
        for col in ['latitude_internal', 'longitude_internal', 'start_year_internal', 'capacity_internal']:
            if col in combined_df.columns:
                combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce')
        
        # Fix DuckDB type mismatch: Convert all columns to consistent types
        # This prevents "Type DOUBLE does not match with INTEGER" errors
        for col in combined_df.columns:
            if combined_df[col].dtype == 'object':
                # Convert object columns to string, but preserve None for actual NaN values
                # First replace NaN with a placeholder, convert to string, then replace back
                combined_df[col] = combined_df[col].fillna('__NULL__')
                combined_df[col] = combined_df[col].astype(str)
                combined_df[col] = combined_df[col].replace('__NULL__', None)
                combined_df[col] = combined_df[col].replace('nan', None)
                combined_df[col] = combined_df[col].replace('None', None)
            elif pd.api.types.is_numeric_dtype(combined_df[col]):
                # Convert all numeric types to float64 for consistency
                combined_df[col] = combined_df[col].astype('float64')
        
        if self.conn:
            self.conn.execute("DROP TABLE IF EXISTS bcg_installed_base")
            self.conn.execute("CREATE TABLE bcg_installed_base AS SELECT * FROM combined_df")
            self.add_log(f"BCG Installed Base loaded: {len(combined_df)} total records")
        
        return combined_df

    REGION_MAPPING = {
        "Americas": ["North America", "South America", "Central America", "Latin America", "Americas"],
        "APAC & MEA": ["APAC", "Asia", "Middle East", "Africa", "Oceania", "Australia", "India", "Southeast Asia", "MEA"],
        "China": ["China"],
        "Commonwealth": ["CIS", "Commonwealth", "Russia"],
        "Europe": ["Europe", "EU", "Western Europe", "Eastern Europe", "Central Europe", "Nordics"]
    }

    COUNTRY_TO_REGION_MAP = {
        "germany": "Europe", "france": "Europe", "italy": "Europe", "spain": "Europe", "united kingdom": "Europe",
        "uk": "Europe", "netherlands": "Europe", "belgium": "Europe", "switzerland": "Europe", "austria": "Europe",
        "sweden": "Europe", "norway": "Europe", "denmark": "Europe", "finland": "Europe", "poland": "Europe",
        "czech republic": "Europe", "czechia": "Europe", "hungary": "Europe", "romania": "Europe", "bulgaria": "Europe",
        "greece": "Europe", "portugal": "Europe", "ireland": "Europe", "slovakia": "Europe", "slovenia": "Europe",
        "croatia": "Europe", "estonia": "Europe", "latvia": "Europe", "lithuania": "Europe", "luxembourg": "Europe",
        "australia": "Oceania", "new zealand": "Oceania", "nz": "Oceania", "papua new guinea": "Oceania", "fiji": "Oceania"
    }

    def get_detailed_plant_data(self, equipment_type: str = "All", country: str = "All", region: str = "All", company_name: str = "All") -> pd.DataFrame:
        """Get granular plant data joined with CRM information"""
        if not self.conn:
            self.initialize_database()
        
        # Ensure company_mappings table exists (once per session, not per call)
        if not self._schema_migrated:
            self._ensure_schema()
            self._schema_migrated = True
        
        # Check if crm_data table exists
        has_crm = False
        try:
            tables = self.conn.execute("SHOW TABLES").df()['name'].tolist()
            has_crm = 'crm_data' in tables
        except:
            pass

        if has_crm:
            query = """
                SELECT 
                    b.*,
                    c.company_ceo as CEO,
                    c.fte_count as "Number of Full time employees",
                    m.crm_name,
                    COALESCE(CAST(m.crm_name AS VARCHAR), CAST(b.company_internal AS VARCHAR)) as name
                FROM bcg_installed_base b
                LEFT JOIN company_mappings m ON b.company_internal = m.bcg_name
                LEFT JOIN (
                    SELECT name, company_ceo, fte_count FROM crm_data
                ) c ON COALESCE(CAST(m.crm_name AS VARCHAR), CAST(b.company_internal AS VARCHAR)) = c.name
                WHERE 1=1
            """
        else:
            query = """
                SELECT 
                    b.*,
                    CAST(NULL AS VARCHAR) as CEO,
                    CAST(NULL AS DOUBLE) as "Number of Full time employees",
                    CAST(NULL AS VARCHAR) as crm_name
                FROM bcg_installed_base b
                LEFT JOIN company_mappings m ON b.company_internal = m.bcg_name
                WHERE 1=1
            """
        params = []
        if equipment_type != "All":
            # Map user label to actual sheet name if needed
            sheet_name = self.EQUIPMENT_MAP.get(equipment_type, equipment_type)
            query += " AND b.equipment_type = ?"
            params.append(sheet_name)
        if country != "All":
            query += " AND b.country_internal = ?"
            params.append(country)
        if company_name != "All":
            query += " AND COALESCE(m.crm_name, b.company_internal) = ?"
            params.append(company_name)
            
        try:
            df = self.conn.execute(query, params).df()
            self.add_log(f"Query returned {len(df)} initial records.")
            
            # Apply Region filter in Pandas to handle mapping logic
            if not df.empty and region != "All":
                if region in self.REGION_MAPPING:
                    allowed_regions = [r.lower() for r in self.REGION_MAPPING[region]]
                    if 'Region' in df.columns:
                        # Case-insensitive match against allowed variations
                        mask = df['Region'].fillna("").apply(
                            lambda x: any(r in str(x).lower() for r in allowed_regions) or str(x).lower() == region.lower()
                        )
                        df = df[mask]
                        self.add_log(f"Filtered to {len(df)} records for region: {region}")
                elif region == "Not assigned":
                     if 'Region' in df.columns:
                        df = df[df['Region'].isna() | (df['Region'].fillna("").astype(str).str.strip() == "")]
                        self.add_log(f"Filtered to {len(df)} records for unassigned region")
            
            return df
        except Exception as e:
            self.add_log(f"Error fetching plant data: {e}")
            import traceback
            self.add_log(traceback.format_exc())
            return pd.DataFrame()

    def get_all_countries(self):
        """Get all country names from BCG data"""
        cached = _cache_get('all_countries')
        if cached is not None:
            return cached
        conn = self.get_conn()
        if not conn:
            return []
        try:
            result = conn.execute(
                "SELECT DISTINCT country_internal FROM bcg_installed_base WHERE country_internal IS NOT NULL ORDER BY 1"
            ).df()['country_internal'].tolist()
            _cache_set('all_countries', result)
            return result
        except:
            return []

    def load_bcg_data(self, filename: str = "bcg_data.xlsx") -> pd.DataFrame:
        """Load BCG market data"""
        df = self.load_excel_file(filename)
        
        if self.conn:
            self.conn.execute("DROP TABLE IF EXISTS bcg_data")
            self.conn.execute("CREATE TABLE bcg_data AS SELECT * FROM df")
            self.add_log("BCG market data loaded")
        
        return df
    
    def load_installed_base(self, filename: str = "installed_base.xlsx") -> pd.DataFrame:
        """Load installed base equipment data"""
        df = self.load_excel_file(filename)
        
        if self.conn:
            self.conn.execute("DROP TABLE IF EXISTS installed_base")
            self.conn.execute("CREATE TABLE installed_base AS SELECT * FROM df")
            self.add_log("Installed base data loaded")
        
        return df
    
    def _ensure_schema(self):
        """Ensure company_mappings table + match_score column exist (run once per session)"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS company_mappings (
                crm_name VARCHAR,
                bcg_name VARCHAR,
                match_score DOUBLE,
                UNIQUE(crm_name, bcg_name)
            )
        """)
        try:
            cols = self.conn.execute("PRAGMA table_info('company_mappings')").df()['name'].tolist()
            if 'match_score' not in cols:
                self.conn.execute("ALTER TABLE company_mappings ADD COLUMN match_score DOUBLE")
        except:
            pass

    def _compute_data_fingerprint(self) -> str:
        """Compute a lightweight fingerprint of source table row counts + timestamps.
        If this value is unchanged, create_unified_view can be skipped."""
        parts = []
        for tbl in ('crm_data', 'bcg_installed_base'):
            try:
                cnt = self.conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                parts.append(f"{tbl}:{cnt}")
            except:
                parts.append(f"{tbl}:0")
        # Also include modification times of source files
        for f in sorted(self.data_dir.glob('*.xlsx')):
            parts.append(f"{f.name}:{int(f.stat().st_mtime)}")
        return hashlib.md5('|'.join(parts).encode()).hexdigest()

    def _get_stored_fingerprint(self) -> str:
        """Read fingerprint stored in DB; returns '' if not set"""
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS _meta (
                    key VARCHAR PRIMARY KEY,
                    value VARCHAR
                )
            """)
            row = self.conn.execute(
                "SELECT value FROM _meta WHERE key = 'data_fingerprint'"
            ).fetchone()
            return row[0] if row else ''
        except:
            return ''

    def _store_fingerprint(self, fp: str):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS _meta (key VARCHAR PRIMARY KEY, value VARCHAR)
        """)
        self.conn.execute("""
            INSERT INTO _meta (key, value) VALUES ('data_fingerprint', ?)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
        """, (fp,))

    def create_unified_view(self):
        """
        Create a unified view of companies from CRM and BCG datasets.
        Uses the mapping service to link entities with different names.
        Skips the expensive DROP+CREATE if source data hasn't changed.
        """
        if not self.conn:
            self.initialize_database()
        
        # ---------------------------------------------------------------
        # Fast path: skip if data fingerprint unchanged and unified_companies exists
        # ---------------------------------------------------------------
        current_fp = self._compute_data_fingerprint()
        stored_fp = self._get_stored_fingerprint()
        tables = self.conn.execute("SHOW TABLES").df()['name'].tolist()
        if current_fp == stored_fp and 'unified_companies' in tables:
            cnt = self.conn.execute("SELECT COUNT(*) FROM unified_companies").fetchone()[0]
            if cnt > 0:
                self.add_log(f"Data unchanged — reusing cached unified view ({cnt} records). Skipping rematch.")
                _cache_clear()
                return

        self.add_log("Building Smart Joint between CRM and BCG datasets...")
        
        crm_names = self.conn.execute("SELECT DISTINCT name FROM crm_data").df()['name'].tolist()
        bcg_companies = self.conn.execute("SELECT DISTINCT company_internal FROM bcg_installed_base").df()['company_internal'].tolist()
        
        # Ensure company_mappings table exists
        self._ensure_schema()
        
        mappings_to_insert = []
        crm_names_set = {str(n).lower() for n in crm_names if pd.notna(n)}
        crm_names_map = {str(n).lower(): n for n in crm_names if pd.notna(n)}
        
        # ---------------------------------------------------------------
        # BATCH check: load all already-mapped BCG names in ONE query 
        # (previously this was an individual SELECT per BCG company → O(n) queries)
        # ---------------------------------------------------------------
        already_mapped = set(
            self.conn.execute("SELECT bcg_name FROM company_mappings").df()['bcg_name'].tolist()
        )
        
        new_bcg = [b for b in bcg_companies
                   if b and str(b).lower() != 'nan' and str(b) not in already_mapped]
        
        self.add_log(f"  {len(bcg_companies)} BCG companies | {len(already_mapped)} already matched | {len(new_bcg)} to process")
        
        for bcg_name in new_bcg:
            bcg_name_str = str(bcg_name)
            bcg_name_lower = bcg_name_str.lower()
            
            # 1. Faster exact match check
            if bcg_name_lower in crm_names_set:
                crm_name = crm_names_map[bcg_name_lower]
                mappings_to_insert.append((crm_name, bcg_name_str, 100.0))
                continue

            # 2. Fuzzy match + optional LLM verification
            match = mapping_service.find_best_match(bcg_name_str, crm_names)
            if match:
                crm_name, score = match
                mappings_to_insert.append((crm_name, bcg_name_str, float(score)))
                self.add_log(f"Mapped: '{bcg_name_str}' -> '{crm_name}' (score: {score})")
        
        if mappings_to_insert:
            self.conn.executemany(
                "INSERT OR IGNORE INTO company_mappings (crm_name, bcg_name, match_score) VALUES (?, ?, ?)", mappings_to_insert
            )
            
        self.conn.execute("DROP TABLE IF EXISTS unified_companies")
        
        # Calculate current year for age calculations
        current_year = pd.Timestamp.now().year
        
        self.conn.execute(f"""
            CREATE TABLE unified_companies AS
            WITH bcg_agg AS (
                SELECT 
                    COALESCE(m.crm_name, b.company_internal) as join_name,
                    MAX(b.company_internal) as bcg_name,
                    SUM(capacity_internal) as total_capacity,
                    AVG(m.match_score) as avg_match_score,
                    COUNT(*) as equip_count,
                    COUNT(DISTINCT equipment_type) as equip_types,
                    LIST(DISTINCT equipment_type) as equipment_list,
                    LIST(DISTINCT country_internal) as bcg_locations,
                    ANY_VALUE(country_internal) as first_country,
                    ANY_VALUE(region) as first_region,
                    MIN(start_year_internal) as oldest_year,
                    MAX(start_year_internal) as newest_year,
                    AVG(latitude_internal) as avg_lat,
                    AVG(longitude_internal) as avg_lon
                FROM bcg_installed_base b
                LEFT JOIN company_mappings m ON b.company_internal = m.bcg_name
                GROUP BY 1
            )
            SELECT 
                COALESCE(CAST(c.name AS VARCHAR), CAST(b.bcg_name AS VARCHAR)) as name,
                CAST(c.name AS VARCHAR) as crm_name,
                CAST(b.bcg_name AS VARCHAR) as bcg_name,
                COALESCE(CAST(c.industry AS VARCHAR), 'Unknown') as industry,
                COALESCE(CAST(c.country AS VARCHAR), CAST(b.first_country AS VARCHAR)) as country,
                COALESCE(CAST(c.region AS VARCHAR), CAST(b.first_region AS VARCHAR)) as region,
                CAST(c.rating AS VARCHAR) as rating,
                CAST(c.status AS VARCHAR) as status,
                CAST(c.fte AS DOUBLE) as fte,
                CAST(c.revenue AS DOUBLE) as revenue,
                CAST(b.avg_match_score AS DOUBLE) as "Matching Quality %",
                CAST(b.total_capacity AS DOUBLE) as total_capacity,
                CAST(b.equip_count AS INTEGER) as equip_count, 
                CAST(b.equip_types AS INTEGER) as equip_types,
                b.equipment_list,
                b.bcg_locations,
                CASE WHEN b.oldest_year IS NOT NULL THEN {current_year} - b.oldest_year ELSE NULL END as oldest_equip_age,
                CASE WHEN b.newest_year IS NOT NULL THEN {current_year} - b.newest_year ELSE NULL END as newest_equip_age,
                CAST(COALESCE(CAST(c.latitude AS DOUBLE), CAST(b.avg_lat AS DOUBLE)) AS DOUBLE) as map_latitude,
                CAST(COALESCE(CAST(c.longitude AS DOUBLE), CAST(b.avg_lon AS DOUBLE)) AS DOUBLE) as map_longitude,
                CAST(c.company_ceo AS VARCHAR) as company_ceo,
                CAST(c.fte_count AS DOUBLE) as fte_count
            FROM crm_data c
            LEFT JOIN bcg_agg b ON c.name = b.join_name
        """)
        
        # Add companies that are ONLY in BCG and not in CRM
        self.conn.execute(f"""
            INSERT INTO unified_companies (
                name, crm_name, bcg_name, industry, country, region, "Matching Quality %", 
                total_capacity, equip_count, equip_types, equipment_list, bcg_locations, 
                oldest_equip_age, newest_equip_age, map_latitude, map_longitude,
                rating, status, fte, revenue -- Add missing columns
            )
            SELECT 
                CAST(company_internal AS VARCHAR) as name,
                NULL as crm_name,
                CAST(company_internal AS VARCHAR) as bcg_name,
                'Steel' as industry,
                CAST(ANY_VALUE(country_internal) AS VARCHAR) as country,
                CAST(ANY_VALUE(region) AS VARCHAR) as region,
                NULL, -- No match score
                CAST(SUM(capacity_internal) AS DOUBLE) as total_capacity,
                CAST(COUNT(*) AS INTEGER), 
                CAST(COUNT(DISTINCT equipment_type) AS INTEGER),
                LIST(DISTINCT equipment_type),
                LIST(DISTINCT country_internal),
                CAST(MIN({current_year} - start_year_internal) AS INTEGER),
                CAST(MAX({current_year} - start_year_internal) AS INTEGER),
                CAST(AVG(latitude_internal) AS DOUBLE),
                CAST(AVG(longitude_internal) AS DOUBLE),
                'C', -- Default rating
                'Operating', -- Default status
                NULL, NULL -- fte, revenue
            FROM bcg_installed_base
            WHERE company_internal NOT IN (SELECT bcg_name FROM company_mappings)
            GROUP BY 1
        """)
        
        # Add DuckDB indexes for fast filter queries
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_uc_country ON unified_companies (country)",
            "CREATE INDEX IF NOT EXISTS idx_uc_region  ON unified_companies (region)",
            "CREATE INDEX IF NOT EXISTS idx_uc_name    ON unified_companies (name)",
            "CREATE INDEX IF NOT EXISTS idx_bcg_company ON bcg_installed_base (company_internal)",
            "CREATE INDEX IF NOT EXISTS idx_bcg_equip   ON bcg_installed_base (equipment_type)",
            "CREATE INDEX IF NOT EXISTS idx_bcg_country ON bcg_installed_base (country_internal)",
        ]:
            try:
                self.conn.execute(idx_sql)
            except:
                pass
        
        # Store fingerprint so next load can skip this work
        self._store_fingerprint(current_fp)
        
        # Invalidate module-level query cache
        _cache_clear()
        self.add_log("Unified view created successfully")

    def enrich_geo_coordinates(self, limit: int = 20):
        """Find missing latitude and longitude for companies"""
        if not self.conn:
            self.initialize_database()
            
        self.add_log(f"Searching for missing geographical coordinates (limit: {limit})...")
        
        try:
            query = """
                SELECT DISTINCT name 
                FROM unified_companies 
                WHERE map_latitude IS NULL OR map_longitude IS NULL
                LIMIT ?
            """
            companies_to_enrich = self.conn.execute(query, (limit,)).df()['name'].tolist()
            
            if not companies_to_enrich:
                self.add_log("  All companies have coordinates.")
                return
            
            geo_results = enrichment_service.enrich_locations(companies_to_enrich)
            
            update_count = 0
            for name, data in geo_results.items():
                lat = data.get('latitude')
                lon = data.get('longitude')
                country = data.get('country')
                
                if lat and lon:
                    self.conn.execute("""
                        UPDATE unified_companies 
                        SET map_latitude = ?,
                            map_longitude = ?,
                            country = COALESCE(country, ?)
                        WHERE name = ?
                    """, (lat, lon, country, name))
                    update_count += 1
            
            self.add_log(f"Successfully enriched {update_count} companies with geo-coordinates.")
            
        except Exception as e:
            self.add_log(f"Error during geo-enrichment: {e}")

    def enrich_company_data(self, limit: int = 20):
        """Find CEO and FTE for companies that don't have it"""
        if not self.conn:
            self.initialize_database()
            
        self.add_log(f"Searching internet for missing CEO and FTE data (limit: {limit} companies)...")
        
        # Find companies with missing data in unified_companies
        try:
            query = """
                SELECT DISTINCT name 
                FROM unified_companies 
                WHERE company_ceo IS NULL OR company_ceo = 'N/A' OR fte_count IS NULL OR fte_count = 0
                LIMIT ?
            """
            companies_to_enrich = self.conn.execute(query, (limit,)).df()['name'].tolist()
            
            if not companies_to_enrich:
                self.add_log("  No companies found requiring enrichment.")
                return
            
            enriched_results = enrichment_service.enrich_companies(companies_to_enrich)
            
            # Update unified_companies table
            update_count = 0
            for name, data in enriched_results.items():
                ceo = data.get('ceo')
                fte = data.get('fte')
                
                if ceo or fte:
                    self.conn.execute("""
                        UPDATE unified_companies 
                        SET company_ceo = COALESCE(?, company_ceo),
                            fte_count = COALESCE(?, fte_count)
                        WHERE name = ?
                    """, (ceo, fte, name))
                    update_count += 1
            
            self.add_log(f"Successfully enriched {update_count} companies with AI data.")
            
        except Exception as e:
            self.add_log(f"Error during enrichment: {e}")

    def get_customer_list(self, equipment_type: str = "All", country: str = "All", region: str = "All", company_name: str = "All") -> pd.DataFrame:
        """Get list of all customers from unified data with optional filtering.
        Uses in-process TTL cache; invalidated when create_unified_view runs."""
        conn = self.get_conn()
        if not conn:
            return pd.DataFrame()
        
        # Cache key includes all filter params
        cache_key = f"customer_list|{equipment_type}|{country}|{region}|{company_name}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        
        try:
            tables = conn.execute("SHOW TABLES").df()['name'].tolist()
            if 'unified_companies' not in tables:
                if 'crm_data' in tables:
                    return conn.execute("SELECT * FROM crm_data LIMIT 1000").df()
                return pd.DataFrame()
            
            # Start building query
            query = "SELECT * FROM unified_companies WHERE 1=1"
            params = []

            # Filter by region
            if region != "All" and hasattr(self, 'REGION_MAPPING') and region in self.REGION_MAPPING:
                region_values = [r.lower() for r in self.REGION_MAPPING[region]]
                filter_str = " OR ".join(["LOWER(region) LIKE ?"] * len(region_values))
                query += f" AND ({filter_str})"
                for r in region_values:
                    params.append(f"%{r}%")
            elif region == "Not assigned":
                query += " AND (region IS NULL OR region = '')"

            # Filter by country — match either CRM HQ country OR any plant in that country.
            # A multinational like Outokumpu (HQ=Finland) must appear when filtering by Germany
            # because they have plants there (stored in bcg_locations array).
            if country != "All":
                query += " AND (LOWER(country) = ? OR list_contains(bcg_locations, ?))"
                params.append(country.lower())
                # bcg_locations stores country_internal values with original casing (e.g. 'Germany')
                # Try title-cased version to match the BCG data
                params.append(country.title())

            # Filter by equipment
            if equipment_type != "All":
                internal_name = self.EQUIPMENT_MAP.get(equipment_type, equipment_type)
                query += " AND list_contains(equipment_list, ?)"
                params.append(internal_name)

            # Filter by company name
            if company_name != "All":
                query += " AND name = ?"
                params.append(company_name)

            query += " ORDER BY equip_count DESC NULLS LAST"
            
            result = conn.execute(query, params).df()
            
            # Safety check for 'name' column
            if not result.empty and 'name' not in result.columns:
                result.rename(columns={result.columns[0]: 'name'}, inplace=True)
            
            _cache_set(cache_key, result)
            return result
        except Exception as e:
            self.add_log(f"Error fetching customer list: {e}")
            import traceback
            self.add_log(traceback.format_exc())
            return pd.DataFrame()

    def get_all_equipment_types(self) -> List[str]:
        """Get list of all equipment types from BCG data"""
        return self.FIXED_EQUIPMENT_LIST
    
    def get_match_quality_stats(self) -> Dict[str, float]:
        """
        Calculate match quality statistics showing % of companies matched at different quality levels
        Returns dict with keys: excellent (100%), good (80-99%), okay (50-79%), poor (<50%)
        """
        if not self.conn:
            self.initialize_database()
        
        try:
            # Get all mappings
            mappings = self.conn.execute("SELECT crm_name, bcg_name FROM company_mappings").df()
            
            if mappings.empty:
                return {"excellent": 0, "good": 0, "okay": 0, "poor": 100}
            
            # Calculate match scores using fuzzy matching
            from thefuzz import fuzz
            
            excellent = 0
            good = 0
            okay = 0
            poor = 0
            
            for _, row in mappings.iterrows():
                crm_name = str(row['crm_name'])
                bcg_name = str(row['bcg_name'])
                
                # Calculate fuzzy match score
                score = fuzz.token_sort_ratio(crm_name, bcg_name)
                
                if score == 100:
                    excellent += 1
                elif score >= 80:
                    good += 1
                elif score >= 50:
                    okay += 1
                else:
                    poor += 1
            
            total = len(mappings)
            
            return {
                "excellent": (excellent / total) * 100 if total > 0 else 0,
                "good": (good / total) * 100 if total > 0 else 0,
                "okay": (okay / total) * 100 if total > 0 else 0,
                "poor": (poor / total) * 100 if total > 0 else 0
            }
            
        except Exception as e:
            self.add_log(f"Error calculating match quality stats: {e}")
            return {"excellent": 0, "good": 0, "okay": 0, "poor": 0}

    def export_unified_to_excel(self) -> bytes:
        """Export the unified customer view to Excel format"""
        df = self.get_customer_list()
        if df.empty:
            return None
            
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Unified Customers')
        
        return output.getvalue()

    def get_customer_detail(self, customer_id: str, equipment_type: str = "All") -> Dict:
        """Get detailed customer information by ID or Name from unified datasets"""
        if not self.conn:
            self.initialize_database()
        
        customer_data = {}
        
        try:
            unified = self.conn.execute(
                f"SELECT * FROM unified_companies WHERE name = ?", (customer_id,)
            ).df()
            if not unified.empty:
                customer_data['crm'] = unified.to_dict('records')[0]
        except:
            pass
            
        try:
            params = [customer_id, customer_id]
            eq_query = f"""
                SELECT * FROM bcg_installed_base 
                WHERE (company_internal = ? 
                OR company_internal IN (SELECT bcg_name FROM company_mappings WHERE crm_name = ?))
            """
            
            if equipment_type != "All":
                internal_name = self.EQUIPMENT_MAP.get(equipment_type, equipment_type)
                eq_query += " AND equipment_type = ?"
                params.append(internal_name)
                
            installed = self.conn.execute(eq_query, params).df()
            if not installed.empty:
                records = installed.to_dict('records')
                for rec in records:
                    if 'equipment_type' in rec and 'equipment' not in rec:
                        rec['equipment'] = rec['equipment_type']
                    if 'start_year_internal' in rec and 'installation_year' not in rec:
                        rec['installation_year'] = rec['start_year_internal']
                customer_data['installed_base'] = records
            else:
                customer_data['installed_base'] = []
        except:
            customer_data['installed_base'] = []
            
        return customer_data


    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# Singleton instance
data_service = DataIngestionService()
