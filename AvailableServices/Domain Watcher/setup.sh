#!/bin/bash

# Create virtual environment
python -m venv ./venv

# Activate virtual environment
source ./venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Install Playwright Chromium
python -m playwright install chromium

echo ""
echo "Installed successfully."
echo "1. Copy config.example.json to config.json and fill in your credentials."
echo "2. Start the app with: python run.py"