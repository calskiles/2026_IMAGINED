"""
Import all required packages and set global variables for file directories.
"""

# GENERAL
import os
import geopandas as gpd
import pandas as pd
import numpy as np

# NETWORKS
import networkx as nx
import osmnx as ox

# PLOTTING
import matplotlib
import matplotlib.pyplot as plt
import plotly

# GLOBAL PATHS
BASE_DIR = os.path.dirname(__file__)
# input directory
INPUT_DIR = os.path.join(BASE_DIR, 'input')
# input subdirectories
DEMAND_DIR = os.path.join(INPUT_DIR, 'demand')
GIS_DIR = os.path.join(INPUT_DIR, 'gis')
PERFORMANCE_DIR = os.path.join(INPUT_DIR, 'performance_metrics')
REGION_DIR = os.path.join(INPUT_DIR, 'region')
