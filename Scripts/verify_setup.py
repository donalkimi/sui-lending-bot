#!/usr/bin/env python3
"""
Setup verification script for Sui Lending Bot
Run this to check if everything is configured correctly
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_python_version():
    """Check Python version"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"   ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ✗ Python {version.major}.{version.minor} (need 3.9+)")
        return False


def check_python_dependencies():
    """Check if required Python packages are installed"""
    print("\n📦 Checking Python dependencies...")
    required = [
        'pandas',
        'numpy',
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


def check_node_sdks():
    """Check if Node.js SDKs are installed"""
    print("\n📡 Checking Node.js SDK installations...")
    
    sdk_dirs = [
        ('AlphaFi', 'data/alphalend/node_modules'),
        ('Suilend', 'data/suilend/node_modules')
    ]
    
    all_installed = True
    for name, path in sdk_dirs:
        if os.path.exists(path):
            print(f"   ✓ {name} SDK installed")
        else:
            print(f"   ✗ {name} SDK not installed")
            all_installed = False
    
    if not all_installed:
        print(f"\n   Install SDKs with: npm run install-sdks-separately")
        return False
    
    return True


def check_config():
    """Check if configuration is set"""
    print("\n⚙️  Checking configuration...")
    
    try:
        from config import settings
        from config.stablecoins import STABLECOIN_CONTRACTS
        
        print(f"   ✓ Liquidation distance: {settings.DEFAULT_LIQUIDATION_DISTANCE*100:.0f}%")
        print(f"   ✓ Alert threshold: {settings.ALERT_NET_APR_THRESHOLD}% APR")
        print(f"   ✓ Check interval: {settings.CHECK_INTERVAL_MINUTES} minutes")
        print(f"   ✓ Stablecoins configured: {len(STABLECOIN_CONTRACTS)}")
        
        # Check Slack (optional)
        if 'YOUR_SLACK_WEBHOOK_URL_HERE' in settings.SLACK_WEBHOOK_URL:
            print(f"   ⚠️  Slack webhook not configured (optional)")
        else:
            print(f"   ✓ Slack webhook configured")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error loading config: {e}")
        return False


def test_protocol_connections():
    """Test connections to all protocols"""
    print("\n🔌 Testing protocol connections...")
    
    try:
        from data.protocol_merger import merge_protocol_data
        from config.stablecoins import STABLECOIN_CONTRACTS
        
        lend_rates, borrow_rates, collateral_ratios = merge_protocol_data(
            stablecoin_contracts=STABLECOIN_CONTRACTS
        )
        
        if lend_rates.empty:
            print(f"   ✗ No lending data retrieved")
            return False
        
        if borrow_rates.empty:
            print(f"   ✗ No borrow data retrieved")
            return False
        
        if collateral_ratios.empty:
            print(f"   ✗ No collateral data retrieved")
            return False
        
        print(f"   ✓ Successfully loaded data for {len(lend_rates)} tokens")
        
        # Check protocol coverage
        protocols = ['Navi', 'AlphaFi', 'Suilend']
        for protocol in protocols:
            if protocol in lend_rates.columns:
                count = lend_rates[protocol].notna().sum()
                print(f"   ✓ {protocol}: {count} tokens")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Protocol connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks"""
    print("="*80)
    print("🚀 SUI LENDING BOT - Setup Verification")
    print("="*80)
    
    checks = [
        ("Python Version", check_python_version),
        ("Python Dependencies", check_python_dependencies),
        ("Node.js SDKs", check_node_sdks),
        ("Configuration", check_config),
        ("Protocol Connections", test_protocol_connections),
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
        print("\nFor help, see README.md")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())