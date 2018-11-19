"""
Quantiphyse - Subclass of QpData for handling Nifti data

Copyright (c) 2013-2018 University of Oxford
"""
from __future__ import division, print_function

import os
import logging

import nibabel as nib
import numpy as np

from quantiphyse.utils import QpException
from .qpdata import DataGrid, QpData, NumpyData

LOG = logging.getLogger(__name__)

QP_NIFTI_EXTENSION_CODE = 42

class NiftiData(QpData):
    """
    QpData from a Nifti file
    """
    def __init__(self, fname):
        nii = nib.load(fname)
        shape = list(nii.shape)
        while len(shape) < 3:
            shape.append(1)

        if len(shape) > 3:
            nvols = shape[3]
        else:
            nvols = 1

        self.rawdata = None
        self.voldata = None
        self.nifti_header = nii.header
        metadata = None
        for ext in self.nifti_header.extensions:
            if ext.get_code() == QP_NIFTI_EXTENSION_CODE:
                import yaml
                LOG.debug("Found QP metadata: %s" % ext.get_content())
                metadata = yaml.load(ext.get_content())
                LOG.debug(metadata)

        grid = DataGrid(shape[:3], nii.header.get_best_affine())
        QpData.__init__(self, fname, grid, nvols, fname=fname, metadata=metadata)

    def raw(self):
        # NB: np.asarray convert data to an in-memory array instead of a numpy file memmap.
        # Appears to improve speed drastically as well as stop a bug with accessing the subset of the array
        # memmap has been designed to save space on ram by keeping the array on the disk but does
        # horrible things with performance, and analysis especially when the data is on the network.
        if self.rawdata is None:
            nii = nib.load(self.fname)
            self.rawdata = np.asarray(nii.get_data())
            self.rawdata = self._correct_dims(self.rawdata)

        self.voldata = None
        return self.rawdata
        
    def volume(self, vol):
        vol = min(vol, self.nvols-1)
        if self.nvols == 1:
            return self.raw()
        elif self.rawdata is not None:
            return self.rawdata[:, :, :, vol]
        else:
            if self.voldata is None:
                self.voldata = [None,] * self.nvols
            if self.voldata[vol] is None:
                nii = nib.load(self.fname)
                self.voldata[vol] = self._correct_dims(nii.dataobj[..., vol])

        return self.voldata[vol]

    def _correct_dims(self, arr):
        while arr.ndim < 3:
            arr = np.expand_dims(arr, -1)

        if self._raw_2dt and arr.ndim == 3:
            # Single-slice, interpret 3rd dimension as time
            arr = np.expand_dims(arr, 2)

        if arr.ndim == 4 and arr.shape[3] == 1:
            arr = np.squeeze(arr, axis=-1)
        return arr

def save(data, fname, grid=None, outdir=""):
    """
    Save data to a file
    
    :param data: QpData instance
    :param fname: File name
    :param grid: If specified, grid to save the data on
    :param outdir: Optional output directory if fname is not absolute
    """
    if grid is None:
        grid = data.grid
        arr = data.raw()
    else:
        arr = data.resample(grid).raw()
        
    if hasattr(data, "nifti_header"):
        header = data.nifti_header.copy()
    else:
        header = None

    img = nib.Nifti1Image(arr, grid.affine, header=header)
    img.update_header()
    if data.metadata:
        import yaml
        yaml_metadata = yaml.dump(data.metadata, default_flow_style=False)
        LOG.debug("Writing metadata: %s", yaml_metadata)
        ext = nib.nifti1.Nifti1Extension(QP_NIFTI_EXTENSION_CODE, yaml_metadata)
        img.header.extensions.append(ext)

    if not fname:
        fname = data.name
        
    _, extension = os.path.splitext(fname)
    if extension == "":
        fname += ".nii"
        
    if not os.path.isabs(fname):
        fname = os.path.join(outdir, fname)

    dirname = os.path.dirname(fname)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    LOG.debug("Saving %s as %s", data.name, fname)
    img.to_filename(fname)
    data.fname = fname
