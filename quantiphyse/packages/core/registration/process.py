"""
Quantiphyse - Analysis processes for registration and motion correction

Copyright (c) 2013-2018 University of Oxford
"""

import sys

import numpy as np

from quantiphyse.utils import debug, warn, get_plugins, set_local_file_path, QpException
from quantiphyse.processes import Process

def get_reg_method(method_name):
    """
    Get a named registration method (case insensitive)
    """
    methods = get_plugins("reg-methods")
    debug("Known methods: ", methods)
    for m in methods:
        method = m()
        if method.name.lower() == method_name.lower():
            return method
    return None

def _run_reg(worker_id, queue, method_name, options, regdata, refdata, voxel_sizes, warp_rois, ignore_idx=None):
    """
    Registration function for asynchronous process - used for moco and registration
    """
    try:
        set_local_file_path()
        method = get_reg_method(method_name)
        if method is None: 
            raise QpException("Unknown registration method: %s" % method_name)

        # Construct output arrays
        if regdata.ndim == 3: 
            regdata = np.expand_dims(regdata, -1)
            data_4d = False
        else:
            data_4d = True
        regdata_out = np.zeros(regdata.shape)

        if warp_rois is not None:
            if data_4d:
                raise QpException("Cannot have linked ROIs when registering more than one volume")
            warp_rois_out = np.zeros(warp_rois.shape)
        else: 
            warp_rois_out = None

        # Go through registration volumes and register each to the reference volume
        log = ""
        for t in range(regdata.shape[-1]):
            log += "Registering volume %i of %i\n" % (t+1, regdata.shape[-1])
            regvol = regdata[:,:,:,t]
            if t == ignore_idx:
                # Ignore this index (e.g. because it is the same as the ref volume in MoCo)
                regdata_out[:,:,:,t] = regvol
            else:
                # Register this volume and set the output data
                outvol, roivol, vol_log = method.reg(regvol, refdata, voxel_sizes, warp_rois, options)
                log += vol_log
                regdata_out[:,:,:,t] = outvol
                if warp_rois is not None: 
                    warp_rois_out = roivol
            queue.put(t)

        if not data_4d:
            regdata_out = np.squeeze(regdata_out, -1)
            if warp_rois is not None:
                # Make warped ROI integers
                # FIXME this is not really right, need to do nearest-neighbour interpolation
                warp_rois_out = np.around(warp_rois_out).astype(np.int)
            
        return worker_id, True, (regdata_out, warp_rois_out, log)
    except:
        return worker_id, False, sys.exc_info()[1]

class RegProcess(Process):
    """
    Asynchronous background process to run registration / motion correction
    """

    PROCESS_NAME = "Reg"

    def __init__(self, ivm, **kwargs):
        Process.__init__(self, ivm, worker_fn=_run_reg, **kwargs)

    def run(self, options):
        self.replace = options.pop("replace-vol", False)
        self.method = options.pop("method", "deeds")

        regdata_name = options.pop("reg", self.ivm.main.name)
        regdata = self.ivm.data[regdata_name]
        self.nvols = regdata.nvols

        self.output_name = options.pop("output-name", "reg_%s" % regdata_name)

        # Reference data defaults to same as reg data so MoCo can be
        # supported as self-registration
        refdata_name = options.pop("ref", regdata_name)

        # Resample the reference data onto the same grid as the data
        # we are registering
        # TODO should not have to resample whole data to get single vol!
        self.grid = regdata.grid
        refdata = self.ivm.data[refdata_name].resample(self.grid)
        if refdata.nvols > 1:
            self.refvol = options.pop("ref-vol", "median")
            if self.refvol == "median":
                refidx = int(refdata.nvols/2)
            elif self.refvol == "mean":
                raise NotImplementedError("Not yet implemented")
            else:
                refidx = self.refvol
            refdata = refdata.volume(refidx)
        else:
            refdata = refdata.raw()

        # Linked ROIS can be specified which will be warped in the same way as the main 
        # registration data. Useful for masks defined on an unregistered volume.
        # We handle multiple warp ROIs by building 4D data in which each volume is
        # a separate ROI. This is then unpacked at the end.
        self.warp_roi_names = dict(options.pop("warp-rois", {}))
        warp_roi_name = options.pop("warp-roi", None)
        if warp_roi_name is not None:  
            self.warp_roi_names[warp_roi_name] = warp_roi_name + "_warp"

        for roi_name in self.warp_roi_names.keys():
            if roi_name not in self.ivm.rois:
                warn("Removing non-existant ROI from warp list: %s" % roi_name)
                del self.warp_roi_names[roi_name]

        if len(self.warp_roi_names) > 0:
            warp_rois = np.zeros(list(refdata.shape) + [len(self.warp_roi_names)])
            for idx, roi_name in enumerate(self.warp_roi_names):
                roi = self.ivm.rois[roi_name].resample(regdata.grid)
                warp_rois[:,:,:,idx] = roi.raw()
            debug("Have %i warped ROIs" % len(self.warp_roi_names))
        else:
            warp_rois = None
        debug(self.warp_roi_names)

        # Remove all option values - individual reg methods should warn if there
        # are unexpected options FIXME WHAT IS THIS FOR?
        for key in options.keys():
            options.pop(key)

        # Function input data must be passed as list of arguments for multiprocessing
        self.start_bg([self.method, options, regdata.raw(), refdata, self.grid.spacing, warp_rois])

    def timeout(self):
        if self.queue.empty(): return
        while not self.queue.empty():
            done = self.queue.get()
        complete = float(done+1)/self.nvols
        self.sig_progress.emit(complete)

    def finished(self):
        """ Add output data to the IVM and set the log """
        self.log = ""
        if self.status == Process.SUCCEEDED:
            output = self.worker_output[0]
            self.ivm.add_data(output[0], name=self.output_name, grid=self.grid, make_current=True)

            if output[1] is not None: 
                for idx, roi_name in enumerate(self.warp_roi_names):
                    roi = output[1][:,:,:,idx]
                    debug("Adding warped ROI: %s" % self.warp_roi_names[roi_name])
                    self.ivm.add_roi(roi, name=self.warp_roi_names[roi_name], grid=self.grid, make_current=False)
            self.log = output[2]

class MocoProcess(RegProcess):
    """
    MoCo is identical to registration but has different batch name
    """

    PROCESS_NAME = "Moco"
