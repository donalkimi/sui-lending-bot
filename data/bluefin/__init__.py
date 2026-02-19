"""
Bluefin Protocol Integration

Fetches perpetual funding rates from Bluefin's public REST API.
"""

from .bluefin_reader import BluefinReader

__all__ = ["BluefinReader"]
