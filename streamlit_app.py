"""
Main entry point for Streamlit Cloud deployment.
This file fixes the import path issues when running on Streamlit Cloud.
"""

import sys
import os

# Add the project root to Python path so 'src' module can be found
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Now import and run the main streamlit app
# We need to execute the app code directly
exec(open(os.path.join(ROOT_DIR, "src", "app", "streamlit_app.py")).read())
