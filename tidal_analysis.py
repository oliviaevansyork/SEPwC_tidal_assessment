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

