"""Track progress of completed DESI observations.
"""
from __future__ import print_function, division


import numpy as np

import astropy.table

import desimodel.io

import desiutil.log

import desisurvey.config

# Increment this value whenever a non-backwards compatible change to the
# table schema is introduced.
_version = 1

class Progress(object):
    """Initialize a progress tracking object.

    The tracker can either be loaded from a file or created from scratch.

    The progress table is designed to minmize duplication of static tile data
    that is already tabulated in the footprint definition table, except for
    the PASS, RA, DEC columns which are useful for generating plots.

    The progress table also does not capture ephemeris data that can be
    easily reproduced from an exposure time stamp.

    Parameters
    ----------
    filename : str or None
        Read an existing progress record from the specified file name. A
        relative path name refers to the :meth:`configuration output path
        <desisurvey.config.Configuration.get_path>`. Creates a new progress
        record from sratch when None.
    max_exposures : int
        Maximum number of exposures of a single tile that a newly created
        table will allocate space for.  Ignored when a previous file name
        is being read.
    """
    def __init__(self, filename=None, max_exposures=16):

        self.log = desiutil.log.get_logger()

        if filename is None:
            # Load the list of tiles to observe.
            tiles = astropy.table.Table(
                desimodel.io.load_tiles(onlydesi=True, extra=False))
            num_tiles = len(tiles)
            # Initialize a new progress table.
            meta = dict(VERSION=_version)
            table = astropy.table.Table(meta=meta)
            table['tileid'] = astropy.table.Column(
                length=num_tiles, dtype=np.int32,
                description='DESI footprint tile ID')
            table['pass'] = astropy.table.Column(
                length=num_tiles, dtype=np.int32,
                description='Observing pass number starting at zero')
            table['ra'] = astropy.table.Column(
                length=num_tiles, description='TILE center RA in degrees',
                unit='deg', format='%.1f')
            table['dec'] = astropy.table.Column(
                length=num_tiles, description='TILE center DEC in degrees',
                unit='deg', format='%.1f')
            table['status'] = astropy.table.Column(
                length=num_tiles, dtype=np.int32,
                description='Observing status: 0=none, 1=partial, 2=done')
            # Add per-exposure columns.
            table['mjd'] = astropy.table.Column(
                length=num_tiles, shape=(max_exposures,), format='%.5f',
                description='MJD of exposure start time')
            table['exptime'] = astropy.table.Column(
                length=num_tiles, shape=(max_exposures,), format='%.1f',
                description='Exposure duration in seconds', unit='s')
            table['snr2frac'] = astropy.table.Column(
                length=num_tiles, shape=(max_exposures,), format='%.3f',
                description='Fraction of target S/N**2 ratio achieved')
            table['airmass'] = astropy.table.Column(
                length=num_tiles, shape=(max_exposures,), format='%.1f',
                description='Estimate airmass of observation')
            table['seeing'] = astropy.table.Column(
                length=num_tiles, shape=(max_exposures,), format='%.1f',
                description='Estimate FWHM seeing of observation in arcsecs',
                unit='arcsec')
            # Copy tile data.
            table['tileid'] = tiles['TILEID']
            table['pass'] = tiles['PASS']
            table['ra'] = tiles['RA']
            table['dec'] = tiles['DEC']
            # Initialize other columns.
            table['status'] = 0
            table['mjd'] = 0.
            table['exptime'] = 0.
            table['snr2frac'] = 0.
            table['airmass'] = 0.
            table['seeing'] = 0.

        else:
            config = desisurvey.config.Configuration()
            filename = config.get_path(filename)
            table = astropy.table.Table.read(filename)
            self.log.info('Loaded progress from {0}.'.format(filename))
            # Check that this table has the current version.
            if table.meta['VERSION'] != _version:
                raise RuntimeError(
                    'Progress table has incompatible version {0}.'
                    .format(table.meta['VERSION']))

        # Initialize attributes from table data.
        self._table = table
        self._last_mjd = np.max(table['mjd'])

    @property
    def num_tiles(self):
        """Number of tiles in DESI footprint"""
        return len(self._table)

    @property
    def last_mjd(self):
        """MJD of most recent exposure or 0 if no exposures have been added."""
        return self._last_mjd

    @property
    def max_exposures(self):
        """Maximum allowed number of exposures of a single tile."""
        return len(self._table[0]['mjd'])

    def completed(self, before_mjd=None, include_partial=True):
        """Number of tiles completed.

        Completion is based on the sum of ``snr2frac`` values for all exposures
        of each tiles.  A completed tile (with ``status`` of 2) counts as one
        towards the completion value, even if its ``snr2frac`` exceeds one.

        Parameters
        ----------
        before_mjd : float
            Only include exposures before the specified MJD cutoff, or use all
            exposures when None.
        include_partial : bool
            Include partially completed tiles according to their sum of snfrac
            values.

        Returns
        -------
        float
            Number of tiles completed. Will always be an integer (returned as
            a float) when ``include_partial`` is False, and will generally
            be non-integer otherwise.
        """
        snr2frac = self._table['snr2frac'].data
        if before_mjd is not None:
            mjd = self._table['mjd'].data
            snr2frac = snr2frac.copy()
            # Zero any SNR**2 after the cutoff.
            snr2frac[self._table['mjd'] >= before_mjd] = 0.
        snr2sum = snr2frac.sum(axis=1)
        # Count fully completed tiles as 1.
        completed = snr2sum >= 1.
        n = float(np.count_nonzero(completed))
        if include_partial:
            # Add partial SNR**2 sums.
            n += snr2sum[~completed].sum()
        return n

    def save(self, filename, overwrite=True):
        """Save the current progress to a file.

        The saved file can be restored from disk using our constructor.

        Parameters
        ----------
        filename : str
            Read an existing progress record from the specified file name. A
            relative path name refers to the :meth:`configuration output path
            <desisurvey.config.Configuration.get_path>`. Creates a new progress
            record from sratch when None.
        overwrite : bool
            Silently overwrite any existing file when this is True.
        """
        config = desisurvey.config.Configuration()
        filename = config.get_path(filename)
        self._table.write(filename, overwrite=overwrite)
        self.log.info('Saved progress to {0}.'.format(filename))

    def get_tile(self, tile_id):
        """Lookup the progress of a single tile.

        Parameters
        ----------
        tile_id : integer
            Valid DESI footprint tile ID.

        Returns
        -------
        astropy.table.Row
            Row of progress table for the requested tile.
        """
        row_sel = np.where(self._table['tileid'] == tile_id)[0]
        if len(row_sel) != 1:
            raise ValueError('Invalid tile_id {0}.'.format(tile_id))
        return self._table[row_sel[0]]

    def get_observed(self, include_partial=True):
        """Return a table of previously observed tiles.

        The returned table is a copy of our internal data, not a view, so
        any changes to its contents are decoupled.

        Parameters
        ----------
        include_partial : bool
            Include partially completed tiles (status=1) in the returned table.

        Returns
        -------
        table view
            Copy of our internal table with only observed rows included.
        """
        sel = self._table['status'] >= (1 if include_partial else 2)
        return self._table[sel]

    def get_summary(self, include='all'):
        """Get a per-tile summary of progress so far.

        Returns a new table so any modifications are decoupled from our
        internal table.  Exposure MJD values are summarized as separate
        ``mjd_min`` and ``mjd_max`` columns, with both equal to zero for
        un-observed tiles. The summary ``exptime`` and ``snr2frac`` columns
        are sums of the individual exposures.  The summary ``airmass``
        and ``seeing`` columns are means.

        Parameters
        ----------
        include : 'all', 'observed', or 'completed'
            Specify which tiles to include in the summary. The 'observed'
            selection will include tiles that have been observed at least
            once but have not yet reached their SNR**2 goal.
        """
        min_status = dict(all=0, observed=1, completed=2)
        if include not in min_status.keys():
            raise ValueError('Invalid include option: pick one of {0}.'
                             .format(', '.join(min_status.keys())))

        # Start a new summary table with the selected rows.
        sel = self._table['status'] >= min_status[include]
        summary = self._table[sel][['tileid', 'pass', 'ra', 'dec', 'status']]

        # Summarize exposure start times.
        mjd = self._table['mjd'].data[sel]
        summary['mjd_min'] = mjd[:, 0]
        summary['mjd_max'] = mjd.max(axis=1)

        # Sum the remaining per-exposure columns.
        for name in ('exptime', 'snr2frac', 'airmass', 'seeing'):
            summary[name] = self._table[name].data[sel].sum(axis=1)

        # Convert the airmass and seeing sums to means.  We use mean rather
        # than median since it is easier to calculate with a variable nexp.
        nexp = (mjd > 0).sum(axis=1).astype(int)
        mask = nexp > 0
        summary['airmass'][mask] /= nexp[mask]
        summary['seeing'][mask] /= nexp[mask]

        return summary

    def add_exposure(self, tile_id, mjd, exptime, snr2frac, airmass, seeing):
        """Add a single exposure to the progress.

        Parameters
        ----------
        tile_id : int
            DESI footprint tile ID
        mjd : float
            MJD of exposure start time.  Must be larger than any previous
            exposure.
        exptime : float
            Exposure open shutter time in seconds.
        snr2frac : float
            Fraction of the design SNR**2 achieved during this exposure.
        airmass : float
            Estimated airmass of this exposure.
        seeing : float
            Estimated FWHM seeing of this exposure in arcseconds.
        """
        row = self.get_tile(tile_id)

        # Check that we have not reached the maximum allowed exposures.
        num_exp = np.count_nonzero(row['mjd'] > 0)
        if num_exp == self.max_exposures:
            raise RuntimeError(
                'Reached maximum exposure limit ({0}) for tile_id {1}.'
                .format(self.max_exposures, tile_id))

        # Check for increasing timestamps.
        if mjd <= self._last_mjd:
            raise ValueError('Exposure MJD <= last MJD.')
        self._last_mjd = mjd

        # Save this exposure.
        row['mjd'][num_exp] = mjd
        row['exptime'][num_exp] = exptime
        row['snr2frac'][num_exp] = snr2frac
        row['airmass'][num_exp] = airmass
        row['seeing'][num_exp] = seeing

        # Update this tile's status.
        row['status'] = 1 if row['snr2frac'].sum() < 1 else 2
