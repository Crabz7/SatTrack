# SatTrack
<img width="1439" height="755" alt="image" src="https://github.com/user-attachments/assets/56d68f97-fda5-4442-b9d3-f6f4d2de25c4" />

SatTrack is a python-based satellite tracking program, that uses [pyorbital](https://github.com/pytroll/pyorbital) for most of it's features. It uses a GUI made with tkinter to make user interaction easier, than had it just been a console. It also uses [cartopy](https://github.com/SciTools/cartopy) and [matplotlib](https://github.com/matplotlib/matplotlib), to create a map with the satellites projected on top.

## Why does this exist?
There are many other programs that do the exact same plus more. They are even more stable.
SatTrack was created for the sole purpose of better interaction with external dish rotors, which isn't actually even possible yet.
Therefore, the purpose of this program is to possibly help someone, who faces the same issue as me.

## Installation
1. Download .zip file under /releases.
2. Unzip. Make sure to keep the file structure intact if you want the example weather.tle file to work out-of-the-box.
3. Done, now you can execute the main.exe in the Scripts folder.

## Setup
**ATTENTION: PLEASE REPLACE THE INCLUDED TLE FILE. IT IS ONLY FOR DEMO PURPOSES AND IT IS HIGHLY RECOMMMENDED TO PROVIDE YOUR OWN UPDATED TLE FILES AS TO AVOID CONFUSION.**
1. Once the program has started for the first time (or when a settings.db file isn't present), the user will be prompted to enter their observing latitude and longitude.
2. .tle files can be placed in the TLEdata folder. Alternatively, the folder which the program references for .tle files can be changed in the program with "Set TLE Folder" under "File" in the top toolbar.

## Usage
### Select satellite
To track a satellite, select it in the left sidebar. Do this by typing the name of the satellite you would like to track in the entry which says "Enter satellite". As you do, suggested satellites, which have been pulled from your .tle files, will show under the entry, and you can click on one, to insert it into the entry. This way you are sure to have matched the satellites name as specified in the .tle file it was pulled from. Now press "Select" and more of the sidebar should reveal itself.

### Plot satellite path
To plot the path of a satellite, input how many hours ahead you would like to plot the path, and press "Plot Path". A red line should then appear on the map, indicating the satellite's future path within the specified time frame.

### Get upcoming satellite passes
To see the upcoming passes of a satellite, specify how many hours ahead you would like to see passes, and the minimum elevation of a pass for it to be included. For this feature, the specified latitude and longitude saved in the "settings.db" file will be used. Then press "Predict" and a table should now pop up containing information about AOS, LOS and MAX EL.

<img width="870" height="420" alt="image" src="https://github.com/user-attachments/assets/94a42d93-645c-45c0-9042-ca1a0c8d6df3" />

### Menubar
At the top of the window, a menubar can be seen containing the following:
- File: Includes TLE options (Set TLE Folder, Inspect TLE) aswell as an "Exit" button.
- Preferences: Includes options to set the observing latitude and longitude.

### Read the map
On the map, the following can be seen:
1. Blue dot: The obsering location.
2. Red dot: Selected satellite's current position.
3. Blue outline: Selected satellite's field of view. Ergo the area where the satellite is over the horizon.
4. Red line: Selected satellite's path.

## Requirements
The main.exe from the releases already has all the requirements bundled, but if you want to run the code with Python, these are the extra's you will need:
1. Python 3.13.5
   - The only verison of Python that has been tested with the program.
2. numpy
   - Currently only there for future expansion.
3. matplotlib
   - Allows for plotting graphs and placing markers etc.
4. pyorbital
   - Does all the important calculations for the satellite position, passes etc.
5. cartopy
   - Used to draw the map and does the math for map projections with matplotlib.

Here are all the imports from main.py listed:
```python
import sqlite3

import time
import warnings
import datetime as dt
from datetime import timedelta
from pathlib import Path

import numpy as np
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import *
from tkinter.messagebox import *
from tkinter.simpledialog import *
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from pyorbital.orbital import Orbital
import cartopy.crs as ccrs
from cartopy.geodesic import Geodesic
from cartopy.feature.nightshade import Nightshade
```
