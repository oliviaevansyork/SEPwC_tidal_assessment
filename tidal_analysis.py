"""
Tidal analysis
Reads tidal gauge data, calculates tidal constituents and sea-level rise.
"""

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
    data = data.set_index('datetime')
    data.index.name = 'datetime'

    #Replace flag values
    for col in ['Sea Level', 'Residual']:
        data[col] = data[col].replace(
            to_replace=r'^\s*.*[MNT]\s*$',
            value=np.nan,
            regex=True
        )
    #catch standalone flag letters
    data['Sea Level'] = data['Sea Level']. replace(
        to_replace=r'^\s*[MNT]\s*$',
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

    # check data frames have sea level columns before joining
    if 'Sea Level' not in data1.columns or 'Sea Level' not in data2.columns:
        return None

    combined = pd.concat([data1, data2])
    combined = combined.sort_index()
    return combined


def extract_single_year_remove_mean(year, data):
    """Extract data for a single year and subtract the mean sea level."""
    year_data = data[data.index.year == int(year)].copy()
    year_data['Sea Level'] = year_data['Sea Level'] - year_data['Sea Level'].mean()
    return year_data

def extract_section_remove_mean(start, end, data):
    """Extract a data range of data and subtract the mean sea level.
    start and end are strings in YYYYMMDD format.
    """
    start_dt = pd.to_datetime(start, format='%Y%m%d')
    end_dt = pd.to_datetime(end,format='%Y%m%d') + pd.Timedelta(days=1)

    mask = (data.index >= start_dt) & (data.index < end_dt)
    section = data.loc[mask].copy()
    section['Sea Level'] = section['Sea Level'] - section['Sea Level'].mean()
    return section

def tidal_analysis(data, constituents, start_datetime):
    """Calculate tidal amplitudes and phrases using uptide."""

    #uptide data no NaN values
    clean = data.dropna(subset=['Sea Level'])

    tide = uptide.Tides(constituents)
    tide.set_initial_time(start_datetime)

    #idex timestamps timezone-naive: utc so match start_datetime
    tz = pytz.utc
    seconds = np.array(
        [(t.replace(tzinfo=tz) - start_datetime).total_seconds()
         for t in clean.index.to_pydatetime()]
    )

    amp, pha = uptide.harmonic_analysis(tide, clean['Sea Level'].values, seconds)
    return amp, pha

def sea_level_rise(data):
    """calculate sea-level rise using linear regression.
    Returns slope in meters/day and p-value
    """
    clean = data.dropna(subset=['Sea Level'])

    # Convert datetime index to numeric (days since 1970-01-01)
    times = matplotlib.dates.date2num(clean.index.to_pydatetime())

    slope, _, _, p_value, _ = scipy.stats.linregress(
        times,
        clean['Sea Level'].values
    )

    return slope, p_value

def main(args_list=None):
    """Main entry point for the tidal analysis CLI."""

    parser = argparse.ArgumentParser(description="Tidal Analysis Tool")
    parser.add_argument('-v', action='store_true', help='Print output to screen')
    parser.add_argument('directory', type=str, help='directory of tidal data files')
    args = parser.parse_args(args_list)

    #find text files in given directory
    files = sorted(glob.glob(os.path.join(args.directory, '*.txt')))

    #read / join all data
    all_data = None
    for f in files:
        year_data =read_tidal_data(f)
        if all_data is None:
            all_data = year_data
        else:
            all_data = join_data(all_data, year_data)

    #sea level rise
    slope, p_value = sea_level_rise(all_data)

    #Tidal constituents using full dataset
    tz = pytz.timezone("utc")
    start_dt = all_data.index[0].to_pydatetime().replace(tzinfo=tz)
    section = extract_section_remove_mean(
        all_data.index[0].strftime('%Y%m%d'),
        all_data.index[-1].strftime('%Y%m%d'),
        all_data
    )
    amp, _ = tidal_analysis(section, ['M2','S2'], start_dt)

    output = (
        f"M2 amplitude: {amp[0]:.3f} m\n"
        f"S2 amplitude: {amp[1]:.3f} m\n"
        f"Sea level rise: {slope * 365:.6f} m/year\n"
        f"p-value: {p_value:.3f}\n"
    )

    if args.v:
        print(output)
    else:
        outfile = os.path.join(args.directory, 'tidal_analysis_output.txt')
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(output)
