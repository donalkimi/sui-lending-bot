#!/usr/bin/env python3
"""
Setup verification script for Sui Lending Bot
Run this to check if everything is configured correctly
"""

import sys
import os

def check_python_version():
    """Check Python version"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ✗ Python {version.major}.{version.minor} (need 3.8+)")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print("\n📦 Checking dependencies...")
    required = [
        'pandas',
        'numpy',
        'gspread',
        'google.auth',
        'requests',
        'streamlit',
        'plotly'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"   ✓ {package}")
        except ImportError:
            print(f"   ✗ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\n   Install missing packages with: pip install -r requirements.txt")
        return False
    return True

def check_credentials():
    """Check if Google credentials file exists"""
    print("\n🔐 Checking Google API credentials...")
    creds_path = "config/credentials.json"
    
    if os.path.exists(creds_path):
        print(f"   ✓ {creds_path} exists")
        # Try to load it
        try:
            import json
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                if 'client_email' in creds:
                    print(f"   ✓ Service account: {creds['client_email']}")
                    print(f"   ℹ️  Make sure your Google Sheet is shared with this email!")
                    return True
                else:
                    print(f"   ✗ Invalid credentials file format")
                    return False
        except Exception as e:
            print(f"   ✗ Error reading credentials: {e}")
            return False
    else:
        print(f"   ✗ {creds_path} not found")
        print(f"   ℹ️  See GOOGLE_SHEETS_SETUP.md for instructions")
        return False

def check_config():
    """Check if configuration is set"""
    print("\n⚙️  Checking configuration...")
    
    try:
        from config import settings
        
        # Check Google Sheets ID
        if settings.GOOGLE_SHEETS_ID == "YOUR_GOOGLE_SHEET_ID_HERE":
            print(f"   ✗ Google Sheets ID not set")
            print(f"   ℹ️  Edit config/settings.py and add your sheet ID")
            return False
        else:
            print(f"   ✓ Google Sheets ID configured")
        
        # Check Slack (optional)
        if settings.SLACK_WEBHOOK_URL == "YOUR_SLACK_WEBHOOK_URL_HERE":
            print(f"   ⚠️  Slack webhook not configured (optional)")
        else:
            print(f"   ✓ Slack webhook configured")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error loading config: {e}")
        return False

def test_google_sheets_connection():
    """Test connection to Google Sheets"""
    print("\n📊 Testing Google Sheets connection...")
    
    try:
        from data.sheets_reader import SheetsReader
        
        reader = SheetsReader()
        reader.connect()
        
        lend_rates, borrow_rates, collateral_ratios = reader.get_all_data()
        
        if lend_rates.empty:
            print(f"   ⚠️  'Protocol Lends' sheet is empty")
        else:
            print(f"   ✓ Loaded {len(lend_rates)} tokens from 'Protocol Lends'")
        
        if borrow_rates.empty:
            print(f"   ⚠️  'Protocol Borrows' sheet is empty")
        else:
            print(f"   ✓ Loaded {len(borrow_rates)} tokens from 'Protocol Borrows'")
        
        if collateral_ratios.empty:
            print(f"   ⚠️  'Collateral Ratios' sheet is empty")
        else:
            print(f"   ✓ Loaded {len(collateral_ratios)} tokens from 'Collateral Ratios'")
        
        return not (lend_rates.empty or borrow_rates.empty or collateral_ratios.empty)
        
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        print(f"   ℹ️  Check GOOGLE_SHEETS_SETUP.md for troubleshooting")
        return False

def main():
    """Run all checks"""
    print("="*80)
    print("🚀 SUI LENDING BOT - Setup Verification")
    print("="*80)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Credentials", check_credentials),
        ("Configuration", check_config),
        ("Google Sheets", test_google_sheets_connection),
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
        if not result:
            all_passed = False
    
    print("="*80)
    
    if all_passed:
        print("\n🎉 All checks passed! You're ready to run the bot.")
        print("\nNext steps:")
        print("  • Run analysis: python main.py --once")
        print("  • Start dashboard: streamlit run dashboard/streamlit_app.py")
        print("  • Run continuously: python main.py")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\nFor help, see:")
        print("  • README.md - General setup guide")
        print("  • GOOGLE_SHEETS_SETUP.md - Detailed Google Sheets setup")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
