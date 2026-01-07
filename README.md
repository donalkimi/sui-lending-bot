# Sui Lending Bot

Cross-protocol yield optimization bot for Sui DeFi lending markets.

## Installation

### Prerequisites
- Python 3.9+
- Node.js 16+

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd sui-lending-bot
   ```

2. **(Optional but recommended) Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Node.js SDK dependencies:**
   ```bash
   npm run install-sdks-separately
   ```
   
   > **Note:** SDKs are installed separately in their respective directories (`data/alphalend/` and `data/suilend/`) to avoid dependency version conflicts between the AlphaFi and Suilend SDKs.

5. **Configure settings:**
   
   Edit `config/settings.py` to add your Slack webhook URL (optional) and adjust other settings as needed.

## Running the Bot

**Run once:**
```bash
python main.py --once
```

**Run continuously:**
```bash
python main.py
```

**Run dashboard:**
```bash
streamlit run dashboard/streamlit_app.py
```

## Configuration

- **Settings:** `config/settings.py` - Bot configuration (liquidation distance, alert thresholds, Slack webhook)
- **Stablecoins:** `config/stablecoins.py` - Stablecoin contract definitions

## Features

- Real-time data fetching from Navi, AlphaFi, and Suilend protocols
- Market-neutral recursive lending strategy analysis
- Stablecoin fungibility support (1:1 conversions)
- Contract-based token matching for accuracy
- Interactive Streamlit dashboard
- Slack notifications for high APR opportunities
