import unittest

from desisurvey.nextobservation import nextFieldSelector

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
                            
if __name__ == '__main__':
    unittest.main()
