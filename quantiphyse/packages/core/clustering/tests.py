import unittest

import numpy as np

from quantiphyse.test.widget_test import WidgetTest

from .widgets import ClusteringWidget

NUM_CLUSTERS = 4
NAME = "test_clusters"
NUM_PCA = 3

class ClusteringWidgetTest(WidgetTest):

    def widget_class(self):
        return ClusteringWidget

    def testNoData(self):
        """ User clicks the run button with no data"""
        if self.w.run_btn.isEnabled():
            self.w.run_btn.clicked.emit()
        self.assertFalse(self.error)

    def test3dData(self):
        """ 3d clustering"""
        self.ivm.add_data(self.data_3d, name="data_3d")
        self.w.data_combo.setCurrentIndex(0)
        self.processEvents()
        self.assertFalse(self.w.n_pca.spin.isVisible())

        self.w.n_clusters.spin.setValue(NUM_CLUSTERS)
        self.w.output_name.setText(NAME)
        self.w.run_btn.clicked.emit()
        self.processEvents()
        
        self.assertTrue(NAME in self.ivm.rois)
        self.assertEquals(self.ivm.current_roi.name, NAME)
        self.assertEquals(len(self.ivm.rois[NAME].regions), NUM_CLUSTERS)
        self.assertFalse(self.error)
        
    def test3dDataWithRoi(self):
        """ 3d clustering"""
        self.ivm.add_data(self.data_3d, name="data_3d")
        self.ivm.add_roi(self.mask, name="mask")
        self.w.data_combo.setCurrentIndex(0)
        self.w.roi_combo.setCurrentIndex(1)
        self.w.n_clusters.spin.setValue(NUM_CLUSTERS)
        self.w.output_name.setText(NAME)
        self.w.run_btn.clicked.emit()
        self.processEvents()
        
        self.assertTrue(NAME in self.ivm.rois)
        self.assertEquals(self.ivm.current_roi.name, NAME)
        self.assertEquals(len(self.ivm.rois[NAME].regions), NUM_CLUSTERS)
        # Cluster value is always zero outside the ROI
        cl = self.ivm.rois[NAME].std()
        self.assertTrue(np.all(cl[self.mask.std() == 0] == 0))
        self.assertFalse(self.error)

    def test4dData(self):
        """ 4d clustering """
        self.ivm.add_data(self.data_4d, name="data_4d")
        self.w.data_combo.setCurrentIndex(0)
        self.processEvents()            
        self.assertTrue(self.w.n_pca.spin.isVisible())

        self.w.n_pca.spin.setValue(NUM_PCA)
        self.w.n_clusters.spin.setValue(NUM_CLUSTERS)
        self.w.output_name.setText(NAME)
        self.w.run_btn.clicked.emit()
        self.processEvents()
        
        self.assertTrue(NAME in self.ivm.rois)
        self.assertEquals(self.ivm.current_roi.name, NAME)
        self.assertEquals(len(self.ivm.rois[NAME].regions), NUM_CLUSTERS)
        self.assertFalse(self.error)
        
    def test4dDataWithRoi(self):
        """ 4d clustering within an ROI"""
        self.ivm.add_data(self.data_4d, name="data_4d")
        self.ivm.add_roi(self.mask, name="mask")
        self.w.data_combo.setCurrentIndex(0)
        self.w.roi_combo.setCurrentIndex(1)

        self.w.n_pca.spin.setValue(NUM_PCA)
        self.w.n_clusters.spin.setValue(NUM_CLUSTERS)
        self.w.output_name.setText(NAME)
        self.w.run_btn.clicked.emit()
        self.processEvents()
        
        self.assertTrue(NAME in self.ivm.rois)
        self.assertEquals(self.ivm.current_roi.name, NAME)
        self.assertEquals(len(self.ivm.rois[NAME].regions), NUM_CLUSTERS)
        # Cluster value is always zero outside the ROI
        cl = self.ivm.rois[NAME].std()
        self.assertTrue(np.all(cl[self.mask.std() == 0] == 0))
        self.assertFalse(self.error)

if __name__ == '__main__':
    unittest.main()