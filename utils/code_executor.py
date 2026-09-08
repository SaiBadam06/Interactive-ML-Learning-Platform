import ast
import os
import re
import secrets
import sys
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


# ---------------------------------------------------------------- packages
# What a learner needs to know about an import is three things: does it have to
# be installed, what is it installed as, and what is it doing here. None of that
# has to come from the model, so none of it does - a hallucinated pip name is a
# command that fails on their machine.

# Import name -> pip name, only where the two differ. Everything else installs
# under the name it is imported by.
PIP_NAMES = {
    'sklearn': 'scikit-learn',
    'cv2': 'opencv-python',
    'PIL': 'Pillow',
    'skimage': 'scikit-image',
    'yaml': 'PyYAML',
    'bs4': 'beautifulsoup4',
    'dateutil': 'python-dateutil',
    'gym': 'gymnasium',
    'mpl_toolkits': 'matplotlib',
}

# One line on what each one is doing in a machine learning program. Only the
# libraries this subject actually reaches for; anything else gets a truthful
# generic line rather than a guess.
PACKAGE_ROLES = {
    'numpy': 'Arrays and the maths on them. Nearly every other library here takes and returns numpy arrays.',
    'pandas': 'Tables of data - loading a CSV, selecting columns, grouping rows.',
    'matplotlib': 'Plotting. Draws the loss curves, scatter plots and decision boundaries.',
    'seaborn': 'Statistical plots on top of matplotlib, with better defaults.',
    'sklearn': 'Classical machine learning: the models, the train/test split, and the scoring metrics.',
    'scipy': 'Scientific computing - optimisation, statistics, distances, sparse matrices.',
    'torch': 'PyTorch. Builds the network, holds the tensors, and works out the gradients.',
    'torchvision': 'Image datasets, pretrained vision models and image transforms for PyTorch.',
    'tensorflow': 'TensorFlow. Builds and trains the network, and works out the gradients.',
    'keras': 'A high-level way to stack layers into a model and train it.',
    'xgboost': 'Gradient-boosted trees - usually the strongest thing to try on table data.',
    'lightgbm': 'Gradient-boosted trees, built to be fast on large datasets.',
    'transformers': 'Pretrained language and vision models, and the tokenisers that feed them.',
    'datasets': 'Loads and streams the datasets that go with the transformers library.',
    'cv2': 'OpenCV. Reading, resizing and transforming images.',
    'PIL': 'Pillow. Opening, converting and saving image files.',
    'skimage': 'Image processing built on numpy arrays.',
    'gym': 'Reinforcement learning environments - the world the agent acts in.',
    'plotly': 'Interactive charts you can hover and zoom.',
    'statsmodels': 'Statistical models and tests, with the coefficient tables to read them.',
    'nltk': 'Classical natural language tools - tokenising, stemming, stopwords.',
    'spacy': 'Industrial natural language pipelines: tokens, entities, dependencies.',
    'joblib': 'Saving a fitted model to disk and loading it back.',
    'tqdm': 'The progress bar around a training loop.',
    # Standard library, where its role in a program like this is worth naming.
    'random': 'Random numbers. Usually seeded here so a run can be repeated.',
    'math': 'Single-number maths - square roots, logs, exponentials.',
    'os': 'Paths, directories and environment variables.',
    'time': 'Timing how long something takes, or pausing.',
    'json': 'Reading and writing JSON.',
    'collections': 'Extra container types - counters, default dicts, deques for replay buffers.',
    'itertools': 'Building and combining iterators without writing the loops by hand.',
    'dataclasses': 'Small classes that only hold data, without the boilerplate.',
    'typing': 'Type hints. They document the code and change nothing at runtime.',
    'csv': 'Reading and writing CSV files.',
    'pickle': 'Saving Python objects to disk. Only ever load a pickle you made yourself.',
    'pathlib': 'Filesystem paths as objects rather than strings.',
    'warnings': 'Silencing the warnings a library emits, or turning them into errors.',
    'logging': 'Progress and diagnostics, with a level you can turn down.',
}

# Used only on Python 3.9 and older, where sys.stdlib_module_names does not
# exist, to split "you must install this" from "this ships with Python".
_STDLIB_FALLBACK = frozenset((
    'random', 'math', 'os', 'sys', 're', 'time', 'json', 'collections',
    'itertools', 'dataclasses', 'typing', 'csv', 'pickle', 'pathlib',
    'warnings', 'logging', 'abc', 'copy', 'functools', 'io', 'string',
    'datetime', 'argparse', 'subprocess', 'threading', 'unittest'))


def _imported_names(code):
    """Top-level module names the code imports, in the order they first appear.

    Parsed rather than pattern-matched: an import inside a function or a
    ``from x.y import z as w`` is still an import, and the words "import numpy"
    inside a docstring are not. A pasted snippet is often a fragment that will
    not parse, so that case falls back to reading the import lines.
    """
    names = []

    def add(name):
        head = str(name or '').split('.')[0]
        if head and head not in names:
            names.append(head)

    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        for line in code.splitlines():
            match = re.match(r'\s*(?:from|import)\s+([A-Za-z_][\w.]*)', line)
            if match:
                add(match.group(1))
        return names

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` names no module, so there is nothing to install.
            if node.level == 0:
                add(node.module)
    return names


def describe_packages(code):
    """Every module a program imports, with what it is and what it is for.

    Returns a list of ``{"name", "pip", "stdlib", "role"}`` with the ones that
    need installing first - those are what stop the program running. Empty when
    nothing is imported.
    """
    stdlib = getattr(sys, 'stdlib_module_names', _STDLIB_FALLBACK)
    described = []
    for name in _imported_names(str(code or '')):
        is_stdlib = name in stdlib
        described.append({
            'name': name,
            # Nothing to install for a module that ships with Python.
            'pip': None if is_stdlib else PIP_NAMES.get(name, name),
            'stdlib': is_stdlib,
            'role': PACKAGE_ROLES.get(
                name,
                'Ships with Python; nothing to install.' if is_stdlib
                else 'A third-party package this program imports.'),
        })
    described.sort(key=lambda pkg: (pkg['stdlib'], pkg['name'].lower()))
    return described


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
