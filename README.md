# Sui Lending Bot 🚀

Cross-protocol yield optimizer for Sui blockchain lending markets. Analyzes lending/borrowing rates across multiple protocols to find optimal arbitrage opportunities using recursive leveraged positions.

## Features

- 📊 **Rate Analysis**: Analyzes all protocol and token combinations to find best yields
- 🔄 **Recursive Strategy**: Implements cross-protocol lending loops with safety buffers
- 💰 **Stablecoin Focus**: Special analysis for stablecoin pairs (USDC, suiUSDT, USDY, AUSD, FDUSD)
- 📈 **Dashboard**: Beautiful Streamlit dashboard for visualization
- 🔔 **Slack Alerts**: Real-time notifications for high APR opportunities
- ⚙️ **Configurable**: Adjustable liquidation distance and alert thresholds

## Strategy Overview

The bot implements a **market-neutral** recursive cross-protocol lending strategy:

1. **Lend** Stablecoin in Protocol A (e.g., USDY in NAVI)
2. **Borrow** High-Yield Token from Protocol A (e.g., DEEP from NAVI)
3. **Lend** High-Yield Token in Protocol B (e.g., DEEP in SuiLend)
4. **Borrow** Stablecoin from Protocol B (e.g., USDY from SuiLend)
5. **Repeat** - deposit borrowed Stablecoin back into Protocol A

**Critical**: The strategy **must start by lending a stablecoin** to remain market neutral and avoid directional price exposure to volatile tokens.

**Where the Yield Comes From:**
- **Primary**: Large spreads on high-yield tokens (DEEP, WAL, BLUE) - often 10%+ difference between lending and borrowing rates
- **Secondary**: Stablecoins provide cheap leverage and small additional yield

This creates a leveraged position that converges to steady-state sizes based on collateral ratios and safety buffers, while maintaining zero net exposure to volatile token prices.

See `STRATEGY_EXPLANATION.md` for detailed breakdown.

## Quick Start

### 1. Prerequisites

- Python 3.8+
- Google account with access to Google Sheets
- Slack workspace (optional, for alerts)

### 2. Installation

```bash
# Clone or download this repository
cd sui-lending-bot

# Install dependencies
pip install -r requirements.txt
```

### 3. Google Sheets Setup

#### A. Create Your Google Sheet

1. Create a new Google Sheet with three sheets:
   - **"Protocol Lends"** - Lending APY rates
   - **"Protocol Borrows"** - Borrow APY rates
   - **"Collateral Ratios"** - Max LTV ratios

2. Format each sheet like this:

**Protocol Lends:**
| Token    | SuiLend | Navi | Alpha Fi | bluefin | ... |
|----------|---------|------|----------|---------|-----|
| SUI      | 3.80%   | 5.20%| 6.20%    | 1.60%   | ... |
| USDC     | 4.90%   | 4.60%| 6.30%    | 6.80%   | ... |
| suiUSDT  | 11.50%  | 6.00%| 7.10%    | 5.10%   | ... |

**Protocol Borrows:**
| Token    | SuiLend | Navi | Alpha Fi | bluefin | ... |
|----------|---------|------|----------|---------|-----|
| SUI      | 2.25%   | 1.90%| 3.40%    | 1.70%   | ... |
| USDC     | 4.90%   | 3.70%| 4.50%    | 5.30%   | ... |

**Collateral Ratios:**
| Token    | SuiLend | Navi | Alpha Fi | bluefin | ... |
|----------|---------|------|----------|---------|-----|
| SUI      | 70%     | 75%  | 85%      | 85%     | ... |
| USDC     | 77%     | 80%  | 85%      | 85%     | ... |

3. Get your Google Sheet ID from the URL:
   - URL: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit`

#### B. Set Up Google API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create credentials:
   - Click "Create Credentials" → "Service Account"
   - Give it a name and click "Create"
   - Grant it "Editor" role
   - Click "Done"
5. Click on the service account email
6. Go to "Keys" tab → "Add Key" → "Create New Key" → "JSON"
7. Download the JSON file and save it as `config/credentials.json`
8. **Important**: Share your Google Sheet with the service account email (found in the JSON file)

### 4. Configuration

Edit `config/settings.py`:

```python
# Google Sheets Configuration
GOOGLE_SHEETS_ID = "YOUR_GOOGLE_SHEET_ID_HERE"  # From step 3.3

# Slack Configuration (optional)
SLACK_WEBHOOK_URL = "YOUR_SLACK_WEBHOOK_URL_HERE"

# Strategy Parameters
DEFAULT_LIQUIDATION_DISTANCE = 0.30  # 30% safety buffer
CHECK_INTERVAL_MINUTES = 15  # How often to check rates
```

To set up Slack webhooks:
1. Go to your Slack workspace settings
2. Navigate to "Apps" → "Incoming Webhooks"
3. Create a new webhook for your channel
4. Copy the webhook URL to `settings.py`

## Usage

### Option 1: Dashboard (Recommended)

Launch the interactive dashboard:

```bash
streamlit run dashboard/streamlit_app.py
```

Then open your browser to `http://localhost:8501`

The dashboard provides:
- 🏆 Best opportunities across all combinations
- 📊 All valid strategies with filtering
- 💰 Stablecoin-focused analysis
- 📈 Current rate tables

### Option 2: Command Line

Run analysis once:
```bash
python main.py --once
```

Run continuously (checks every X minutes):
```bash
python main.py
```

### Option 3: Import as Module

```python
from data.sheets_reader import SheetsReader
from analysis.rate_analyzer import RateAnalyzer

# Load data
reader = SheetsReader()
reader.connect()
lend_rates, borrow_rates, collateral_ratios = reader.get_all_data()

# Analyze
analyzer = RateAnalyzer(lend_rates, borrow_rates, collateral_ratios)
protocol_A, protocol_B, results = analyzer.find_best_protocol_pair()

# Get best strategy
best = results.iloc[0]
print(f"Best APR: {best['net_apr']:.2f}%")
```

## Project Structure

```
sui-lending-bot/
├── config/
│   ├── settings.py           # Configuration
│   └── credentials.json      # Google API credentials (you create this)
├── data/
│   └── sheets_reader.py      # Google Sheets integration
├── analysis/
│   ├── position_calculator.py  # Position size & APR calculations
│   └── rate_analyzer.py        # Strategy finder
├── alerts/
│   └── slack_notifier.py     # Slack notifications
├── dashboard/
│   └── streamlit_app.py      # Interactive dashboard
├── main.py                   # Main orchestration
└── requirements.txt          # Python dependencies
```

## How It Works

### Position Calculation

The bot calculates recursive position sizes using geometric series convergence:

```
r_A = collateral_ratio_A / (1 + liquidation_distance)
r_B = collateral_ratio_B / (1 + liquidation_distance)

L_A (total lent) = 1 / (1 - r_A * r_B)
B_A (total borrowed) = L_A * r_A
L_B = B_A
B_B = L_B * r_B
```

### Net APR Calculation

```
Net APR = (L_A * lend_rate_1A + L_B * lend_rate_2B) 
        - (B_A * borrow_rate_2A + B_B * borrow_rate_1B)
```

### Safety Features

- **Liquidation Distance**: Safety buffer from liquidation price (default 30%)
- **Convergence Check**: Ensures position converges (r_A * r_B < 1)
- **Missing Data Handling**: Gracefully skips incomplete data
- **Error Alerts**: Notifies via Slack if errors occur

## Configuration Options

### In `config/settings.py`:

```python
# Tokens to analyze
STABLECOINS = ["USDC", "suiUSDT", "USDY", "AUSD", "FDUSD"]
OTHER_TOKENS = ["DEEP", "WAL", "SUI"]

# Safety parameters
DEFAULT_LIQUIDATION_DISTANCE = 0.30  # 30% buffer
MIN_NET_APR_THRESHOLD = 0.5  # Minimum APR to consider

# Alert thresholds
ALERT_NET_APR_THRESHOLD = 5.0  # Alert when APR > 5%
ALERT_RATE_SPREAD_THRESHOLD = 2.0  # Alert when spread > 2%

# Scheduling
CHECK_INTERVAL_MINUTES = 15  # Check every 15 minutes
```

## Updating Data

### Manual Update (Current Implementation)

1. Update rates in your Google Sheet
2. The bot reads data on each check
3. Dashboard auto-refreshes every 5 minutes (or click "Refresh Data")

### Future: Automated Data Collection

The bot is designed to eventually fetch data automatically from:
- Sui RPC nodes
- Protocol APIs (NAVI, Scallop, etc.)
- On-chain data indexers

To implement this, replace `sheets_reader.py` with API-based fetchers.

## Troubleshooting

### "Credentials file not found"
- Make sure `config/credentials.json` exists
- Check that the path is correct in `settings.py`

### "Sheet not found"
- Verify sheet names match exactly: "Protocol Lends", "Protocol Borrows", "Collateral Ratios"
- Check that sheets exist in your Google Sheet

### "Permission denied"
- Share your Google Sheet with the service account email
- Email is in `credentials.json` under `client_email`

### "Position does not converge"
- Collateral ratios too high or liquidation distance too low
- Increase liquidation distance in settings
- Check that collateral ratio data is correct (should be < 1.0)

### Dashboard won't load
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Try: `streamlit run dashboard/streamlit_app.py --server.port 8502`

## Next Steps

### Phase 1: ✅ Monitoring & Analysis (Current)
- [x] Google Sheets data source
- [x] Rate analysis engine
- [x] Dashboard visualization
- [x] Slack alerts

### Phase 2: Automated Data Collection
- [ ] Integrate Sui RPC for live data
- [ ] Protocol-specific API connectors
- [ ] Historical data storage

### Phase 3: Execution
- [ ] Wallet integration
- [ ] Transaction builder
- [ ] Manual approval workflow
- [ ] Auto-execution with limits

### Phase 4: Advanced Features
- [ ] Gas cost optimization
- [ ] Multi-position management
- [ ] Risk analytics
- [ ] Backtesting

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## Disclaimer

**This bot is for informational and educational purposes only.**

- DeFi protocols involve significant financial risk
- Always verify data before making financial decisions
- Test with small amounts first
- The bot does not provide financial advice
- Use at your own risk

## License

MIT License - feel free to use and modify for your own purposes.

---

Built with ❤️ for the Sui DeFi community
