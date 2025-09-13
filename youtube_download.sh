#!/bin/bash

# This script activates the local Python virtual environment
# and runs the youtube_download.py script.

# Find the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Set paths to your venv and Python script
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
PYTHON_SCRIPT="$SCRIPT_DIR/youtube_download.py"

# --- Pre-run Checks ---
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Python interpreter not found in virtual environment."
    echo "Please make sure a 'venv' folder exists and is set up correctly."
    read -p "Press Enter to exit."
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: The main script 'youtube_download.py' was not found."
    read -p "Press Enter to exit."
    exit 1
fi

# --- Run the Script ---
echo "Starting the YouTube Downloader script..."
"$VENV_PYTHON" "$PYTHON_SCRIPT"

echo
echo "Script has been closed. The terminal will close now."
sleep 3
