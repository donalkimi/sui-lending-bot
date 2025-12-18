"""
Google Sheets data reader for protocol rates and collateral ratios
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Tuple
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


class SheetsReader:
    """Read lending rates, borrow rates, and collateral ratios from Google Sheets"""
    
    def __init__(self, credentials_file: str = None, sheet_id: str = None):
        """
        Initialize the Google Sheets reader
        
        Args:
            credentials_file: Path to Google API credentials JSON
            sheet_id: Google Sheets ID
        """
        self.credentials_file = credentials_file or settings.GOOGLE_CREDENTIALS_FILE
        self.sheet_id = sheet_id or settings.GOOGLE_SHEETS_ID
        self.client = None
        self.spreadsheet = None
        
    def connect(self):
        """Authenticate and connect to Google Sheets"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            creds = Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=scopes
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            print(f"✓ Connected to Google Sheets: {self.spreadsheet.title}")
            
        except FileNotFoundError:
            print(f"✗ Credentials file not found: {self.credentials_file}")
            print("Please download your Google API credentials and save them to config/credentials.json")
            raise
        except Exception as e:
            print(f"✗ Error connecting to Google Sheets: {e}")
            raise
    
    def read_sheet_to_dataframe(self, sheet_name: str) -> pd.DataFrame:
        """
        Read a sheet and convert to pandas DataFrame
        
        Args:
            sheet_name: Name of the sheet to read
            
        Returns:
            DataFrame with the sheet data
        """
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
            data = worksheet.get_all_values()
            
            if not data:
                return pd.DataFrame()
            
            # First row is headers
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # Convert numeric columns (all except first column which is token names)
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col].str.rstrip('%'), errors='coerce') / 100
            
            return df
            
        except gspread.exceptions.WorksheetNotFound:
            print(f"✗ Sheet '{sheet_name}' not found in spreadsheet")
            return pd.DataFrame()
        except Exception as e:
            print(f"✗ Error reading sheet '{sheet_name}': {e}")
            return pd.DataFrame()
    
    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch all data from the three main sheets
        
        Returns:
            Tuple of (lend_rates_df, borrow_rates_df, collateral_ratios_df)
        """
        if not self.client:
            self.connect()
        
        print("\n📊 Fetching data from Google Sheets...")
        
        lend_rates = self.read_sheet_to_dataframe(settings.SHEET_LENDS)
        print(f"  ✓ Loaded {len(lend_rates)} tokens lending rates")
        
        borrow_rates = self.read_sheet_to_dataframe(settings.SHEET_BORROWS)
        print(f"  ✓ Loaded {len(borrow_rates)} tokens borrow rates")
        
        collateral_ratios = self.read_sheet_to_dataframe(settings.SHEET_COLLATERAL_RATIOS)
        print(f"  ✓ Loaded {len(collateral_ratios)} tokens collateral ratios")
        
        return lend_rates, borrow_rates, collateral_ratios
    
    def get_protocol_list(self) -> list:
        """
        Get list of all protocols from the column headers
        
        Returns:
            List of protocol names
        """
        if not self.client:
            self.connect()
        
        lend_rates = self.read_sheet_to_dataframe(settings.SHEET_LENDS)
        # Return all columns except the first one (which is token names)
        return lend_rates.columns[1:].tolist()


# Example usage
if __name__ == "__main__":
    reader = SheetsReader()
    reader.connect()
    
    lend_df, borrow_df, collateral_df = reader.get_all_data()
    
    print("\n" + "="*60)
    print("LENDING RATES:")
    print(lend_df)
    
    print("\n" + "="*60)
    print("BORROW RATES:")
    print(borrow_df)
    
    print("\n" + "="*60)
    print("COLLATERAL RATIOS:")
    print(collateral_df)
    
    print("\n" + "="*60)
    print("PROTOCOLS:", reader.get_protocol_list())
