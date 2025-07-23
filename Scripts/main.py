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

# Welcome message
print("---------- Welcome to SatTrack v0! ----------")

# Remove datetime warnings
warnings.filterwarnings("ignore", category=UserWarning)


tracking = False
job = None
timejob= None
projection = ccrs.PlateCarree()
paths = []
fov_artists = []
tle_folder = "../TLEdata/"
active_orbit = None
usrlon = ""
usrlat = ""
now = dt.datetime.now(dt.timezone.utc)
nightshade_obj = None

# Connect/Create SQLite3 database
con = sqlite3.connect("settings.db")
cur = con.cursor()
# Create the preferences data table if it doesn't exist
cur.execute("""CREATE TABLE IF NOT EXISTS preferences(option PRIMARY KEY, value)""")

# Assign preferences variables
def update_preferences():
    global usrlat, usrlon
    con.commit()

    res = cur.execute("SELECT value FROM preferences WHERE option='user_latitude'").fetchone()
    if res and res[0] != "":
        try:
            usrlat = float(res[0])
            print("User Latitude:", usrlat)
        except ValueError:
            usrlat = None

    res = cur.execute("SELECT value FROM preferences WHERE option='user_longitude'").fetchone()
    if res and res[0] != "":
        try:
            usrlon = float(res[0])
            print("User Longitude:", usrlon)
        except ValueError:
            usrlon = None

update_preferences()


class table:
    def __init__(self, root, lst, rows, columns):
        self.tcells = []
        for i in range(rows):
            row_widgets = []
            for j in range(columns):
                e = tk.Entry(root, width=10)
                e.grid(row=i, column=j, padx=1, pady=1)

                value = lst[i][j] if j < len(lst[i]) else ""  # safe fallback
                e.insert(tk.END, value)
                e.config(state="readonly")

                row_widgets.append(e)
            self.tcells.append(row_widgets)

def time():
    global now, timejob, nightshade_obj
    now = dt.datetime.now(dt.timezone.utc)

    # Nightshade
    if nightshade_obj in map_ax.collections:
        nightshade_obj.remove()
    new_nightshade = Nightshade(now, alpha=0.2)
    nightshade_obj = map_ax.add_feature(new_nightshade, zorder=0)


    canvas.draw_idle()
    timejob = root.after(1000, time)

def entry_error(entry, error):
    entry.delete(0, tk.END)
    entry.insert(0, error)
    entry.config(fg="red")

    def clear_error():
        if entry.get() == error:
            entry.delete(0, tk.END)
            entry.config(fg="black")

    entry.bind("<FocusIn>", lambda e: clear_error(), add=True)
    root.after(1, lambda: root.focus_set())


def on_track():
    global tracking, job, active_orbit, sat, paths

    plot_path("clear")

    active_orbit = None

    if not tracking:
        tle_file = ""
        sat = satinput.get()
        if not sat or sat == "Enter satellite":
            return
        sat = sat.upper()
        satinput.delete(0, tk.END)
        satinput.insert(0, sat)
        for item in all_sats:
            if item[0] == sat:
                tle_file = item[1]
        if not tle_file:
            entry_error(satinput, "NOT FOUND")
            return
        orbit = set_tracking(sat, tle_file)
        if orbit != "Fail":
            active_orbit = orbit
            satinput.config(state="disabled")
            tracking = not tracking
            trackbtn.config(text="Unselect")
            prediction_frame.grid()
            track(active_orbit)
    elif tracking:
        trackbtn.config(text="Select")
        satinput.config(state="normal")
        prediction_frame.grid_forget()
        sat_marker.set_data([None], [None])
        sat_text.set_position((999, 999))
        
        for artist in fov_artists:
            artist.remove()
        fov_artists.clear()


        tracking = not tracking
        root.after_cancel(job)


def track(orbit):
    global job

    now = dt.datetime.now(dt.timezone.utc)
    lon, lat, alt = orbit.get_lonlatalt(now)

    satlon.config(text=f"Longitude: {lon: .2f}°")
    satlat.config(text=f"Latitude:  {lat: .2f}°")
    satalt.config(text=f"Altitude:  {alt: .2f} km")

    sat_marker.set_data([round(lon, 2)], [round(lat, 2)])
    sat_text.set_text(sat)
    sat_text.set_position((round(lon, 2), round(lat, 2) - 10))

    draw_fov(map_ax, lat, lon, alt)

    canvas.draw()
    job = root.after(500, lambda: track(orbit))


def draw_fov(ax, sat_lat, sat_lon, alt_km):
    global fov_artists

    R = 6371  # Earth radius (km)
    horizon_angle = np.degrees(np.arccos(R / (R + alt_km)))  # Horizon angle
    radius_km = R * np.radians(horizon_angle)  # Convert angle to approx km

    gd = Geodesic()
    circle = gd.circle(lon=sat_lon, lat=sat_lat, radius=radius_km * 1000, n_samples=100)

    lons, lats = zip(*circle)

    if fov_artists:
        for artist in fov_artists:
            artist.remove()
        fov_artists.clear()

    polygons = split_polygon_at_dateline(lons, lats)

    for poly in polygons:
        plon, plat = zip(*poly)
        fov_artists.extend(ax.plot(plon, plat, transform=ccrs.PlateCarree(), color='blue', alpha=0.6))


def split_polygon_at_dateline(lons, lats):
    polygons = []
    current_poly = [(lons[0], lats[0])]

    for i in range(1, len(lons)):
        prev_lon = lons[i - 1]
        curr_lon = lons[i]
        if abs(curr_lon - prev_lon) > 180:
            polygons.append(current_poly)
            current_poly = []
        current_poly.append((curr_lon, lats[i]))

    polygons.append(current_poly)
    return polygons


def plot_path(option):
    global projection, sat, paths, path, now
    resolution = 2
    
    if option != "clear":
        if not active_orbit: 
            entry_error(pathinput, "No satellite")
            return

        lonslats = []

        now = dt.datetime.now(dt.timezone.utc)
        try:
            minutes = int(pathinput.get()) * 60 * resolution
        except ValueError:
            entry_error(pathinput, "Invalid time")
            return

    for line in paths:
        line.remove()
    paths.clear()
    canvas.draw()
    if option == "clear":
        return

    for x in range(0, minutes, 2):
        lon, lat, alt = active_orbit.get_lonlatalt(now + timedelta(minutes=x / resolution))
        lonslats.append((lon, lat))

    lon, lat = zip(*lonslats)

    segments = []
    current_segment = [lonslats[0]]

    for i in range(1, len(lonslats)):
        lon_prev, lat_prev = lonslats[i - 1]
        lon_curr, lat_curr = lonslats[i]

        if abs(lon_curr - lon_prev) > 180:
            segments.append(current_segment)
            current_segment = []

        current_segment.append(lonslats[i])

    segments.append(current_segment)

    for segment in segments:
        lons, lats = zip(*segment)
        path, = map_ax.plot(lons, lats, color="red", linewidth=1, transform=projection)
        paths.append(path)

    canvas.draw_idle()

    newnow = dt.datetime.now(dt.timezone.utc)
    comptime = newnow - now
    print(f"Computed {minutes / 60 * resolution} hours of {sat}'s path in {comptime.total_seconds():.2f} seconds.")


def add_placeholder(entry, placeholder):
    entry.insert(0, placeholder)
    entry.config(fg='grey')

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg='black')

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg='grey')

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def tle_scan(directory):
    folder = Path(directory)
    tle_sats = []
    files = list(folder.glob("*.tle"))
    print(f"Found {len(files)} .tle files:")
    for f in files:
        print(f)
    for tle_file in folder.glob("*.tle"):
        with tle_file.open() as f:
            lines = f.readlines()
        for i in range(0, len(lines), 3):
            tle_sats.append((lines[i].strip(), str(tle_file)))
    return tle_sats


all_sats = tle_scan(tle_folder)

def set_tracking(name, tle_file):
    try:
        orbit = Orbital(name, tle_file=tle_file)
        return orbit
    except Exception:
        return "Fail"

def update_preferences():
    global usrlat, usrlon
    con.commit()

    res = cur.execute("SELECT value FROM preferences WHERE option='user_latitude'").fetchone()
    if res and res[0] != "":
        try:
            usrlat = float(res[0])
            print("User Latitude:", usrlat)
        except ValueError:
            usrlat = None

    res = cur.execute("SELECT value FROM preferences WHERE option='user_longitude'").fetchone()
    if res and res[0] != "":
        try:
            usrlon = float(res[0])
            print("User Longitude:", usrlon)
        except ValueError:
            usrlon = None

def preferences(pref):
    global usrlon, usrlat

    if pref == "usrcoords":
        # Ask for lat
        lat = askstring("Latitude", "Enter latitude:")
        if lat not in (None, "", ''):
            try:
                usrlat = float(lat)
                cur.execute("""
                    INSERT OR IGNORE INTO preferences (option, value) VALUES (?, ?)""",
                        ('user_latitude', str(usrlat)))
                cur.execute("UPDATE preferences SET value = ? WHERE option = 'user_latitude'", (str(usrlat),))
            except ValueError:
                showerror("Error", "Wrong input. Please only use numbers.")
                return
        
        # Ask for lon
        lon = askstring("Longitude", "Enter longitude:")
        if lon not in (None, "", ''):
            try:
                usrlon = float(lon)
                cur.execute("""
                    INSERT OR IGNORE INTO preferences (option, value) VALUES (?, ?)""",
                        ('user_longitude', str(usrlon)))
                cur.execute("UPDATE preferences SET value = ? WHERE option = 'user_longitude'", (str(usrlon),))
            except ValueError:
                showerror("Error", "Wrong input. Please only use numbers.")
                return

        con.commit()
        
        try:
            loc_marker.set_data([usrlon], [usrlat])
        except Exception:
            pass

def set_tle_folder():
    global all_sats, tle_folder, tracking
    if tracking:
        showerror(master=root, message="Cannot set TLE folder while satellite is selected. Unselect satellite, and try again.")
        return
    try:
        tle_folder = askdirectory()
        all_sats = []
        all_sats = tle_scan(tle_folder)
    except Exception:
        tle_folder = "../TLEdata/"
        all_sats = tle_scan(tle_folder)

def get_passes():
    if not active_orbit:
        return 
    
    try:
        hours = int(hrse.get())
        lon = float(usrlon)
        lat = float(usrlat)
        tolerance = 1
        min_el = int(mine.get())
    except Exception:
        showerror("Error", "Invalid input. Please only enter numbers without decimals, letters or other special characters.")
        return
    now = dt.datetime.now(dt.timezone.utc)

    passes = active_orbit.get_next_passes(now, hours, lon, lat, 0, tolerance, min_el)

    if len(passes) < 1:
        print("No passes found within the specified timeframe.")
        showerror("Error", "No passes found within the specified timeframe.")
        return
    else:
        print("Found passes within the specified timeframe, calculating...")

    passes_table = tk.Toplevel(prediction_frame)
    passes_table.attributes("-type", "dialog")

    lst = [('DATE', 'AOS TIME', 'AOS AZ', 'LOS TIME', 'LOS AZ', 'EL TIME', 'EL')]

    for satpass in passes:
        if len(satpass) < 3:
                continue
        
        # Data from pyOrbital command
        pass_date = satpass[0].strftime("%Y-%m-%d")
        aos = satpass[0].strftime("%H:%M:%S")
        los = satpass[1].strftime("%H:%M:%S")
        el_time = satpass[2].strftime("%H:%M:%S")

        # Other data
        aos_az, aos_el = active_orbit.get_observer_look(satpass[0], lon, lat, 0)
        los_az, los_el = active_orbit.get_observer_look(satpass[1], lon, lat, 0)
        max_az, max_el = active_orbit.get_observer_look(satpass[2], lon, lat, 0)

        lst.append((pass_date, aos, f"{aos_az: .1f}°", los, f"{los_az: .1f}°", el_time, f"{max_el: .1f}°"))

    rows = int(len(lst))
    columns = int(len(list(lst[1])))

    print("Calculated", rows - 1, "passes within the specified timeframe.")

    pass_table = table(passes_table, lst, rows, columns)
    return len(passes)

def inspect_tle():
    sats = tk.Toplevel() 
    sats.attributes("-type", "dialog")

    sats_header = tk.Label(sats, text="Currently loaded satellite list gathered from TLE files:")
    sats_header.grid(row=0, column=0)

    sattrim = []
    i = 0
    for sat in all_sats:
        satnm = list(all_sats[i])
        sattrim.append(satnm[0])

        i += 1
    
    listcontent = tk.StringVar()
    listcontent.set(sattrim)

    satlistbox = tk.Listbox(sats, listvariable=listcontent)
    satlistbox.grid(row=1, column=0, sticky="ew")

def unfocus():
    dummy.focus_set()


def close():
    print("Closing...")
    plt.close('all')
    root.destroy()


# -----------------Define window-----------------
root = tk.Tk()
root.protocol('WM_DELETE_WINDOW', close)
root.title("Sat Tracker")
root.attributes("-type", "dialog")
root.tk.call('tk', 'scaling', 2.0)

for i in range(2):
    if i != 0:
        root.grid_rowconfigure(i, weight=0)
        root.grid_columnconfigure(i, weight=1)
root.grid_columnconfigure(0, weight=0)
root.grid_rowconfigure(0, weight=1)

# -----------------Menus-----------------
menu = tk.Menu(root)

filemenu = tk.Menu(menu, tearoff=0, bd=1)
tlemenu = tk.Menu(filemenu, tearoff=0)
prefmenu = tk.Menu(menu, tearoff=0)

tlemenu.add_command(label="Set TLE Folder", command=set_tle_folder)
tlemenu.add_command(label="Inspect TLE", command=inspect_tle)
filemenu.add_cascade(label="TLE", menu=tlemenu)
prefmenu.add_command(label="User Location", command=lambda:preferences("usrcoords"))

menu.add_cascade(label="File", menu=filemenu)

menu.add_cascade(label="Preferences", menu=prefmenu)

featuremenu = tk.Menu(menu, tearoff=0)

filemenu.add_separator()
filemenu.add_command(label="Exit", command=close)

root.config(menu=menu)

bdstick = "new"
bdwidth = 1
siderlf = 'flat'
sidepad = 5
padspacing = 5

# --------------------Sidebar--------------------
sidebar = tk.Frame(root, relief='sunken', bd=2)
sidebar.grid(row=0, column=0, sticky=bdstick, padx=sidepad)
for i in range(4):
    sidebar.grid_rowconfigure(i, weight=1)

# -----------------Tracking-----------------
tracking_frame = tk.Frame(sidebar, relief=siderlf, borderwidth=bdwidth)
tracking_frame.grid(row=0, column=0, sticky=bdstick, pady=padspacing, ipady=5, ipadx=5)
trkstick = "w"

for i in range(4):
    tracking_frame.grid_columnconfigure(i, weight=1)

tracking_header = tk.Label(tracking_frame, text="Satellite")
tracking_header.grid(row=0, column=0, columnspan=2)

def on_select(event):
    widget = event.widget
    selection = widget.curselection()
    if selection:
        index = selection[0]
        value = widget.get(index)
        print("Selected:", value)
        satinput.delete(0, tk.END)
        satinput.insert(0, value)

search_scroll = tk.Scrollbar(tracking_frame, orient="vertical")
search_list = tk.Listbox(tracking_frame, width=14, yscrollcommand=search_scroll.set)
search_scroll.config(command=search_list.yview)

search_list.grid(row=2, column=0, sticky="nsew")
search_list.grid_remove()
search_scroll.grid(row=2, column=1, sticky="nsw")
search_list.bind("<<ListboxSelect>>", on_select)

MAX_VISIBLE_ROWS = 6  # max rows listbox can grow

def update_listbox(items):
    search_list.delete(0, tk.END)
    for item in items:
        search_list.insert(tk.END, item)

    visible_rows = min(len(items), MAX_VISIBLE_ROWS)
    search_list.config(height=visible_rows)

    if visible_rows >= len(items):
        search_scroll.grid_remove()
    else:
        search_scroll.grid()

def on_type(*args):
    global all_sats
    satnamelist = []

    for sat in all_sats:
        satnamelist.append(sat[0])

    search_term = current_search.get().lower()
    filtered = [s for s in satnamelist if search_term in s.lower()]
    update_listbox(filtered)

current_search = tk.StringVar()
current_search.trace_add("write", on_type)
satinput = tk.Entry(tracking_frame, width=14, textvariable=current_search)
satinput.grid(row=1, column=0, sticky=trkstick, padx=(0, 5))
add_placeholder(satinput, "Enter satellite")

def show_list(event):
    search_list.grid()
def hide_list(event):
    search_list.grid_remove()

satinput.bind("<FocusIn>", show_list, add="+")
satinput.bind("<FocusOut>", hide_list, add="+")


trackbtn = tk.Button(tracking_frame, text="Select", command=on_track)
trackbtn.grid(row=1, column=1, sticky="e", pady=5)


sepA = ttk.Separator(sidebar, orient='horizontal')
sepA.grid(row=1, column=0, sticky="ew")

# ---------------Prediction--------------

prediction_frame = tk.Frame(sidebar, relief=siderlf, borderwidth=bdwidth)
prediction_frame.grid(row=2, column=0, sticky=bdstick, pady=padspacing)
prediction_frame.grid_forget()
prdstick = "w"

for i in range(4):
    prediction_frame.grid_columnconfigure(i, weight=1)

prediction_header = tk.Label(prediction_frame, text="Prediction")
prediction_header.grid(row=0, column=0, columnspan=2)

path_header = tk.Label(prediction_frame, text="Satellite Path:")
path_header.grid(row=1, column=0, columnspan=2, sticky="w")

pathinput = tk.Entry(prediction_frame, width=14)
pathinput.grid(row=2, column=0, sticky=prdstick, padx=(0, 2))
add_placeholder(pathinput, "Hours")

pathbtn = tk.Button(prediction_frame, text="Plot path", command=lambda: plot_path("nope"))
pathbtn.grid(row=2, column=1, sticky="ew", padx=3)

passes_frame = tk.Frame(prediction_frame)
passes_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")

pass_header = tk.Label(passes_frame, text="Future Passes:")
pass_header.grid(row=0, column=0, columnspan=2, sticky="w")

hrslbl = tk.Label(passes_frame, text="Hours ahead:").grid(row=3, column=0, sticky="w")
hrse = tk.Entry(passes_frame, width=10)
hrse.grid(row=3, column=1, sticky="e")
hrse.insert(0, 96)

minellbl = tk.Label(passes_frame, text="Min. elevation:").grid(row=4, column=0, sticky="w")
mine = tk.Entry(passes_frame, width=10)
mine.grid(row=4, column=1, sticky="e")
mine.insert(0, 10)

prdctbtn = tk.Button(passes_frame, text="Predict", command=get_passes)
prdctbtn.grid(row=6, column=0, columnspan=2)

pass_frame = tk.Frame(passes_frame, bg="black")



info_panel = tk.Frame(root, relief=siderlf, borderwidth=bdwidth)
info_panel.grid(row=1, column=1, sticky=bdstick, pady=padspacing)

satlon = tk.Label(info_panel, text="Longitude: -")
satlon.grid(row=0, column=0, sticky="nw")

satlat = tk.Label(info_panel, text="Latitude: -")
satlat.grid(row=1, column=0, sticky="nw")

satalt = tk.Label(info_panel, text="Altitude: -")
satalt.grid(row=2, column=0, sticky="nw")

map_fig = plt.figure()
map_ax = plt.subplot(1, 1, 1, projection=projection)
map_ax.stock_img()
map_ax.coastlines(linewidth=0.5)
map_fig.set_size_inches(6, 3)
map_fig.patch.set_facecolor("#d9d9d9")
map_fig.subplots_adjust(left=0.01, right=0.95, top=0.98, bottom=0.05)
nightshade = Nightshade(now, alpha=0.2)
nightshade_obj = map_ax.add_feature(nightshade)


sat_marker, = map_ax.plot([None], [None], marker="o", color="red", markersize=4, transform=projection)
sat_text = plt.text(0, 0, "", color="black", fontsize=10, weight='bold', ha='center', va='center', transform=projection)

canvas = FigureCanvasTkAgg(map_fig, master=root)
canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew")

dummy = tk.Label(root)
dummy.pack_forget()

root.geometry("")
root.update_idletasks()
root.update()

canvas.draw()

print("Found", len(all_sats), "satellites in .tle file(s)")

try:
    loc_marker, = map_ax.plot([float(usrlon)], [float(usrlat)], marker="o", color="blue", markersize=4, transform=projection)
except Exception:
    preferences("usrcoords")
    loc_marker, = map_ax.plot([float(usrlon)], [float(usrlat)], marker="o", color="blue", markersize=4, transform=projection)

time()

root.mainloop()
