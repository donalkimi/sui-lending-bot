# Sui Lending Bot - Complete Project

## 📦 What You Have

A complete, working Python bot for analyzing cross-protocol lending opportunities on Sui blockchain.

## 🎯 What It Does

1. **Analyzes** lending/borrowing rates across multiple Sui protocols
2. **Calculates** optimal recursive lending strategies
3. **Finds** the best protocol pairs and token combinations
4. **Visualizes** everything in a beautiful dashboard
5. **Alerts** you via Slack when opportunities arise

## 📁 Project Structure

```
sui-lending-bot/
├── README.md                    # Full documentation
├── QUICKSTART.md               # 10-minute setup guide
├── GOOGLE_SHEETS_SETUP.md      # Detailed Google Sheets setup
├── requirements.txt            # Python dependencies
├── verify_setup.py             # Setup verification script
├── main.py                     # Main bot orchestration
├── .gitignore                  # Git ignore file
│
├── config/
│   ├── settings.py            # Configuration (YOU EDIT THIS)
│   └── credentials.json       # (YOU CREATE THIS - see setup guide)
│
├── data/
│   └── sheets_reader.py       # Google Sheets integration
│
├── analysis/
│   ├── position_calculator.py # Position & APR calculations
│   └── rate_analyzer.py       # Strategy finder
│
├── alerts/
│   └── slack_notifier.py      # Slack notifications
│
└── dashboard/
    └── streamlit_app.py       # Interactive dashboard
```

## 🚀 Getting Started (10 Minutes)

### Step 1: Install (2 min)
```bash
pip install -r requirements.txt
```

### Step 2: Google Sheets (5 min)
1. Create a Google Sheet with your protocol data
2. Set up Google API credentials
3. Get your sheet ID

See `GOOGLE_SHEETS_SETUP.md` for detailed instructions.

### Step 3: Configure (1 min)
Edit `config/settings.py`:
- Add your Google Sheet ID
- (Optional) Add Slack webhook URL

### Step 4: Verify (1 min)
```bash
python verify_setup.py
```

### Step 5: Run! (1 min)
```bash
# Dashboard
streamlit run dashboard/streamlit_app.py

# Command line
python main.py --once
```

## 📊 Features

### Core Analysis Engine
- **Recursive Position Calculator**: Calculates leveraged cross-protocol positions
- **Net APR Calculator**: Computes total yield after borrowing costs
- **Safety Checks**: Ensures positions converge with liquidation buffers
- **Bidirectional Analysis**: Checks both protocol directions

### Dashboard
- **Best Opportunities**: See top strategies instantly
- **All Strategies**: Browse and filter all valid combinations
- **Stablecoin Focus**: Dedicated analysis for stablecoins
- **Rate Tables**: View all current rates
- **Interactive**: Adjust liquidation distance in real-time

### Alerts
- **High APR Alerts**: Notified when APR exceeds threshold
- **Rebalance Alerts**: Alerted when better opportunities arise
- **Error Alerts**: Know immediately if something goes wrong

### Configuration
- **Liquidation Distance**: Adjustable safety buffer (default 30%)
- **Token Lists**: Configure which tokens to analyze
- **Alert Thresholds**: Set your own notification triggers
- **Check Interval**: Control how often to analyze rates

## 🧮 The Strategy

### How It Works

1. **Lend** Token1 in Protocol A (e.g., USDY in NAVI)
2. **Borrow** Token2 from Protocol A (e.g., DEEP)
3. **Lend** Token2 in Protocol B (e.g., DEEP in SuiLend)
4. **Borrow** Token1 from Protocol B (e.g., USDY)
5. **Repeat** - creating recursive leverage

### Position Calculation

```
Effective Ratio A = Collateral_A / (1 + Liquidation_Distance)
Effective Ratio B = Collateral_B / (1 + Liquidation_Distance)

Total Lent A = 1 / (1 - Ratio_A × Ratio_B)
Total Borrowed A = Total_Lent_A × Ratio_A
Total Lent B = Total_Borrowed_A
Total Borrowed B = Total_Lent_B × Ratio_B
```

### Net APR Formula

```
Net APR = (Lent_A × Rate_Lend_A + Lent_B × Rate_Lend_B)
        - (Borrowed_A × Rate_Borrow_A + Borrowed_B × Rate_Borrow_B)
```

## 📝 Data Format

Your Google Sheet needs three sheets:

### "Protocol Lends"
| Token | SuiLend | Navi | Alpha Fi | bluefin |
|-------|---------|------|----------|---------|
| USDC  | 4.90%   | 4.60%| 6.30%    | 6.80%   |
| SUI   | 3.80%   | 5.20%| 6.20%    | 1.60%   |

### "Protocol Borrows"
| Token | SuiLend | Navi | Alpha Fi | bluefin |
|-------|---------|------|----------|---------|
| USDC  | 4.90%   | 3.70%| 4.50%    | 5.30%   |
| SUI   | 2.25%   | 1.90%| 3.40%    | 1.70%   |

### "Collateral Ratios"
| Token | SuiLend | Navi | Alpha Fi | bluefin |
|-------|---------|------|----------|---------|
| USDC  | 77%     | 80%  | 85%      | 85%     |
| SUI   | 70%     | 75%  | 85%      | 85%     |

## 🔧 Key Files to Edit

### Required Setup:
1. **config/settings.py** - Add your Google Sheet ID
2. **config/credentials.json** - Download from Google Cloud Console

### Optional Customization:
- **config/settings.py** - Adjust tokens, thresholds, intervals
- **Google Sheet** - Update rates as markets change

## 🎓 Usage Examples

### Run Analysis Once
```bash
python main.py --once
```

### Run Continuously
```bash
python main.py  # Checks every 15 minutes
```

### Launch Dashboard
```bash
streamlit run dashboard/streamlit_app.py
```

### Import as Module
```python
from data.sheets_reader import SheetsReader
from analysis.rate_analyzer import RateAnalyzer

reader = SheetsReader()
reader.connect()
data = reader.get_all_data()

analyzer = RateAnalyzer(*data)
best_protocol_A, best_protocol_B, results = analyzer.find_best_protocol_pair()

print(f"Best APR: {results.iloc[0]['net_apr']:.2f}%")
```

## 🐛 Troubleshooting

Common issues and solutions:

1. **"Credentials not found"**
   - Create `config/credentials.json` from Google Cloud Console

2. **"Permission denied"**
   - Share your Google Sheet with the service account email

3. **"Sheet not found"**
   - Check sheet names exactly match: "Protocol Lends", "Protocol Borrows", "Collateral Ratios"

4. **"Position does not converge"**
   - Increase liquidation distance
   - Check collateral ratios are correct

Run `python verify_setup.py` to diagnose issues.

## 🔄 Future Enhancements

This bot is designed for easy extension:

### Phase 2: Automated Data
- Replace Google Sheets with direct protocol API calls
- Add Sui RPC integration
- Store historical data

### Phase 3: Execution
- Wallet integration
- Transaction building
- Automated rebalancing

### Phase 4: Advanced Analytics
- Gas cost optimization
- Risk metrics
- Backtesting

## 📚 Documentation Files

- **README.md** - Complete documentation
- **QUICKSTART.md** - Fast setup guide
- **GOOGLE_SHEETS_SETUP.md** - Detailed Google setup
- **This file** - Project overview

## 🔐 Security

- Never commit `credentials.json` (included in .gitignore)
- Keep your service account email private
- Don't share API keys or webhooks
- Test with small amounts first

## 📜 License

MIT License - Free to use and modify

## 🎉 You're Ready!

Everything you need is here:
✅ Complete, working codebase
✅ Comprehensive documentation
✅ Setup verification tools
✅ Interactive dashboard
✅ Slack integration
✅ Extensible architecture

Start with the `QUICKSTART.md` guide and you'll be running in 10 minutes!

Questions? Check the documentation or run `python verify_setup.py` to diagnose issues.

Happy yield farming! 🚀
