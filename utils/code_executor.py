import os
import secrets
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def detect_dependencies(code):
    """
    Detect common ML libraries used in the code.
    
    Args:
        code: Python code string
    
    Returns:
        List of detected dependencies
    """
    dependencies = []
    common_imports = {
        'sklearn': 'scikit-learn',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'matplotlib': 'matplotlib',
        'seaborn': 'seaborn',
        'tensorflow': 'tensorflow',
        'torch': 'torch',
        'cv2': 'opencv-python',
        'PIL': 'Pillow',
        'plotly': 'plotly',
        'keras': 'keras',
        'scipy': 'scipy',
        'xgboost': 'xgboost',
        'lightgbm': 'lightgbm'
    }
    
    for import_name, package_name in common_imports.items():
        if f"import {import_name}" in code or f"from {import_name}" in code:
            dependencies.append(package_name)
    
    return list(set(dependencies))  # Remove duplicates

def save_code_to_file(code, topic):
    """
    Save generated code to a file
    
    Args:
        code: Python code string
        topic: Topic name for filename
    
    Returns:
        Filename of saved code or None if failed
    """
    if not code or not code.strip():
        logger.warning("Cannot save empty code.")
        return None
    
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        # A random component, because the app is now multi-user and these files
        # sit in one shared directory: topic plus timestamp is guessable, which
        # would let one learner fetch another's generated file. The name is the
        # only thing protecting it, so it has to be unguessable.
        filename = f"{safe_topic}_{timestamp}_{secrets.token_urlsafe(9)}.py"
        filepath = os.path.join(os.getenv('DATA_DIR', '.'), 'generated_code', filename)
        
        # Save code
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        logger.info(f"Code saved successfully: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Failed to save code: {e}")
        return None

def get_execution_instructions():
    """
    Get instructions for running generated code
    
    Returns:
        Dictionary with execution instructions
    """
    return {
        "google_colab": {
            "name": "Google Colab",
            "url": "https://colab.research.google.com/",
            "steps": [
                "Click 'Open Google Colab' button",
                "Create a new notebook",
                "Copy and paste the code into a cell",
                "Run the cell with Shift + Enter",
                "Install dependencies if needed: !pip install package_name"
            ]
        },
        "local": {
            "name": "Local Environment",
            "steps": [
                "Save the code to a .py file",
                "Open terminal/command prompt",
                "Navigate to the directory",
                "Install dependencies: pip install -r requirements.txt",
                "Run the script: python filename.py"
            ]
        },
        "jupyter": {
            "name": "Jupyter Notebook",
            "steps": [
                "Start Jupyter: jupyter notebook",
                "Create a new notebook",
                "Copy code into cells",
                "Run cells sequentially",
                "Install packages in cells: !pip install package_name"
            ]
        }
    }

def delete_old_code_files(max_age_hours=24):
    """
    Delete code files older than specified hours
    
    Args:
        max_age_hours: Maximum age of files to keep in hours
    """
    try:
        code_dir = os.path.join(os.getenv('DATA_DIR', '.'), 'generated_code')
        if not os.path.exists(code_dir):
            return
        
        current_time = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(code_dir):
            filepath = os.path.join(code_dir, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    logger.info(f"Deleted old code file: {filename}")
    
    except Exception as e:
        logger.error(f"Error deleting old code files: {e}")
