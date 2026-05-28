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

    # Header lines start with letters; find first line starting with a digit
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

    # Combine Date and time into a single datetime column, then set as index
    data['datetime'] = pd.to_datetime(
        data['Date'] + ' ' + data['Time'],
        format='%Y/%m/%d %H:%M:%S'
    )
    data = data.set_index('datetime')
    data.index.name = 'datetime'

    # Replace flag values
    for col in ['Sea Level', 'Residual']:
        data[col] = data[col].replace(
            to_replace=r'^\s*.*[MNT]\s*$',
            value=np.nan,
            regex=True
        )
    # Catch standalone flag letters
    data['Sea Level'] = data['Sea Level'].replace(
        to_replace=r'^\s*[MNT]\s*$',
        value=np.nan,
        regex=True
    )

    # Ensure sea level data is stored as a float
    data['Sea Level'] = pd.to_numeric(data['Sea Level'], errors='coerce')

    # Keep only needed columns
    data = data[['Time', 'Sea Level']]

    return data


def join_data(data1, data2):
    """Join two tidal DataFrames and sort by datetime index."""

    # Check data frames have sea level columns before joining
    if 'Sea Level' not in data1.columns or 'Sea Level' not in data2.columns:
        return None

    combined = pd.concat([data1, data2])
    # Sort ensures chronological order regardless of which year passed first
    combined = combined.sort_index()
    return combined


def extract_single_year_remove_mean(year, data):
    """Extract data for a single year and subtract the mean sea level."""
    year_data = data[data.index.year == int(year)].copy()
    year_data['Sea Level'] = year_data['Sea Level'] - year_data['Sea Level'].mean()
    return year_data


def extract_section_remove_mean(start, end, data):
    """
    Extract a data range of data and subtract the mean sea level.
    start and end are strings in YYYYMMDD format.
    """
    start_dt = pd.to_datetime(start, format='%Y%m%d')
    # Add one day to make end date inclusive of the full final day
    end_dt = pd.to_datetime(end, format='%Y%m%d') + pd.Timedelta(days=1)

    mask = (data.index >= start_dt) & (data.index < end_dt)
    section = data.loc[mask].copy()
    section['Sea Level'] = section['Sea Level'] - section['Sea Level'].mean()
    return section


def tidal_analysis(data, constituents, start_datetime):
    """Calculate tidal amplitudes and phases using uptide."""

    # Uptide requires clean data - drop NaN rows before harmonic analysis
    clean = data.dropna(subset=['Sea Level'])

    tide = uptide.Tides(constituents)
    tide.set_initial_time(start_datetime)

    # Index timestamps are timezone-naive: add UTC to match start_datetime
    tz = pytz.utc
    seconds = np.array(
        [(t.replace(tzinfo=tz) - start_datetime).total_seconds()
         for t in clean.index.to_pydatetime()]
    )

    amp, pha = uptide.harmonic_analysis(tide, clean['Sea Level'].values, seconds)
    return amp, pha


def sea_level_rise(data):
    """
    Calculate sea-level rise using linear regression.
    Returns slope in meters/day and p-value
    """
    clean = data.dropna(subset=['Sea Level'])

    # Convert datetime index to float (days since 1970-01-01)
    times = matplotlib.dates.date2num(clean.index.to_pydatetime())

    slope, _, _, p_value, _ = scipy.stats.linregress(
        times,
        clean['Sea Level'].values
    )

    return slope, p_value


def get_longest_contiguous_data(data):
    """
    Find longest contiguous period with no missing sea level data.
    Returns start and end datetime of longest gap-free stretch
    """
    # Boolean series: True where sea level is valid
    valid = data['Sea Level'].notna()

    longest_start = None
    longest_end = None
    longest_length = 0
    current_start = None
    current_length = 0

    for timestamp, is_valid in valid.items():
        if is_valid:
            # Start new stretch if not already in one
            if current_start is None:
                current_start = timestamp
            current_length += 1
        else:
            # End of a stretch - check if longest so far
            if current_length > longest_length:
                longest_length = current_length
                longest_start = current_start
                longest_end = data.index[data.index.get_loc(timestamp) - 1]
            current_start = None
            current_length = 0

    # Check final stretch in case data ends without NaN
    if current_length > longest_length:
        longest_start = current_start
        longest_end = data.index[-1]

    return longest_start, longest_end


def main(args_list=None):
    """Main entry point for the tidal analysis CLI."""

    parser = argparse.ArgumentParser(description="Tidal Analysis Tool")
    parser.add_argument('-v', '--verbose', action='store_true', help='Print output to screen')
    parser.add_argument('directory', type=str, help='directory of tidal data files')
    args = parser.parse_args(args_list)

    # Find text files in given directory
    files = sorted(glob.glob(os.path.join(args.directory, '[0-9]*.txt')))

    # Read / join all data
    all_data = None
    for f in files:
        year_data = read_tidal_data(f)
        if all_data is None:
            all_data = year_data
        else:
            all_data = join_data(all_data, year_data)

    # Sea level rise
    slope, p_value = sea_level_rise(all_data)

    # Tidal constituents using full dataset
    start_dt = datetime.datetime(
        all_data.index[0].year,
        all_data.index[0].month,
        all_data.index[0].day,
        all_data.index[0].hour,
        all_data.index[0].minute,
        all_data.index[0].second,
        tzinfo=pytz.utc
    )
    section = extract_section_remove_mean(
        all_data.index[0].strftime('%Y%m%d'),
        all_data.index[-1].strftime('%Y%m%d'),
        all_data
    )
    amp, _ = tidal_analysis(section, ['M2','S2'], start_dt)

    # Find longest contiguous period of valid data
    contiguous = get_longest_contiguous_data(all_data)

    output = (
        f"M2 amplitude: {amp[0]:.3f} m\n"
        f"S2 amplitude: {amp[1]:.3f} m\n"
        f"Sea level rise: {slope * 365:.6f} m/year\n"
        f"p-value: {p_value:.3f}\n"
        f"Longest contiguous period: {contiguous[0]} to {contiguous[1]}\n"
    )

    if args.verbose:
        print(output, flush=True)
    else:
        outfile = os.path.join(args.directory, 'tidal_analysis_output.txt')
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(output)

if __name__ == '__main__':
    main()
