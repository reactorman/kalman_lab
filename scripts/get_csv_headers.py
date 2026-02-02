
import pandas as pd
import os

data_path = os.path.join('measurements', 'compute_20260115_174521.csv')

try:
    df = pd.read_csv(data_path, nrows=0) # Read only the header
    print(','.join(df.columns))
except FileNotFoundError:
    print(f"Error: Data file not found at {data_path}")
except Exception as e:
    print(f"An error occurred: {e}")
