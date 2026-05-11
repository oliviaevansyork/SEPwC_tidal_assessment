"""
Tidal analysis
Reads tidal gauge data, calculates tidal constituents and sea-level rise.
"""

import sys
import os
import argparse
import glob
import datetime

import numpy as np
import pandas as pd
import scipy.stats
import matplotlib.dates
import uptide
import pytz

def read_tidal_data(filename):
    """Read a single tidal data file and return a cleaned DataFrame."""
    
    # Raise an error if the file doesn't exist
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")
    
    #skip rows that arent data
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    skip = 0
    for i, line in enumerate(lines):
        if line.strip() and line.strip()[0].isdigit():
            skip = i
            break

    data = pd.read_csv(
        filename,
        skiprows=skip,
        sep=r'\s+',
        header=None,
        names=['Cycle', 'Date', 'Time', 'Sea Level', 'Residual']
    )

    #combine Date and time into a single datetime column, then set as index
    data['datetime'] = pd.to_datetime(
        data['Date'] + ' ' + data['Time'],
        format='%Y/%m/%d %H:%M:%S'
    )

    #Replace flag values (anything ending in M, N, or T) with NaN
    for col in ['Sea Level', 'Residual']:
        data[col] = data[col].replace(
            to_replace=r' .*[MNT]$',
            value=np.nan,
            regex=True
        )

    #ensure sea level data is stored as a float
    data['Sea Level'] = pd.to_numeric(data['Sea Level'], errors='coerce')

    #keep only needed columns
    data = data [['Time', 'Sea Level']]

    return data
                 


def join_data(data1, data2):
    """ Join two tidal DataFrames and sort by datetime index."""
    pass

def extract_single_year_remove_mean(year, data):
    """Extract data for a single year and subtract the mean sea level."""
    pass

def extract_section_remove_mean(start, end, data):
    """Extract a data range of data and subtract the mean sea level."""
    pass

def tidal_analysis(data, constituents, start_datetime):
    """Calculate tidal amplitudes and phrases using uptide."""
    pass

def sea_level_rise(data):
    """calculate sea-level rise using linear regression."""
    pass

def main(args_list=None):
    """Main entry point for the tidal analysis CLI."""
    pass

if __name__ == "__main__":
    main()