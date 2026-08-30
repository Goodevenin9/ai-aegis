#!/bin/bash
# Post-installation script for Aegis on Linux

echo "Aegis installed successfully!"
echo ""
echo "To start Aegis as a background service:"
echo "  systemctl --user enable aegis"
echo "  systemctl --user start aegis"
echo ""
echo "To run the desktop app:"
echo "  aegis"
echo ""
echo "API endpoint will be available at: http://localhost:8741/analyze"
