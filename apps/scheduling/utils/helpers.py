"""
Helper functions và utilities
"""

from datetime import datetime
import pandas as pd
import numpy as np


def json_serial(obj):
    """JSON serializer cho datetime và numpy objects"""
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):  # Bất kỳ datetime-like object nào
        return obj.isoformat()
    elif isinstance(obj, np.integer):  # numpy int types
        return int(obj)
    elif isinstance(obj, np.floating):  # numpy float types
        return float(obj)
    elif isinstance(obj, np.ndarray):  # numpy arrays
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")
