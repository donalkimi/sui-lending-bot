"""
Main orchestration script for Sui Lending Bot
"""

import time
from datetime import datetime
from config import settings
from data.sheets_reader import SheetsReader
from data.api_enricher import enrich_with_navi_data, enrich_with_alphafi_data
from analysis.rate_analyzer import RateAnalyzer
from alerts.slack_notifier import SlackNotifier


class SuiLendingBot:
    """Main bot controller"""
    
    def __init__(self):
        """Initialize the bot"""
        self.reader = SheetsReader()
        self.notifier = SlackNotifier()
        self.last_best_strategy = None
        
        print("\n" + "="*80)
        print("🚀 SUI LENDING BOT - Cross-Protocol Yield Optimizer")
        print("="*80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Check interval: {settings.CHECK_INTERVAL_MINUTES} minutes")
        print(f"Liquidation distance: {settings.DEFAULT_LIQUIDATION_DISTANCE*100:.0f}%")
        print("="*80 + "\n")
    
    def run_analysis(self):
        """Run a single analysis cycle"""
        try:
            print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Running analysis...")
            
            # Load data from Google Sheets
            lend_rates, borrow_rates, collateral_ratios = self.reader.get_all_data()
            
            if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
                print("✗ No data available")
                return
                

            # Enrich with live API data (Navi)
            lend_rates, borrow_rates, collateral_ratios, navi_meta = enrich_with_navi_data(
                lend_rates, borrow_rates, collateral_ratios
            )

            # Enrich with live SDK data (AlphaFi via Node)
            lend_rates, borrow_rates, collateral_ratios, alphafi_meta = enrich_with_alphafi_data(
                lend_rates, borrow_rates, collateral_ratios,
                node_script_path="data/alphalend_reader-sdk.mjs"  # adjust if needed
            )

            # Initialize analyzer
            analyzer = RateAnalyzer(
                lend_rates=lend_rates,
                borrow_rates=borrow_rates,
                collateral_ratios=collateral_ratios,
                liquidation_distance=settings.DEFAULT_LIQUIDATION_DISTANCE
            )
            
            # Find best protocol pair
            protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()
            
            if all_results.empty:
                print("✗ No valid strategies found")
                return
            
            # Get best strategy
            best = all_results.iloc[0].to_dict()
            
            # Check if APR exceeds alert threshold
            if best['net_apr'] >= settings.ALERT_NET_APR_THRESHOLD:
                self.notifier.alert_high_apr(best)
            
            # Check for rebalance opportunity
            if self.last_best_strategy:
                apr_improvement = best['net_apr'] - self.last_best_strategy['net_apr']
                
                # Alert if improvement is significant (> 1% APR)
                if apr_improvement > 1.0:
                    self.notifier.alert_rebalance_opportunity(
                        current_strategy=self.last_best_strategy,
                        new_strategy=best,
                        apr_improvement=apr_improvement
                    )
            
            # Update last best strategy
            self.last_best_strategy = best
            
            print("\n" + "="*80)
            print("✓ Analysis complete")
            print("="*80 + "\n")
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            print(f"✗ {error_msg}")
            self.notifier.alert_error(error_msg)
    
    def run_once(self):
        """Run analysis once and exit"""
        try:
            self.reader.connect()
            self.run_analysis()
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            self.notifier.alert_error(f"Fatal error: {str(e)}")
    
    def run_continuously(self):
        """Run analysis on a schedule"""
        try:
            self.reader.connect()
            
            print("🔄 Running in continuous mode")
            print(f"Will check every {settings.CHECK_INTERVAL_MINUTES} minutes")
            print("Press Ctrl+C to stop\n")
            
            while True:
                self.run_analysis()
                
                # Wait for next check
                next_check = datetime.now().timestamp() + (settings.CHECK_INTERVAL_MINUTES * 60)
                next_check_time = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
                print(f"💤 Sleeping until {next_check_time}...")
                
                time.sleep(settings.CHECK_INTERVAL_MINUTES * 60)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            self.notifier.alert_error(f"Fatal error: {str(e)}")


def main():
    """Main entry point"""
    import sys
    
    bot = SuiLendingBot()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Running once...")
        bot.run_once()
    else:
        print("Running continuously...")
        print("Use --once flag to run just once")
        bot.run_continuously()


if __name__ == "__main__":
    main()
