#!/bin/env python
"""
GUI interface to generating clock corrections from x-corr results.
"""

import os

try:
    import tkinter as tk
except ImportError:
    import Tkinter as tk

import tkFileDialog

import matplotlib
matplotlib.use("TkAgg")
# import matplotlib.backends.tkagg as tkagg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# from matplotlib.figure import Figure

from seismic.ASDFdatabase import FederatedASDFDataSet
from seismic.xcorqc.xcorr_station_clock_analysis import (plot_xcorr_file_clock_analysis,
                                                         read_correlator_config,
                                                         batch_process_xcorr)


dataset = "/g/data/ha3/Passive/SHARED_DATA/Index/asdf_files.txt"


class GpsClockCorrectionApp(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.nc_file = tk.StringVar(self)
        self.pack()
        self._last_dir = None
        self.fds = FederatedASDFDataSet.FederatedASDFDataSet(dataset)
        self.current_step = 0
        self.station_code = ''
        self.time_window = tk.IntVar(self, value=300)
        self.snr_threshold = tk.IntVar(self, value=6)
        self.pearson_cutoff_factor = 0.5
        self.xcorr_ca = None
        self.xcorr_fig = None
        self.fig_canv = None
        self.cluster_fig = None
        self.cluster_fig_canv = None
        self.cluster_coeff0 = tk.DoubleVar(self, value=1.0)
        self.cluster_coeff1 = tk.DoubleVar(self, value=1.0)
        self.cluster_coeff2 = tk.DoubleVar(self, value=0.0)
        self.cluster_ids = None

        self._createStep0Widgets()

    def _createStep0Widgets(self):
        self.ROOT_FRAME_0 = tk.Frame(self)
        self.ROOT_FRAME_0.pack(fill=tk.BOTH, expand=1)

        self.UPPER_FRAME_0 = tk.LabelFrame(self.ROOT_FRAME_0, text="Input file selection", borderwidth=2)
        self.UPPER_FRAME_0.pack(anchor=tk.N, side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.STN_CODE_LABEL = tk.Label(self.ROOT_FRAME_0, text="Station code: ", font=8)
        self.STN_CODE_LABEL.pack(side=tk.TOP, fill=tk.X, padx=2, pady=8)

        self.LOWER_FRAME_0 = tk.Frame(self.ROOT_FRAME_0)
        self.LOWER_FRAME_0.pack(anchor=tk.S, side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)

        self.NC_FILE_LABEL = tk.Label(self.UPPER_FRAME_0, text="Cross-correlation file:")
        self.NC_FILE_LABEL.pack(anchor=tk.E, side=tk.LEFT, pady=2)

        self.NC_FILE_ENTRY = tk.Entry(self.UPPER_FRAME_0)
        self.NC_FILE_ENTRY['width'] = 64
        self.NC_FILE_ENTRY.pack(anchor=tk.W, padx=5, pady=2, side=tk.LEFT)
        self.NC_FILE_ENTRY['textvariable'] = self.nc_file

        self.OPEN = tk.Button(self.LOWER_FRAME_0)
        self.OPEN['text'] = "Open..."
        self.OPEN['command'] = self._openNcFile
        self.OPEN.pack(anchor=tk.SW, side=tk.LEFT)

        self.NEXT = tk.Button(self.LOWER_FRAME_0)
        self.NEXT['text'] = "Next..."
        self.NEXT['state'] = tk.DISABLED
        self.NEXT['command'] = self._gotoStep1
        self.NEXT.pack(anchor=tk.SW, side=tk.LEFT)
        self.nc_file.trace_variable('w', self._updateNextButton)

        self.QUIT = tk.Button(self.LOWER_FRAME_0)
        self.QUIT['text'] = "Quit"
        self.QUIT['command'] = self._quitApp
        self.QUIT.pack(anchor=tk.SE, side=tk.RIGHT)

    def _quitApp(self):
        self._destroyFigures()
        self.quit()

    def _extractCodeFromFilename(self, src_file):
        _, basename = os.path.split(src_file)
        _, file_type = os.path.splitext(src_file)
        name_parts = basename.split('.')
        netcode = name_parts[0]
        statcode = name_parts[1]
        full_code = '.'.join([netcode, statcode])
        return full_code

    def _updateNextButton(self, _1, _2, _3):
        nc_file_value = self.nc_file.get()
        nc_file_valid = bool(nc_file_value) and os.path.exists(nc_file_value)
        self.NEXT['state'] = tk.NORMAL if nc_file_valid else tk.DISABLED
        if nc_file_valid:
            self.station_code= self._extractCodeFromFilename(nc_file_value)
        else:
            self.station_code = ''
        self.STN_CODE_LABEL['text'] = "Station code: " + self.station_code

    def _openNcFile(self):
        initial_dir = '/g/data/ha3/Passive/SHARED_DATA/GPS_Clock/xcorr' if self._last_dir is None else self._last_dir
        file_name = tkFileDialog.askopenfilename(initialdir=initial_dir,
                                                 title='Select .nc file to analyze',
                                                 filetypes=(("nc files", "*.nc"), ("all files", "*")))
        if file_name:
            self._last_dir = os.path.split(file_name)[0]
            self.nc_file.set(file_name)

    def _gotoStep1(self):
        if self.current_step == 0:
            # for child in self.TOP_PANE_0.winfo_children():
            #     self.child.destroy()
            self.ROOT_FRAME_0.destroy()
            self.ROOT_FRAME_0 = None
            self._createStep1Widgets()

    def _createStep1Widgets(self):
        self.current_step = 1
        self.ROOT_FRAME_1 = tk.Frame(self)
        self.ROOT_FRAME_1.pack(fill=tk.BOTH, expand=1)

        self.LEFT_FRAME_1 = tk.LabelFrame(self.ROOT_FRAME_1, width=800)
        self.LEFT_FRAME_1.pack(anchor=tk.NW, side=tk.LEFT, fill=tk.X)

        self.STN_CODE_LABEL = tk.Label(self.LEFT_FRAME_1, text="Station code: " + self.station_code, font=8)
        self.STN_CODE_LABEL.pack(anchor=tk.W, side=tk.TOP)

        self.TIME_WINDOW_FRAME = tk.LabelFrame(self.LEFT_FRAME_1, borderwidth=2)
        self.TIME_WINDOW_FRAME.pack(anchor=tk.W, side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.TIME_WINDOW_LABEL = tk.Label(self.TIME_WINDOW_FRAME, text="Time window (s)")
        self.TIME_WINDOW_LABEL.pack(anchor=tk.NW, side=tk.TOP)
        self.TIME_WINDOW_ENTRY = tk.Scale(self.TIME_WINDOW_FRAME, from_=30, to=1800, resolution=10,
                                          orient=tk.HORIZONTAL, length=500)
        self.TIME_WINDOW_ENTRY.set(self.time_window.get())
        self.TIME_WINDOW_ENTRY['variable'] = self.time_window
        self.TIME_WINDOW_ENTRY['command'] = self._enableRefresh
        self.TIME_WINDOW_ENTRY.pack(anchor=tk.SW, side=tk.BOTTOM, fill=tk.X)

        self.SNR_FRAME = tk.LabelFrame(self.LEFT_FRAME_1, borderwidth=2)
        self.SNR_FRAME.pack(anchor=tk.W, side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.SNR_LABEL = tk.Label(self.SNR_FRAME, text="SNR")
        self.SNR_LABEL.pack(anchor=tk.NW, side=tk.TOP)
        self.SNR_ENTRY = tk.Scale(self.SNR_FRAME, from_=0, to=100, resolution=1, orient=tk.HORIZONTAL, length=500)
        self.SNR_ENTRY.set(self.snr_threshold.get())
        self.SNR_ENTRY['variable'] = self.snr_threshold
        self.SNR_ENTRY['command'] = self._enableRefresh
        self.SNR_ENTRY.pack(anchor=tk.SW, side=tk.BOTTOM, fill=tk.X)

        self.RIGHT_FIGURE_CANVAS_1 = tk.Canvas(self.ROOT_FRAME_1)
        self.RIGHT_FIGURE_CANVAS_1.pack(anchor=tk.NE, side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.REFRESH = tk.Button(self.LEFT_FRAME_1)
        self.REFRESH['text'] = "Refresh"
        self.REFRESH['state'] = tk.DISABLED
        self.REFRESH['command'] = self._updateStep1Canvas
        self.REFRESH.pack(anchor=tk.NW, side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.NEXT = tk.Button(self.LEFT_FRAME_1)
        self.NEXT['text'] = "Save and Next..."
        self.NEXT['command'] = self._gotoStep2
        self.NEXT.pack(anchor=tk.NW, side=tk.TOP, fill=tk.X, padx=2, pady=2)

        self.QUIT = tk.Button(self.LEFT_FRAME_1)
        self.QUIT['text'] = "Quit"
        self.QUIT['command'] = self._quitApp
        self.QUIT.pack(anchor=tk.SW, side=tk.BOTTOM, fill=tk.X, padx=2, pady=16)

        self.xcorr_settings, self.xcorr_title_tag = read_correlator_config(self.nc_file.get())
        self._updateStep1Canvas()

    def _enableRefresh(self, _new_val):
        self.REFRESH['state'] = tk.NORMAL

    def _destroyFigures(self):
        if self.xcorr_fig is not None:
            self.xcorr_fig.clear()
            self.xcorr_fig = None
        if self.fig_canv is not None:
            self.fig_canv.get_tk_widget().destroy()
            self.fig_canv = None
        if self.cluster_fig is not None:
            self.cluster_fig.clear()
            self.cluster_fig = None
        if self.cluster_fig_canv is not None:
            self.cluster_fig_canv.get_tk_widget().destroy()
            self.cluster_fig_canv = None

    def _updateStep1Canvas(self):
        self.REFRESH['state'] = tk.DISABLED
        self.NEXT['state'] = tk.DISABLED
        self._destroyFigures()
        self.RIGHT_FIGURE_CANVAS_1.delete(tk.ALL)
        self.xcorr_ca, self.xcorr_fig = \
            plot_xcorr_file_clock_analysis(self.nc_file.get(), self.fds, self.time_window.get(),
                                           self.snr_threshold.get(), self.pearson_cutoff_factor, show=False,
                                           title_tag=self.xcorr_title_tag, settings=self.xcorr_settings)
        self.fig_canv = FigureCanvasTkAgg(self.xcorr_fig, master=self.RIGHT_FIGURE_CANVAS_1)
        self.fig_canv.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.RIGHT_FIGURE_CANVAS_1.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.NEXT['state'] = tk.NORMAL
        self.update()

    def _gotoStep2(self):
        if self.current_step == 1:
            self.NEXT['state'] = tk.DISABLED

            self._destroyFigures()

            self.RIGHT_FIGURE_CANVAS_1.delete(tk.ALL)
            self.ROOT_FRAME_1.destroy()
            self.ROOT_FRAME_1 = None
            self.update()

            info_label = tk.Label(self, text="Saving plot to graphical file...")
            info_label.pack()
            self.update()

            # Generate PNG file for the .nc file using the current settings.
            batch_process_xcorr([self.nc_file.get()], self.fds, self.time_window.get(), self.snr_threshold.get(),
                                pearson_cutoff_factor=self.pearson_cutoff_factor, save_plots=True, force_save=True)

            info_label.destroy()

            self._createStep2Widgets()

    def _createStep2Widgets(self):
        self.current_step = 2

        assert self.xcorr_ca is not None

        self.ROOT_FRAME_2 = tk.Frame(self)
        self.ROOT_FRAME_2.pack(fill=tk.BOTH, expand=1)

        self.UPPER_FRAME_2 = tk.LabelFrame(self.ROOT_FRAME_2, text="Station code: " + self.station_code)
        self.UPPER_FRAME_2.pack(anchor=tk.N, side=tk.TOP)

        self.COEFF_WIDGETS_FRAME_2 = tk.Frame(self.UPPER_FRAME_2)
        self.COEFF_WIDGETS_FRAME_2.pack(anchor=tk.NW, side=tk.TOP, padx=2, pady=2)

        self.COEFF_WIDGETS_LABEL = tk.Label(self.COEFF_WIDGETS_FRAME_2, font=8,
                                            text="Tune coefficients to optimize clustering and filtering of outliers")
        self.COEFF_WIDGETS_LABEL.pack(anchor=tk.W, side=tk.TOP, pady=2)

        self.COEFF0_LABEL = tk.LabelFrame(self.COEFF_WIDGETS_FRAME_2, text="Coefficient 0 (x-separation)")
        self.COEFF0_LABEL.pack(anchor=tk.W, side=tk.LEFT, padx=2)
        self.COEFF0_SPINBOX = tk.Spinbox(self.COEFF0_LABEL, from_=0.0, to=100.0, increment=0.1,
                                         textvariable=self.cluster_coeff0)
        self.COEFF0_SPINBOX.pack(padx=2, pady=2)

        self.COEFF1_LABEL = tk.LabelFrame(self.COEFF_WIDGETS_FRAME_2, text="Coefficient 1 (y-separation)")
        self.COEFF1_LABEL.pack(anchor=tk.W, side=tk.LEFT, padx=2)
        self.COEFF1_SPINBOX = tk.Spinbox(self.COEFF1_LABEL, from_=0.0, to=100.0, increment=0.1,
                                         textvariable=self.cluster_coeff1)
        self.COEFF1_SPINBOX.pack(padx=2, pady=2)

        self.COEFF2_LABEL = tk.LabelFrame(self.COEFF_WIDGETS_FRAME_2, text="Coefficient 2 (slope)")
        self.COEFF2_LABEL.pack(anchor=tk.W, side=tk.LEFT, padx=2)
        self.COEFF2_SPINBOX = tk.Spinbox(self.COEFF2_LABEL, from_=0.0, to=100.0, increment=0.1,
                                         textvariable=self.cluster_coeff2)
        self.COEFF2_SPINBOX.pack(padx=2, pady=2)

        self.CONTROL_BUTTONS_FRAME_2 = tk.Frame(self.UPPER_FRAME_2)
        self.CONTROL_BUTTONS_FRAME_2.pack(anchor=tk.NW, side=tk.TOP, padx=2, pady=2, fill=tk.X)

        self.NEXT = tk.Button(self.CONTROL_BUTTONS_FRAME_2)
        self.NEXT['text'] = "Next..."
        self.NEXT['command'] = self._gotoStep3
        self.NEXT.pack(anchor=tk.NW, side=tk.LEFT)

        self.QUIT = tk.Button(self.CONTROL_BUTTONS_FRAME_2)
        self.QUIT['text'] = "Quit"
        self.QUIT['command'] = self._quitApp
        self.QUIT.pack(anchor=tk.SE, side=tk.RIGHT)

        self.LOWER_FRAME_2 = tk.LabelFrame(self.ROOT_FRAME_2, text="Clustering Result")
        self.LOWER_FRAME_2.pack(anchor=tk.N, side=tk.TOP)

        self.CLUSTER_FIGURE_CANVAS_2 = tk.Canvas(self.LOWER_FRAME_2)
        self.CLUSTER_FIGURE_CANVAS_2.pack(anchor=tk.N, side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._refreshClusteringCanvas()

        self.update()

        self.COEFF0_SPINBOX['command'] = self._refreshClusteringCanvas
        self.COEFF1_SPINBOX['command'] = self._refreshClusteringCanvas
        self.COEFF2_SPINBOX['command'] = self._refreshClusteringCanvas

    def _refreshClusteringCanvas(self):
        if self.cluster_fig_canv:
            self.cluster_fig_canv.get_tk_widget().destroy()
        self.CLUSTER_FIGURE_CANVAS_2.delete(tk.ALL)
        self._redrawClusteringFigure()
        self.cluster_fig_canv = FigureCanvasTkAgg(self.cluster_fig, master=self.CLUSTER_FIGURE_CANVAS_2)
        self.cluster_fig_canv.get_tk_widget().pack(anchor=tk.N, side=tk.TOP, fill=tk.BOTH, expand=True)
        self.CLUSTER_FIGURE_CANVAS_2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.update()

    def _redrawClusteringFigure(self):
        cluster_coeffs = (self.cluster_coeff0.get(), self.cluster_coeff1.get(), self.cluster_coeff2.get())
        _, self.cluster_ids = self.xcorr_ca.do_clustering(cluster_coeffs)

        if self.cluster_fig is not None:
            self.cluster_fig.clear()
        else:
            self.cluster_fig = plt.figure(figsize=(16,9))

        self.xcorr_ca.plot_clusters(self.cluster_fig.gca(), self.cluster_ids, cluster_coeffs, self.station_code)
        self.cluster_fig.tight_layout()
        self.cluster_fig.autofmt_xdate()

    def _gotoStep3(self):
        if self.current_step == 2:

            assert self.cluster_ids is not None

            self.NEXT['state'] = tk.DISABLED

            self._destroyFigures()

            self.CLUSTER_FIGURE_CANVAS_2.delete(tk.ALL)
            self.ROOT_FRAME_2.destroy()
            self.ROOT_FRAME_2 = None
            self.update()

            self._createStep3Widgets()

    def _createStep3Widgets(self):
        self.current_step = 3

        self.ROOT_FRAME_3 = tk.Frame(self)
        self.ROOT_FRAME_3.pack(fill=tk.BOTH, expand=1)

        self.QUIT = tk.Button(self.ROOT_FRAME_3)
        self.QUIT['text'] = "Quit"
        self.QUIT['command'] = self._quitApp
        self.QUIT.pack(anchor=tk.SE, side=tk.BOTTOM)


#end class


tk_root = tk.Tk()
app = GpsClockCorrectionApp(master=tk_root)
app.master.title("GPS Clock Correction Workflow")
app.master.minsize(320, 160)
app.master.columnconfigure(0, weight=1)
app.master.rowconfigure(0, weight=1)
app.mainloop()
# tk_root.destroy()
