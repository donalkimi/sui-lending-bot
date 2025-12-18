# Quick Start Guide

Get your Sui Lending Bot up and running in 10 minutes!

## 1. Install Dependencies (2 minutes)

```bash
cd sui-lending-bot
pip install -r requirements.txt
```

## 2. Set Up Google Sheets (5 minutes)

### Create Your Sheet
1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Create three sheets: "Protocol Lends", "Protocol Borrows", "Collateral Ratios"
4. Add your data (see GOOGLE_SHEETS_SETUP.md for format)

### Get Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project
3. Enable Google Sheets API and Google Drive API
4. Create a Service Account
5. Download JSON key as `config/credentials.json`
6. **Share your Google Sheet with the service account email**

Detailed instructions: See `GOOGLE_SHEETS_SETUP.md`

## 3. Configure the Bot (1 minute)

Edit `config/settings.py`:

```python
# Your Google Sheet ID (from the URL)
GOOGLE_SHEETS_ID = "YOUR_SHEET_ID_HERE"

# Optional: Your Slack webhook
SLACK_WEBHOOK_URL = "YOUR_WEBHOOK_URL"
```

## 4. Verify Setup (1 minute)

```bash
python verify_setup.py
```

This will check if everything is configured correctly.

## 5. Run the Bot! (1 minute)

### Option A: Interactive Dashboard (Recommended)
```bash
streamlit run dashboard/streamlit_app.py
```
Open http://localhost:8501 in your browser

### Option B: Command Line
```bash
# Run once
python main.py --once

# Run continuously (checks every 15 minutes)
python main.py
```

## What You'll See

### Dashboard Features:
- 🏆 **Best Opportunities**: Top strategies across all protocols
- 📊 **All Strategies**: Complete list with filtering
- 💰 **Stablecoin Focus**: Best stablecoin pairs
- 📈 **Rate Tables**: Current rates from your sheet

### Example Output:
```
Best APR: 15.50%
Protocol A: NAVI
Protocol B: SuiLend
Token Pair: USDY <-> DEEP
Leverage: 1.09x
```

## Common Issues

### "Credentials not found"
- Make sure `config/credentials.json` exists
- Download it from Google Cloud Console

### "Permission denied"
- Share your Google Sheet with the service account email
- Email is in `credentials.json` → `client_email`

### "Sheet not found"
- Check sheet names are exactly: "Protocol Lends", "Protocol Borrows", "Collateral Ratios"
- Names are case-sensitive!

### Need more help?
- See `README.md` for full documentation
- See `GOOGLE_SHEETS_SETUP.md` for detailed Google setup

## Next Steps

1. ✅ Get the bot running
2. 📊 Update your Google Sheet with real data
3. 🔔 Set up Slack alerts (optional)
4. 🔄 Run continuously to monitor opportunities

Happy yield farming! 🚀
