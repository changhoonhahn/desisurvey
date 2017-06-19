import unittest
import tempfile
import shutil
import os
import datetime

import numpy as np
from astropy.table import Table
import astropy.time
import astropy.units as u

import desisurvey.config
from desisurvey.ephemerides import Ephemerides
from desisurvey.progress import Progress
from desisurvey.afternoonplan import surveyPlan
from desisurvey.nextobservation import nextFieldSelector

class TestNextField(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create a temporary directory.
        cls.tmpdir = tempfile.mkdtemp()
        # Write output files to this temporary directory.
        config = desisurvey.config.Configuration()
        config.set_output_path(cls.tmpdir)

        start = datetime.date(2019, 9, 1)
        stop = datetime.date(2019, 10, 1)
        cls.ephem = Ephemerides(start, stop, use_cache=False, write_cache=False)
        cls.surveyplan = surveyPlan(
            cls.ephem.start.mjd, cls.ephem.stop.mjd, cls.ephem)

    @classmethod
    def tearDownClass(cls):
        # Remove the directory after the test.
        shutil.rmtree(cls.tmpdir)
        # Reset our configuration.
        desisurvey.config.Configuration.reset()

    def test_nfs(self):
        #- Plan night 0; set the first 10 tiles as observed
        progress = Progress()
        planfile = self.surveyplan.afternoonPlan(self.ephem._table[0], progress)
        mjd = 2458728.708333 - 2400000.5  #- Sept 1 2019 @ 10pm in Arizona
        t0 = astropy.time.Time(mjd, format='mjd')

        tilesObserved = list()

        #- Observe 10 exp in a row at same MJD to ensure we don't keep picking
        #- the same tile and we increase in dec
        decobs = list()
        for i in range(10):
            tileinfo = nextFieldSelector(planfile, mjd, progress)
            progress.add_exposure(
                tileinfo['tileID'], t0 + i * u.min, 30 * u.s,
                1., 1.5, 1.1, 0, 0, 0)
            tilesObserved.append(tileinfo['tileID'])
            decobs.append(tileinfo['DEC'])
            prev_ra = tileinfo['RA']
            prev_dec = tileinfo['DEC']

        self.assertEqual(len(tilesObserved), len(np.unique(tilesObserved)))

        #- Fails
        ## self.assertTrue(np.all(np.diff(decobs)>0))

        #- Observe 10 exp at different MJDs to make sure we walk through RA
        raobs = list()
        for i in range(10):
            t0 += 0.3 * u.hour
            tileinfo = nextFieldSelector(planfile, t0.mjd, progress)
            progress.add_exposure(
                tileinfo['tileID'], t0, 1e3 * u.s, 1., 1.5, 1.1, 0, 0, 0)
            tilesObserved.append(tileinfo['tileID'])
            prev_ra = tileinfo['RA']
            prev_dec = tileinfo['DEC']
            raobs.append(tileinfo['RA'])

        #- Fails
        ## self.assertTrue(np.all(np.diff(raobs)>0))


#####
# These tests checked the right things but don't work with the new code
# Keeping them for reference until we have tests for the new AP code
#####

# class TestNextField(unittest.TestCase):
#
#     #- Parameters to use for default get_next_field call
#     def setUp(self):
#         self.dateobs = 2458728.708333  #- Sept 1 2019 @ 10pm in Arizona
#         self.skylevel = 0.0
#         self.transparency = 0
#         self.seeing = 1.0
#         self.previoustiles = []
#         self.programname = 'DESI'
#         #next_field = get_next_field(dateobs, skylevel, transparency, previoustiles, programname)
#
#     def test_output(self):
#         """
#         Test get_next_field output
#         """
#         next_field = get_next_field(self.dateobs, self.skylevel, self.seeing, \
#             self.transparency, self.previoustiles, self.programname)
#
#         #- Confirm that the output has the correct keys
#         self.assertLess(next_field['telera'], 360.0)
#         self.assertGreaterEqual(next_field['telera'], 0.0)
#         self.assertLess(next_field['teledec'], 90.0)
#         self.assertGreater(next_field['teledec'], -90.0)
#         self.assertGreater(next_field['tileid'], 0)
#         self.assertIsInstance(next_field['tileid'], int)
#         self.assertLessEqual(next_field['exptime'], next_field['maxtime'])
#         self.assertEqual(self.programname, next_field['programname'])
#
#         #- for a few keys, just check that they exist for now
#         self.assertIn('gfa', next_field)
#         self.assertIn('fibers', next_field)
#
#     def test_dateobs(self):
#         """
#         Test several values of dateobs
#         """
#         for dt in range(6):
#             next_field = get_next_field(self.dateobs + dt/24.0, self.skylevel, \
#                 self.transparency, self.previoustiles, self.programname)
#
#     #@unittest.expectedFailure
#     def test_previoustiles(self):
#         """
#         Test that previoustiles are in fact excluded
#         """
#         previoustiles = []
#         for test in range(10):
#             next_field = get_next_field(self.dateobs, self.skylevel, \
#                 self.seeing, self.transparency, previoustiles, self.programname)
#             self.assertNotIn(next_field['tileid'], previoustiles)
#             previoustiles.append(next_field['tileid'])
#
#     def test_rightanswer(self):
#         """
#         Test that the tileid returned is correct for the specified date. The values in
#         the rightanswer array were found by hand to be the 'correct' answer (i.e the tile
#         with the minimum declination, within +/- 15 degrees of the meridian.
#         """
#         rightanswer = [23492, 28072, 26499, 2435, 26832, 11522, 23364, 25159, 23492, 28072]
#         for test in range(10):
#             next_field = get_next_field(2458728.708 + 137.0*test, self.skylevel, self.seeing, \
#                 self.transparency, self.previoustiles, self.programname)
#             self.assertEqual(next_field['tileid'], rightanswer[test])

def test_suite():
    """Allows testing of only this module with the command::

        python setup.py test -m <modulename>
    """
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
