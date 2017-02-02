from __future__ import print_function, division, absolute_import

from PySide import QtGui, QtCore
from ..QtInherit import HelpButton
from pkview.utils import get_icon

class OverviewWidget(QtGui.QWidget):

    def __init__(self):
        super(OverviewWidget, self).__init__()

        layout = QtGui.QVBoxLayout()

        # List for volume management
        tb = QtGui.QLabel("<font size=50> PKView </font> \n")

        pixmap = QtGui.QPixmap(get_icon("main_icon.png"))
        pixmap = pixmap.scaled(35, 35, QtCore.Qt.KeepAspectRatio)
        lpic = QtGui.QLabel(self)
        lpic.setPixmap(pixmap)

        b1 = HelpButton(self)
        l03 = QtGui.QHBoxLayout()
        l03.addWidget(lpic)
        l03.addWidget(tb)
        l03.addStretch(1)
        l03.addWidget(b1)

        ta = QtGui.QLabel("The GUI enables analysis of a DCE-MRI volume, ROI and multiple overlays "
                          "with pharmacokinetic modelling, subregion analysis and statistics included. "
                          "Please use help (?) buttons for more online information on each widget and the entire GUI. "
                          " \n \n"
                          "Creator: Benjamin Irving (mail@birving.com) \n"
                          "Contributors: Benjamin Irving, Martin Craig, Michael Chappell"
                          " \n \n"
                          "By using the this software you agree to the online licencing and disclaimer (see help)")
        ta.setWordWrap(True)

        t1 = QtGui.QLabel("Current overlays")
        self.l1 = CaseWidget(self)
        t2 = QtGui.QLabel("Current ROIs")
        self.l2 = RoiWidget(self)

        layout.addLayout(l03)
        layout.addWidget(ta)
        layout.addStretch()
        layout.addWidget(t1)
        layout.addWidget(self.l1)
        layout.addWidget(t2)
        layout.addWidget(self.l2)

        self.setLayout(layout)

    def add_image_management(self, image_vol_management):
        """
        Adding image management
        """
        self.ivm = image_vol_management
        self.l1.add_image_management(self.ivm)
        self.l2.add_image_management(self.ivm)

class CaseWidget(QtGui.QListWidget):
    """
    Class to handle the organisation of the loaded volumes
    """
    def __init__(self, parent):
        super(CaseWidget, self).__init__(parent)
        self.list_current = []
        self.ivm = None
        self.currentItemChanged.connect(self.emit_volume)

    def add_image_management(self, image_volume_management):
        self.ivm = image_volume_management
        self.ivm.sig_current_overlay.connect(self.update_current)
        self.ivm.sig_all_overlays.connect(self.update_list)

    def update_list(self, list1):
        self.clear()
        for ii in list1:
            if ii not in self.list_current:
                self.list_current.append(ii)
                self.addItem(ii)

    def update_current(self, ovl):
        if ovl is not None and ovl.name in self.list_current:
            ind1 = self.list_current.index(ovl.name)
            self.setCurrentItem(self.item(ind1))
        elif ovl is not None:
            print("Warning: This overlay does not exist")

    @QtCore.Slot()
    def emit_volume(self, choice1, choice1_prev):
        if choice1 is not None:
            self.ivm.set_current_overlay(choice1.text(), signal=True)

class RoiWidget(QtGui.QListWidget):
    """
    Class to handle the organisation of the loaded ROIs
    """
    def __init__(self, parent):
        super(RoiWidget, self).__init__(parent)
        self.list_current = []
        self.ivm = None
        self.currentItemChanged.connect(self.emit_volume)

    def add_image_management(self, image_volume_management):
        self.ivm = image_volume_management
        self.ivm.sig_current_roi.connect(self.update_current)
        self.ivm.sig_all_rois.connect(self.update_list)

    def update_list(self, list1):
        self.clear()
        for ii in list1:
            if ii not in self.list_current:
                self.list_current.append(ii)
                self.addItem(ii)

    def update_current(self, roi):
        if roi is not None and roi.name in self.list_current:
            ind1 = self.list_current.index(roi.name)
            self.setCurrentItem(self.item(ind1))
        elif roi is not None:
            print("Warning: This ROI does not exist")

    @QtCore.Slot()
    def emit_volume(self, choice1, choice1_prev):
        if choice1 is not None:
            self.ivm.set_current_roi(choice1.text(), signal=True)



