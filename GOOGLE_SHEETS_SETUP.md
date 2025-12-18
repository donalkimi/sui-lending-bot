# Google Sheets Setup Guide

## Step 1: Create Your Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new blank spreadsheet
3. Rename it to "Sui Lending Bot Data" (or any name you prefer)

## Step 2: Create Three Sheets

Rename the default sheets and create the following three sheets:

### Sheet 1: "Protocol Lends"
This contains lending APY rates for each token across protocols.

**Format:**
- Column A: Token names (SUI, USDC, suiUSDT, USDY, AUSD, FDUSD, DEEP, WAL, etc.)
- Other columns: Protocol names (SuiLend, Navi, Alpha Fi, bluefin, Momentum, Cetus, Scallop, Turbos, etc.)
- Values: Lending APY as percentages (e.g., 5.20% or just 5.20)

**Example:**
```
|   A      |    B     |   C   |    D     |    E     |
|----------|----------|-------|----------|----------|
| Token    | SuiLend  | Navi  | Alpha Fi | bluefin  |
| SUI      | 3.80%    | 5.20% | 6.20%    | 1.60%    |
| USDC     | 4.90%    | 4.60% | 6.30%    | 6.80%    |
| suiUSDT  | 11.50%   | 6.00% | 7.10%    | 5.10%    |
| USDY     |          | 9.70% |          |          |
| FDUSD    |          | 5.10% |          |          |
| AUSD     | 7.00%    | 2.90% |          |          |
| DEEP     | 31%      | 28%   | 23%      | 22.70%   |
| WAL      | 35%      | 36%   | 35%      | 33.50%   |
```

### Sheet 2: "Protocol Borrows"
This contains borrow APY rates for each token across protocols.

**Format:**
- Same structure as "Protocol Lends"
- Values: Borrow APY as percentages

**Example:**
```
|   A      |    B     |   C   |    D     |    E     |
|----------|----------|-------|----------|----------|
| Token    | SuiLend  | Navi  | Alpha Fi | bluefin  |
| SUI      | 2.25%    | 1.90% | 3.40%    | 1.70%    |
| USDC     | 4.90%    | 3.70% | 4.50%    | 5.30%    |
| suiUSDT  | 11.60%   | 4.90% | 5.70%    | 3.80%    |
| USDY     |          | 5.90% |          |          |
| FDUSD    |          | 10.80%|          |          |
| AUSD     | 5.24     | 9.40% |          |          |
| DEEP     | 26.90%   | 19.50%| 17.50%   | 19%      |
| WAL      | 28.50%   | 24.20%| 20.00%   | 20.70%   |
```

### Sheet 3: "Collateral Ratios"
This contains maximum LTV (Loan-To-Value) ratios before liquidation.

**Format:**
- Same structure as other sheets
- Values: Collateral ratios as percentages (e.g., 75% means you can borrow up to 75% of your collateral value)

**Example:**
```
|   A      |    B     |   C   |    D     |    E     |
|----------|----------|-------|----------|----------|
| Token    | SuiLend  | Navi  | Alpha Fi | bluefin  |
| SUI      | 70%      | 75%   | 85%      | 85%      |
| USDC     | 77%      | 80%   | 85%      | 85%      |
| suiUSDT  | 77%      | 80%   | 85%      | 85%      |
| USDY     |          | 75%   |          |          |
| FDUSD    |          | 70%   |          |          |
| AUSD     | 77%      | 80%   |          |          |
| DEEP     | 19%      | 47%   | 80%      | 80%      |
| WAL      | 19%      | 60%   | 80%      | 80%      |
```

## Step 3: Get Your Sheet ID

1. Look at your Google Sheet URL
2. It will look like: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit#gid=0`
3. Copy the `SHEET_ID_HERE` part
4. Save it - you'll need it for `config/settings.py`

## Step 4: Set Up Google API Credentials

### A. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it "Sui Lending Bot" (or any name)
4. Click "Create"

### B. Enable Required APIs

1. In the left sidebar, go to "APIs & Services" → "Library"
2. Search for "Google Sheets API" → Click it → Click "Enable"
3. Search for "Google Drive API" → Click it → Click "Enable"

### C. Create Service Account Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Enter:
   - Service account name: "sui-lending-bot"
   - Service account ID: (auto-filled)
4. Click "Create and Continue"
5. For "Grant this service account access to project":
   - Select role: "Editor"
   - Click "Continue"
6. Click "Done"

### D. Download Credentials JSON

1. Click on the service account you just created (in the Service Accounts list)
2. Go to the "Keys" tab
3. Click "Add Key" → "Create new key"
4. Select "JSON" format
5. Click "Create"
6. A JSON file will download automatically
7. Rename it to `credentials.json`
8. Move it to your `config/` folder

### E. Share Your Sheet with the Service Account

**This is crucial!**

1. Open the downloaded `credentials.json` file
2. Find the `client_email` field (looks like: `sui-lending-bot@project-name.iam.gserviceaccount.com`)
3. Copy this email address
4. Go to your Google Sheet
5. Click "Share" (top right)
6. Paste the service account email
7. Give it "Editor" permissions
8. Click "Send"

## Step 5: Update Bot Configuration

Edit `config/settings.py`:

```python
GOOGLE_SHEETS_ID = "YOUR_SHEET_ID_FROM_STEP_3"
```

## Step 6: Test the Connection

Run this command to test:

```bash
python -c "from data.sheets_reader import SheetsReader; r = SheetsReader(); r.connect(); print('Success!')"
```

If you see "✓ Connected to Google Sheets", you're all set!

## Tips for Maintaining Your Sheet

### Data Entry Tips

1. **Use percentages**: Enter 5.2% or just 5.2 (both work)
2. **Leave empty cells**: If a protocol doesn't support a token, leave the cell empty
3. **Be consistent**: Use the same protocol names in all three sheets
4. **Update regularly**: The bot reads the sheet each time it runs

### Example Workflow

1. Visit each protocol's website/dashboard
2. Note down the current APY rates
3. Update your Google Sheet
4. The bot will automatically use the new data

### Where to Find Protocol Data

- **NAVI Protocol**: https://app.naviprotocol.io/
- **Scallop**: https://app.scallop.io/
- **SuiLend**: https://suilend.fi/
- (Add other protocols as you track them)

## Troubleshooting

### "Sheet not found"
- Check that your sheet names are exactly: "Protocol Lends", "Protocol Borrows", "Collateral Ratios"
- Names are case-sensitive

### "Permission denied"
- Make sure you shared the sheet with the service account email
- Check that the service account has "Editor" permissions

### "Unable to parse value"
- Make sure all numeric values are entered as numbers
- Remove any text or symbols except % sign
- Empty cells are OK

### "Invalid credentials"
- Verify `credentials.json` is in the `config/` folder
- Check that both Google Sheets API and Google Drive API are enabled
- Try creating a new service account and credentials

## Security Notes

⚠️ **Important:**
- Never commit `credentials.json` to git
- Never share your credentials file publicly
- The `.gitignore` file is set up to exclude it automatically
- Keep your service account email private

## Need Help?

If you run into issues:
1. Check the error messages carefully
2. Verify each step above
3. Make sure APIs are enabled
4. Confirm the service account has access to your sheet

Happy tracking! 🚀
