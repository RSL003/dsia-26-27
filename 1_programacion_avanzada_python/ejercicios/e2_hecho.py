from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import numpy as np
import pandas as pd

print("pandas:", pd.__version__)
print("cwd:", Path.cwd())
DATA_DIR = Path(__file__).resolve().parent.parent / "Datos"
print("Datos existe:", DATA_DIR.exists())

serie = pd.Series(["a", "b", "c"])
serie

ts = pd.Series(
	{
		date(2026, 9, 7): 10,
		date(2026, 9, 14): 15,
		date(2026, 9, 21): 15,
	}
)
ts

df_demo = pd.DataFrame(
	data=[
		[date(2026, 9, 7), 1, "a"],
		[date(2026, 9, 14), 2, "b"],
		[date(2026, 9, 21), 3, "c"],
	],
	columns=["timestamp", "integers", "strings"],
)
df_demo

print(df_demo)
