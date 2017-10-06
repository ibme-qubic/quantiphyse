"""

Author: Benjamin Irving (benjamin.irv@gmail.com)
Copyright (c) 2013-2015 University of Oxford, Benjamin Irving

"""
import os.path
import glob
import importlib

from PySide import QtGui

from ..utils import debug, warn, get_icon

def _possible_module(f):
    if f.endswith("__init__.py"): 
        return None
    elif os.path.isdir(f): 
        return os.path.basename(f)
    elif f.endswith(".py") or f.endswith(".dll") or f.endswith(".so"):
        return os.path.basename(f).rsplit(".", 1)[0]

def _load_plugins(dirname, pkgname):
    """
    Beginning of plugin system - load modules dynamically from the specified directory

    Then check in module for widgets and/or processes to return
    """
    submodules = glob.glob(os.path.join(dirname, "*"))
    widgets, processes = [], []
    done = set()
    for f in submodules:
        mod = _possible_module(f)
        if mod is not None and mod not in done:
            done.add(mod)
            modname = "%s.%s" % (pkgname, mod)
            try:
                m = importlib.import_module(modname)
                if hasattr(m, "WIDGETS"):
                    debug(modname, m.WIDGETS)
                    widgets += m.WIDGETS
                if hasattr(m, "PROCESSES"):
                    debug(modname, m.PROCESSES)
                    processes += m.PROCESSES
            except:
                warn("Error loading widget: %s" % modname)
    debug(widgets)
    debug(processes)
    return widgets, processes

def get_known_widgets():
    """
    Beginning of plugin system - load widgets dynamically from this package

    Will be extended to load widgets and processes from some specified plugins directory
    """
    widgets, processes = _load_plugins(os.path.dirname(__file__), "quantiphyse.widgets")
    return widgets

class QpWidget(QtGui.QWidget):
    """
    Base class for a Quantiphyse widget

    The following properties are set automatically from keyword args or defaults:
      self.ivm - Image Volume Management instance
      self.ivl - ImageView instance
      self.icon - QIcon for the menu/tab
      self.name - Name for the menu
      self.description - Longer description (for tooltip)
      self.tabname - Name for the tab
    """
    def __init__(self, **kwargs):
        super(QpWidget, self).__init__()
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("desc", self.name)
        self.icon = QtGui.QIcon(get_icon(kwargs.get("icon", "")))
        self.tabname = kwargs.get("tabname", self.name.replace(" ", "\n"))
        self.ivm = kwargs.get("ivm", None)
        self.ivl = kwargs.get("ivl", None)
        self.opts = kwargs.get("opts", None)
        self.default = kwargs.get("default", False)
        self.visible = False
        if self.opts:
                self.opts.sig_options_changed.connect(self.options_changed)

    def init_ui(self):
        """
        Called when widget is first shown. Widgets should ideally override this to build their
        UI widgets when required, rather than in the constructor which is called at startup
        """
        pass

    def activate(self):
        """
        Called when widget is made active, so can for example connect signals to the 
        volume management or view classes, and update it's current state
        """
        pass

    def deactivate(self):
        """
        Called when widget is made inactive, so should for example disconnect signals and remove 
        any related selections from the view
        """
        pass

    def options_changed(self):
        """
        Override to respond to global option changes
        """
        pass

