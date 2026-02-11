"""
Stablecoin Configuration

Defines which tokens are considered stablecoins for the lending bot.
Stablecoins are treated as fungible (1:1 convertible) and are excluded 
from single-protocol filtering rules.
"""

# Stablecoin definitions: {symbol: contract_address}
STABLECOINS = {
    'USDC': '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC',
    'USDY': '0x960b531667636f39e85867775f52f6b1f220a058c4de786905bdf761e06a56bb::usdy::USDY',
    'AUSD': '0x2053d08c1e2bd02791056171aab0fd12bd7cd7efad2ab8f6b9c8902f14df2ff2::ausd::AUSD',
    'FDUSD': '0xf16e6b723f242ec745dfd7634ad072c42d5c1d9ac9d62a39c381303eaa57693a::fdusd::FDUSD',
    'suiUSDT': '0x375f70cf2ae4c00bf37117d0c85a2c71545e6ee05c4a5c7d282cd66a4504b068::usdt::USDT',
    'suiUSDe': '0x41d587e5336f1c86cad50d38a7136db99333bb9bda91cea4ba69115defeb1402::sui_usde::SUI_USDE'
}

# Extract just the symbols for easy checking
STABLECOIN_SYMBOLS = set(STABLECOINS.keys())

# Extract just the contracts for matching by address
STABLECOIN_CONTRACTS = set(STABLECOINS.values())