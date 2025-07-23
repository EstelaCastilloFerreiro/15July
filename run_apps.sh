#!/bin/bash

# TRUCCO Analytics - Application Launcher
# This script helps you run either the fixed Streamlit app or the new Dash app

echo "🚀 TRUCCO Analytics - Application Launcher"
echo "==========================================="
echo ""
echo "Choose which application to run:"
echo "1. Fixed Streamlit App (Original, all bugs fixed)"
echo "2. New Dash App (Recommended - Modern UI)"
echo "3. Install dependencies only"
echo "4. Exit"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🔧 Starting Fixed Streamlit Application..."
        echo "Access the app at: http://localhost:8501"
        echo "Press Ctrl+C to stop"
        echo ""
        python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0
        ;;
    2)
        echo ""
        echo "✨ Starting New Dash Application..."
        echo "Access the app at: http://localhost:8050"
        echo "Press Ctrl+C to stop"
        echo ""
        python3 dash_app.py
        ;;
    3)
        echo ""
        echo "📦 Installing dependencies..."
        python3 -m pip install --break-system-packages -r requirements.txt
        echo "✅ Dependencies installed successfully!"
        ;;
    4)
        echo "👋 Goodbye!"
        exit 0
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac