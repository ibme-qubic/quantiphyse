"""
Quantiphyse - Generic analysis widgets

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, print_function, absolute_import

import numpy as np
import pyqtgraph as pg
from PySide import QtCore, QtGui

from quantiphyse.gui.plot import Plot
from quantiphyse.gui.pickers import PickMode
from quantiphyse.gui.widgets import QpWidget, RoiCombo, HelpButton, BatchButton, TitleWidget, OverlayCombo
from quantiphyse.utils import get_icon, copy_table, get_kelly_col, sf

from .processes import CalcVolumesProcess, ExecProcess, DataStatisticsProcess

class MultiVoxelAnalysis(QpWidget):
    """
    Plots timeseries for multiple selected points
    """
    
    def __init__(self, **kwargs):
        super(MultiVoxelAnalysis, self).__init__(name="Multi-Voxel Analysis", icon="voxel", desc="Compare signal curves at different voxels", group="Analysis", position=2, **kwargs)

        self.colors = {'grey':(200, 200, 200), 'red':(255, 0, 0), 'green':(0, 255, 0), 'blue':(0, 0, 255),
                       'orange':(255, 140, 0), 'cyan':(0, 255, 255), 'brown':(139, 69, 19)}
        self.activated = False

    def init_ui(self):
        self.setStatusTip("Click points on the 4D volume to see data curve")

        vbox = QtGui.QVBoxLayout()

        title = TitleWidget(self, "Multi-Voxel Analysis", help="curve_compare", batch_btn=False)
        vbox.addWidget(title)

        # Plot window
        self.plot = Plot(clear_btn=True)
        self.plot.clear_btn.clicked.connect(self.clear_all)
        self.plot.options.sig_options_changed.connect(self.update_graph)
        vbox.addWidget(self.plot)

        opts_box = QtGui.QGroupBox()
        opts_box.setTitle('Point selection')
        opts_vbox = QtGui.QVBoxLayout()
        opts_box.setLayout(opts_vbox)

        # Select plot color
        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel('Plot color'))
        self.color_combo = QtGui.QComboBox(self)
        for text, col in self.colors.items():
            self.color_combo.addItem(text, col)
        self.color_combo.currentIndexChanged.connect(self.plot_col_changed)
        self.color_combo.setToolTip("Set the color of the enhancement curve when a point is clicked on the image. "
                                    "Allows visualisation of multiple enhancement curves of different colours")
        hbox.addWidget(self.color_combo)
        hbox.addStretch(1)
        opts_vbox.addLayout(hbox)

        # Show individual curves (can disable to just show mean)
        self.indiv_cb = QtGui.QCheckBox('Show individual curves', self)
        self.indiv_cb.toggle() # default ON
        self.indiv_cb.stateChanged.connect(self._indiv_changed)
        opts_vbox.addWidget(self.indiv_cb)

        # Show mean
        self.mean_cb = QtGui.QCheckBox('Show mean curve', self)
        self.mean_cb.stateChanged.connect(self._mean_changed)
        opts_vbox.addWidget(self.mean_cb)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(opts_box)
        hbox.addStretch()
        vbox.addLayout(hbox)

        vbox.addStretch(1)
        self.setLayout(vbox)
    
        self.color_combo.setCurrentIndex(self.color_combo.findText("red"))
        self.col = self.colors["red"]

        self.plots = {}
        self.mean_plots = {}
        self.clear_all()

    def activate(self):
        self.ivm.sig_main_data.connect(self.update_graph)
        self.ivl.sig_selection_changed.connect(self.sel_changed)
        self.ivl.set_picker(PickMode.MULTIPLE)
        self.activated = True
        self.update_graph()

    def deactivate(self):
        self.ivm.sig_main_data.disconnect(self.update_graph)
        self.ivl.sig_selection_changed.disconnect(self.sel_changed)
        self.ivl.set_picker(PickMode.SINGLE)

    def options_changed(self, _):
        if self.activated:
            self.update_graph()

    def update_graph(self):
        if self.ivm.main:
            xlabel = self.ivm.main.metadata.get("vol_scale", "Volume")
            xunits = self.ivm.main.metadata.get("vol_units", "")
            if xunits:
                xlabel = "%s (%s)" % (xlabel, xunits)
            self.plot.set_xlabel(xlabel)

            if self.plot.options.sig_enh:
                self.plot.set_ylabel("Signal enhancement")
            else:
                self.plot.set_ylabel("Signal")

    def _indiv_changed(self):
        for plt in self.plots.values():
            if self.indiv_cb.isChecked():
                plt.show()
            else:
                plt.hide()

    def _mean_changed(self):
        if self.mean_cb.isChecked():
            self.update_means()
            for plt in self.mean_plots.values():
                plt.show()
        else:
            for plt in self.mean_plots.values():
                plt.hide()

    def clear_all(self):
        """
        Clear point data
        """
        self.plots, self.mean_plots = {}, {}
        # Reset the list of picked points
        self.ivl.set_picker(PickMode.MULTIPLE)
        self.ivl.picker.col = self.col

    def add_point(self, point, col):
        """
        Add a selected point of the specified colour
        """
        sig = self.ivm.main.timeseries(point, grid=self.ivl.grid)
        if point in self.plots:
            self.plot.remove(self.plots[point])

        self.plots[point] = self.plot.add_line(None, sig, line_col=col)
        if not self.indiv_cb.isChecked():
            self.plots[point].hide()
        self.update_means()

    def update_means(self):
        for col in self.colors.values():
            if col in self.mean_plots:
                self.plot.remove(self.mean_plots[col])
                del self.mean_plots[col]
            all_plts = [plt for plt in self.plots.values() if plt.line_col == col]
            if all_plts:
                mean_values = np.stack([plt.yvalues for plt in all_plts], axis=1)
                mean_values = np.squeeze(np.mean(mean_values, axis=1))
                self.mean_plots[col] = self.plot.add_line(None, mean_values, line_col=col, line_style=QtCore.Qt.DashLine, point_brush=col, point_col='k', point_size=10)
                if not self.mean_cb.isChecked():
                    self.mean_plots[col].hide()

    def sel_changed(self, picker):
        """
        Point selection changed
        """
        # Add plots for points in the selection which we haven't plotted (or which have changed colour)
        allpoints = []
        for col, points in picker.selection().items():
            points = [tuple([int(p+0.5) for p in pos]) for pos in points]
            allpoints += points
            for point in points:
                if point not in self.plots or self.plots[point].line_col != col:
                    self.add_point(point, col)

        # Remove plots for points no longer in the selection
        for point in self.plots:
            if point not in allpoints:
                self.plots[point].hide()
                del self.plots[point]

    def plot_col_changed(self, idx):
        self.col = tuple(self.color_combo.itemData(idx))
        self.ivl.picker.col = self.col

class DataStatistics(QpWidget):

    def __init__(self, **kwargs):
        super(DataStatistics, self).__init__(name="Data Statistics", desc="Display statistics about data sets", icon="edit", group="DEFAULT", position=1, **kwargs)
        
    def init_ui(self):
        """ Set up UI controls here so as not to delay startup"""
        self.process = DataStatisticsProcess(self.ivm)
        self.process_ss = DataStatisticsProcess(self.ivm)
        
        main_vbox = QtGui.QVBoxLayout()

        title = TitleWidget(self, help="overlay_stats", batch_btn=False)
        main_vbox.addWidget(title)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel("Data selection"))
        self.data_combo = OverlayCombo(self.ivm, all_option=True)
        self.data_combo.currentIndexChanged.connect(self.update_all)
        hbox.addWidget(self.data_combo)
        hbox.addWidget(QtGui.QLabel("ROI"))
        self.roi_combo = RoiCombo(self.ivm, none_option=True)
        self.roi_combo.currentIndexChanged.connect(self.update_all)
        hbox.addWidget(self.roi_combo)
        hbox.addStretch(1)
        main_vbox.addLayout(hbox)

        # Summary stats
        stats_box = QtGui.QGroupBox()
        stats_box.setTitle('Summary Statistics')
        vbox = QtGui.QVBoxLayout()
        stats_box.setLayout(vbox)

        hbox = QtGui.QHBoxLayout()
        self.butgen = QtGui.QPushButton("Show")
        self.butgen.setToolTip("Show standard statistics for the data in each ROI")
        self.butgen.clicked.connect(self.show_stats)
        hbox.addWidget(self.butgen)
        self.copy_btn = QtGui.QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy_stats)
        self.copy_btn.setVisible(False)
        hbox.addWidget(self.copy_btn)
        hbox.addStretch(1)
        vbox.addLayout(hbox)

        self.stats_table = QtGui.QTableView()
        self.stats_table.resizeColumnsToContents()
        self.stats_table.setModel(self.process.model)
        self.stats_table.setVisible(False)
        vbox.addWidget(self.stats_table)

        main_vbox.addWidget(stats_box)

        # Summary stats (single slice)

        stats_box_ss = QtGui.QGroupBox()
        stats_box_ss.setTitle('Summary Statistics - Slice')
        vbox = QtGui.QVBoxLayout()
        stats_box_ss.setLayout(vbox)

        hbox = QtGui.QHBoxLayout()
        self.butgenss = QtGui.QPushButton("Show")
        self.butgenss.setToolTip("Show standard statistics for the current slice")
        self.butgenss.clicked.connect(self.show_stats_current_slice)
        hbox.addWidget(self.butgenss)
        self.slice_dir_label = QtGui.QLabel("Slice direction:")
        self.slice_dir_label.setVisible(False)
        hbox.addWidget(self.slice_dir_label)
        self.sscombo = QtGui.QComboBox()
        self.sscombo.addItem("Axial")
        self.sscombo.addItem("Coronal")
        self.sscombo.addItem("Sagittal")
        self.sscombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.sscombo.currentIndexChanged.connect(self.focus_changed)
        self.sscombo.setVisible(False)
        hbox.addWidget(self.sscombo)
        self.copy_btn_ss = QtGui.QPushButton("Copy")
        self.copy_btn_ss.clicked.connect(self.copy_stats_ss)
        self.copy_btn_ss.setVisible(False)
        hbox.addWidget(self.copy_btn_ss)
        hbox.addStretch(1)
        vbox.addLayout(hbox)

        self.stats_table_ss = QtGui.QTableView()
        self.stats_table_ss.resizeColumnsToContents()
        self.stats_table_ss.setModel(self.process_ss.model)
        self.stats_table_ss.setVisible(False)
        vbox.addWidget(self.stats_table_ss)

        main_vbox.addWidget(stats_box_ss)

        main_vbox.addStretch(1)
        self.setLayout(main_vbox)

    def activate(self):
        self.ivm.sig_current_roi.connect(self.update_all)
        self.ivm.sig_all_data.connect(self.update_all)
        self.ivm.sig_current_data.connect(self.update_all)
        self.ivl.sig_focus_changed.connect(self.focus_changed)
        self.update_all()

    def deactivate(self):
        self.ivm.sig_current_roi.disconnect(self.update_all)
        self.ivm.sig_all_data.disconnect(self.update_all)
        self.ivm.sig_current_data.connect(self.update_all)
        self.ivl.sig_focus_changed.disconnect(self.focus_changed)

    def mode_changed(self, idx):
        self.ovl_selection = idx
        self.update_all()

    def focus_changed(self, _):
        if self.stats_table_ss.isVisible():
            self.update_stats_current_slice()

    def update_all(self):
        if self.stats_table.isVisible():
            self.update_stats()
        if self.stats_table_ss.isVisible():
            self.update_stats_current_slice()

    def copy_stats(self):
        copy_table(self.process.model)

    def copy_stats_ss(self):
        copy_table(self.process_ss.model)
        
    def show_stats(self):
        if self.stats_table.isVisible():
            self.stats_table.setVisible(False)
            self.copy_btn.setVisible(False)
            self.butgen.setText("Show")
        else:
            self.update_stats()
            self.stats_table.setVisible(True)
            self.copy_btn.setVisible(True)
            self.butgen.setText("Hide")

    def show_stats_current_slice(self):
        if self.stats_table_ss.isVisible():
            self.stats_table_ss.setVisible(False)
            self.slice_dir_label.setVisible(False)
            self.sscombo.setVisible(False)
            self.copy_btn_ss.setVisible(False)
            self.butgenss.setText("Show")
        else:
            self.update_stats_current_slice()
            self.stats_table_ss.setVisible(True)
            self.slice_dir_label.setVisible(True)
            self.sscombo.setVisible(True)
            self.copy_btn_ss.setVisible(True)
            self.butgenss.setText("Hide")

    def update_stats(self):
        self.populate_stats_table(self.process, {})

    def update_stats_current_slice(self):
        if self.ivm.main is not None:
            slice_dir = 2-self.sscombo.currentIndex()
            options = {
                "slice-dir" : slice_dir,
                "slice-pos" : self.ivl.focus(self.ivm.main.grid)[slice_dir],
            }
            self.populate_stats_table(self.process_ss, options)

    def populate_stats_table(self, process, options):
        if self.data_combo.currentText() != "<all>":
            options["data"] = self.data_combo.currentText()
        roi = self.roi_combo.currentText()
        if roi in self.ivm.data:
            options["roi"] = roi
        process.run(options)

class RoiAnalysisWidget(QpWidget):
    """
    Analysis of ROIs
    """
    def __init__(self, **kwargs):
        super(RoiAnalysisWidget, self).__init__(name="ROI Analysis", icon="roi", desc="Analysis of ROIs", 
                                                group="ROIs", **kwargs)
        
    def init_ui(self):
        self.process = CalcVolumesProcess(self.ivm)

        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)

        title = TitleWidget(self, help="roi_analysis")
        layout.addWidget(title)

        info = QtGui.QLabel("<i><br>Calculate size and volume of an ROI<br></i>")
        info.setWordWrap(True)
        layout.addWidget(info)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel('ROI: '))
        self.combo = RoiCombo(self.ivm)
        self.combo.currentIndexChanged.connect(self.update)
        hbox.addWidget(self.combo)
        hbox.addStretch(1)
        layout.addLayout(hbox)

        self.table = QtGui.QTableView()
        self.table.resizeColumnsToContents()
        self.table.setModel(self.process.model)
        layout.addWidget(self.table)

        hbox = QtGui.QHBoxLayout()
        self.copy_btn = QtGui.QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy_stats)
        hbox.addWidget(self.copy_btn)
        hbox.addStretch(1)
        layout.addLayout(hbox)
        layout.addStretch(1)

    def activate(self):
        self.ivm.sig_current_roi.connect(self.current_roi_changed)
        self.ivm.sig_all_data.connect(self.update)
        self.update()

    def deactivate(self):
        self.ivm.sig_current_roi.disconnect(self.current_roi_changed)
        self.ivm.sig_all_data.disconnect(self.update)

    def batch_options(self):
        return "CalcVolumes", {"roi" : self.combo.currentText()}

    def current_roi_changed(self, roi):
        self.combo.setCurrentIndex(self.combo.findText(roi.name))

    def update(self):
        roi = self.combo.currentText()
        if roi in self.ivm.rois:
            self.process.run({"roi" : roi, "no-extras" : True})
        
    def copy_stats(self):
        copy_table(self.process.model)

MATHS_INFO = """
<i>Create data using simple mathematical operations on existing data
<br><br>
For example, if you have loaded data called 'mydata' and run modelling
to produce a model prediction 'modelfit', you could calculate the residuals
using:</i>
<br><br>
resids = mydata - modelfit
<br>
"""

class SimpleMathsWidget(QpWidget):
    def __init__(self, **kwargs):
        super(SimpleMathsWidget, self).__init__(name="Simple Maths", icon="maths", 
                                                desc="Simple mathematical operations on data", 
                                                group="Processing", **kwargs)

    def init_ui(self):
        layout = QtGui.QVBoxLayout()
        self.setLayout(layout)

        title = TitleWidget(self, help="simple_maths")
        layout.addWidget(title)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel('<font size="5">Simple Maths</font>'))
        hbox.addStretch(1)
        hbox.addWidget(BatchButton(self))
        hbox.addWidget(HelpButton(self))
        layout.addLayout(hbox)
        
        info = QtGui.QLabel(MATHS_INFO)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.process = ExecProcess(self.ivm)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel("Set"))
        self.output_name_edit = QtGui.QLineEdit("newdata")
        self.output_name_edit.setFixedWidth(100)
        hbox.addWidget(self.output_name_edit)
        hbox.addWidget(QtGui.QLabel("="))
        self.proc_edit = QtGui.QLineEdit()
        hbox.addWidget(self.proc_edit)
        layout.addLayout(hbox)
        
        hbox = QtGui.QHBoxLayout()
        self.go_btn = QtGui.QPushButton("Go")
        self.go_btn.setFixedWidth(50)
        self.go_btn.clicked.connect(self.go)
        hbox.addWidget(self.go_btn)
        hbox.addStretch(1)
        layout.addLayout(hbox)

        layout.addStretch(1)

    def batch_options(self):
        return "SimpleMaths", {self.output_name_edit.text() : self.proc_edit.text()}

    def go(self):
        options = self.batch_options()[1]
        self.process.run(options)

class ModelCurvesOptions(QtGui.QDialog):
    def __init__(self, parent):
        QtGui.QDialog.__init__(self, parent)
        self.parent = parent

        self.setWindowTitle('Plot options')
        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        # Display mode
        self.mode = 0
        grid.addWidget(QtGui.QLabel("Display mode"), 0, 0)
        self.mode_combo = QtGui.QComboBox()
        self.mode_combo.addItem("Signal")
        self.mode_combo.addItem("Signal Enhancement")
        self.mode_combo.addItem("Signal and Residuals")
        self.mode_combo.currentIndexChanged.connect(self.mode_changed)
        grid.addWidget(self.mode_combo, 0, 1)

        # Y-axis scale
        self.auto_y_cb = QtGui.QCheckBox('Automatic Y axis scale', self)
        self.auto_y_cb.setChecked(True)
        self.auto_y_cb.stateChanged.connect(self.auto_y_changed)

        hbox = QtGui.QHBoxLayout()
        grid.addWidget(self.auto_y_cb, 1, 0)
        self.min_lbl = QtGui.QLabel("Min")
        self.min_lbl.setEnabled(False)
        hbox.addWidget(self.min_lbl)
        self.min_spin = QtGui.QDoubleSpinBox()
        self.min_spin.setMinimum(-1e20)
        self.min_spin.setMaximum(1e20)
        self.min_spin.valueChanged.connect(parent.update)
        self.min_spin.setEnabled(False)
        hbox.addWidget(self.min_spin)
        self.max_lbl = QtGui.QLabel("Max")
        self.max_lbl.setEnabled(False)
        hbox.addWidget(self.max_lbl)
        self.max_spin = QtGui.QDoubleSpinBox()
        self.max_spin.setMinimum(-1e20)
        self.max_spin.setMaximum(1e20)
        self.max_spin.valueChanged.connect(parent.update)
        self.max_spin.setEnabled(False)
        hbox.addWidget(self.max_spin)
        hbox.addStretch(1)
        grid.addLayout(hbox, 1, 1)

        # Signal enhancement baseline
        self.se_lbl = QtGui.QLabel('Signal enhancement: Use first')
        self.se_lbl.setEnabled(False)
        grid.addWidget(self.se_lbl, 2, 0)

        hbox = QtGui.QHBoxLayout()
        self.norm_frames = QtGui.QSpinBox()
        self.norm_frames.setValue(3)
        self.norm_frames.setMinimum(1)
        self.norm_frames.setMaximum(100)
        self.norm_frames.valueChanged.connect(parent.update)
        self.norm_frames.setEnabled(False)
        hbox.addWidget(self.norm_frames)
        self.se_lbl2 = QtGui.QLabel('frames as baseline')
        self.se_lbl2.setEnabled(False)
        hbox.addWidget(self.se_lbl2)
        hbox.addStretch(1)
        grid.addLayout(hbox, 2, 1)

    def mode_changed(self, idx):
        self.mode = idx
        se = (self.mode == 1)
        self.se_lbl.setEnabled(se)
        self.norm_frames.setEnabled(se)
        self.se_lbl2.setEnabled(se)
        self.parent.update()

    def auto_y_changed(self, ch):
        self.min_lbl.setEnabled(not ch)
        self.min_spin.setEnabled(not ch)
        self.max_lbl.setEnabled(not ch)
        self.max_spin.setEnabled(not ch)
        self.parent.update()

class VoxelAnalysis(QpWidget):
    """
    View original data and generated signal curves side by side
    """

    def __init__(self, **kwargs):
        super(VoxelAnalysis, self).__init__(name="Voxel analysis", desc="Display data at a voxel", 
                                          icon="curve_view", group="Analysis", **kwargs)
        self.data_enabled = {}
        self.updating = False

    def init_ui(self):
        main_vbox = QtGui.QVBoxLayout()
        self.setLayout(main_vbox)
        self.setStatusTip("Click points on the 4D volume to see actual and predicted curve")

        title = TitleWidget(self, title="Voxel analysis", help="modelfit", batch_btn=False, opts_btn=True)
        main_vbox.addWidget(title)

        win = pg.GraphicsLayoutWidget()
        win.setBackground(background=None)
        self.plot = Plot()

        ## For second y-axis, create a new ViewBox, link the right axis to its coordinate system
        self.plot_rightaxis = pg.ViewBox()
        self.plot.scene().addItem(self.plot_rightaxis)
        self.plot.getAxis('right').linkToView(self.plot_rightaxis)
        self.plot_rightaxis.setXLink(self.plot)
        self.plot.vb.sigResized.connect(self._update_plot_viewbox)

        main_vbox.addWidget(win)

        hbox = QtGui.QHBoxLayout()

        # Table showing RMS deviation
        rms_box = QtGui.QGroupBox()
        rms_box.setTitle('Timeseries data')
        vbox = QtGui.QVBoxLayout()
        self.rms_table = QtGui.QStandardItemModel()
        self.rms_table.itemChanged.connect(self.data_table_changed)
        tview = QtGui.QTableView()
        tview.resizeColumnsToContents()
        tview.setModel(self.rms_table)
        vbox.addWidget(tview)
        rms_box.setLayout(vbox)
        hbox.addWidget(rms_box)

        # Table showing value of model parameters
        params_box = QtGui.QGroupBox()
        params_box.setTitle('Non-timeseries data')
        vbox2 = QtGui.QVBoxLayout()
        self.values_table = QtGui.QStandardItemModel()
        tview = QtGui.QTableView()
        tview.resizeColumnsToContents()
        tview.setModel(self.values_table)
        vbox2.addWidget(tview)
        params_box.setLayout(vbox2)
        hbox.addWidget(params_box)

        main_vbox.addLayout(hbox)

        self.plot_opts = ModelCurvesOptions(self)
    
    def _update_plot_viewbox(self):
        """ Required to keep the right and left axis plots in sync with each other """
        self.plot_rightaxis.setGeometry(self.plot.vb.sceneBoundingRect())
        
        ## need to re-update linked axes since this was called
        ## incorrectly while views had different shapes.
        ## (probably this should be handled in ViewBox.resizeEvent)
        self.plot_rightaxis.linkedViewChanged(self.plot.vb, self.plot_rightaxis.XAxis)

    def show_options(self):
        self.update_minmax(self.ivm.data)
        self.plot_opts.show()
        self.plot_opts.raise_()

    def activate(self):
        self.ivm.sig_all_data.connect(self.update)
        self.ivl.sig_focus_changed.connect(self.update)
        self.update()

    def deactivate(self):
        self.ivm.sig_all_data.disconnect(self.update)
        self.ivl.sig_focus_changed.disconnect(self.update)

    def options_changed(self, opts):
        if hasattr(self, "plot"):
            # Have we been initialized?
            self.update()

    def update_minmax(self, data_items):
        dmin, dmax, first = 0, 100, True
        for name in data_items:
            data_range = self.ivm.data[name].range()
            if first or data_range[0] < dmin: dmin = data_range[0]
            if first or data_range[1] > dmax: dmax = data_range[1]
            first = False
        self.plot_opts.min_spin.setValue(dmin)
        self.plot_opts.max_spin.setValue(dmax)

    def update(self, pos=None):
        self._update_table()
        self._update_rms_table()
        self._plot()

    def _update_table(self):
        """
        Set the data parameter values in the table based on the current point clicked
        """
        self.values_table.clear()
        self.values_table.setHorizontalHeaderItem(0, QtGui.QStandardItem("Value"))
        data_vals = self.ivm.values(self.ivl.focus(), self.ivl.grid)
        for ii, ovl in enumerate(sorted(data_vals.keys())):
            if self.ivm.data[ovl].ndim == 3:
                self.values_table.setVerticalHeaderItem(ii, QtGui.QStandardItem(ovl))
                self.values_table.setItem(ii, 0, QtGui.QStandardItem(sf(data_vals[ovl])))

    def _update_rms_table(self):
        try:
            self.updating = True # Hack to prevent plot being refreshed during table update
            self.rms_table.clear()
            self.rms_table.setHorizontalHeaderItem(0, QtGui.QStandardItem("Name"))
            self.rms_table.setHorizontalHeaderItem(1, QtGui.QStandardItem("RMS (Position)"))
            idx = 0
            pos = self.ivl.focus()
            sigs = self.ivm.timeseries(pos, self.ivl.grid)
            max_length = max([0,] + [len(sig) for sig in sigs.values()])

            if not self.ivm.main:
                return

            main_curve = self.ivm.main.timeseries(pos, grid=self.ivl.grid)
            main_curve.extend([0] * max_length)
            main_curve = main_curve[:max_length]

            for name in sorted(sigs.keys()):
                # Make sure data curve is correct length
                data_curve = sigs[name]
                data_curve.extend([0] * max_length)
                data_curve = data_curve[:max_length]

                data_rms = np.sqrt(np.mean(np.square([v1-v2 for v1, v2 in zip(main_curve, data_curve)])))

                name_item = QtGui.QStandardItem(name)
                name_item.setCheckable(True)
                name_item.setEditable(False)
                if name not in self.data_enabled:
                    self.data_enabled[name] = QtCore.Qt.Checked
                name_item.setCheckState(self.data_enabled[name])
                self.rms_table.setItem(idx, 0, name_item)

                item = QtGui.QStandardItem(sf(data_rms))
                item.setEditable(False)
                self.rms_table.setItem(idx, 1, item)
                idx += 1
        finally:
            self.updating = False

    def data_table_changed(self, item):
        if not self.updating:
            # A checkbox has been toggled
            self.data_enabled[item.text()] = item.checkState()
            self._plot()

    def _plot(self):
        """
        Plot the curve / curves
        """
        self.plot.clear() 
        self.plot_rightaxis.clear()

        # Get all timeseries signals and determine max number of timepoints
        pos = self.ivl.focus()
        sigs = self.ivm.timeseries(pos, self.ivl.grid)
        max_length = max([0, ] + [len(sig) for name, sig in sigs.items() if self.data_enabled[name] == QtCore.Qt.Checked])
        
        if max_length == 0:
            return
        
        # FIXME custom range for residuals axis?
        self.plot_rightaxis.enableAutoRange()
        if self.plot_opts.auto_y_cb.isChecked():
            self.plot.enableAutoRange()
        else: 
            self.plot.disableAutoRange()
            self.plot.setYRange(self.plot_opts.min_spin.value(), self.plot_opts.max_spin.value())
            
        # Replaces any existing legend but keep position the same in case user moved it
        legend_pos = (30, 30)
        if self.plot.legend: 
            legend_pos = self.plot.legend.pos()
            self.plot.legend.scene().removeItem(self.plot.legend)
        legend = self.plot.addLegend(offset=legend_pos)

        # Get x scale
        xx = self.opts.t_scale
        if len(xx) > 1:
            unit = xx[-1] - xx[-2]
        else:
            unit = 1
        xx.extend([xx[-1] + unit*(idx+1) for idx in range(max_length)])
        xx = xx[:max_length]
        frames1 = self.plot_opts.norm_frames.value()
        self.plot.setLabel('bottom', self.opts.t_type, units=self.opts.t_unit)

        # Set y labels
        axis_labels = {0 : "Signal", 1 : "Signal enhancement", 2 : "Signal"}
        self.plot.setLabel('left', axis_labels[self.plot_opts.mode])
        if self.plot_opts.mode == 2:
            self.plot.showAxis('right')
            self.plot.getAxis('right').setLabel('Residual')
        else:
            self.plot.hideAxis('right')

        if not self.ivm.main:
            return

        main_curve = self.ivm.main.timeseries(pos, grid=self.ivl.grid)
        main_curve.extend([0] * max_length)
        main_curve = main_curve[:max_length]

        idx, _ = 0, len(sigs)
        for ovl, sig_values in sigs.items():
            if self.data_enabled[ovl] == QtCore.Qt.Checked:
                sig_values.extend([0] * max_length)
                sig_values = sig_values[:max_length]

                pen = get_kelly_col(idx)

                if self.plot_opts.mode == 1:
                    # Show signal enhancement rather than raw values
                    m1 = np.mean(sig_values[:frames1])
                    if m1 != 0: sig_values = sig_values / m1 - 1
                
                if self.plot_opts.mode == 2 and ovl != self.ivm.main.name:
                    # Show residuals on the right hand axis
                    resid_values = [v1 - v2 for v1, v2 in zip(sig_values, main_curve)]
                    self.plot_rightaxis.addItem(pg.PlotCurveItem(resid_values, pen=pg.mkPen(pen, style=QtCore.Qt.DashLine)))
                    
                # Plot signal or signal enhancement
                self.plot.plot(xx, sig_values, pen=None, symbolBrush=(200, 200, 200), symbolPen='k', symbolSize=5.0)
                line = self.plot.plot(xx, sig_values, pen=pen, width=4.0)
                legend.addItem(line, ovl)
                idx += 1
