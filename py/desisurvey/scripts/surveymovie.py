"""Script wrapper for creating a movie of survey progress.

To run this script from the command line, use the ``surveymovie`` entry point
that is created when this package is installed, and should be in your shell
command search path.

The external program ffmpeg must be installed to use this script.
"""
from __future__ import print_function, division, absolute_import

import argparse
import os.path

import numpy as np

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec
import matplotlib.animation
import matplotlib.colors
import matplotlib.animation

import astropy.time
import astropy.io.fits
import astropy.units as u

import desiutil.log

import desisurvey.ephemerides
import desisurvey.utils
import desisurvey.config
import desisurvey.progress
import desisurvey.plots


def parse(options=None):
    """Parse command-line options for running survey planning.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose', action='store_true',
        help='display log messages with severity >= info')
    parser.add_argument('--debug', action='store_true',
        help='display log messages with severity >= debug (implies verbose)')
    parser.add_argument('--progress', default='progress.fits', metavar='FITS',
        help='name of FITS file with progress record')
    parser.add_argument(
        '--start', type=str, default=None, metavar='DATE',
        help='movie starts on the evening of this day, formatted as YYYY-MM-DD')
    parser.add_argument(
        '--stop', type=str, default=None, metavar='DATE',
        help='movie stops on the morning of this day, formatted as YYYY-MM-DD')
    parser.add_argument(
        '--expid', type=int, default=None, metavar='ID',
        help='index of single exposure to display')
    parser.add_argument(
        '--save', type=str, default='surveymovie', metavar='NAME',
        help='base name (without extension) of output file to write')
    parser.add_argument(
        '--label', type=str, default='DESI surveysim', metavar='TEXT',
        help='label to display on each frame')
    parser.add_argument(
        '--output-path', default=None, metavar='PATH',
        help='output path where output files should be written')

    if options is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(options)

    # Validate start/stop date args and covert to datetime objects.
    # Unspecified values are taken from our config.
    config = desisurvey.config.Configuration()
    if args.start is None:
        args.start = config.first_day()
    else:
        try:
            args.start = desisurvey.utils.get_date(args.start)
        except ValueError as e:
            raise ValueError('Invalid start: {0}'.format(e))
    if args.stop is None:
        args.stop = config.last_day()
    else:
        try:
            args.stop = desisurvey.utils.get_date(args.stop)
        except ValueError as e:
            raise ValueError('Invalid stop: {0}'.format(e))
    if args.start >= args.stop:
        raise ValueError('Expected start < stop.')

    return args


def wrap(angle, offset=-60):
    """Wrap values in the range [0, 360] to [offset, offset+360].
    """
    return np.fmod(angle - offset + 360, 360) + offset


class Animator(object):
    """Manage animation of survey progress.
    """
    def __init__(self, ephem, progress, start, stop, label):
        """
        """
        self.ephem = ephem
        self.label = label
        self.config = desisurvey.config.Configuration()
        tiles = progress._table
        self.ra = wrap(tiles['ra'])
        self.dec = tiles['dec']
        self.passnum = tiles['pass']
        self.tileid = tiles['tileid']

        # Get a list of exposures in [start, stop].
        self.exposures = progress.get_exposures(
            start, stop, tile_fields='tileid,ra,dec,pass',
            exp_fields='expid,mjd,night,exptime,snr2cum')
        self.num_exp = len(self.exposures)

        # Calculate each exposure's LST window.
        exp_midpt = astropy.time.Time(
            self.exposures['mjd'] + self.exposures['exptime'] / 86400.,
            format='mjd', location=desisurvey.utils.get_location())
        lst_midpt = exp_midpt.sidereal_time('apparent').to(u.deg).value
        # convert from seconds to degrees.
        lst_len = self.exposures['exptime'] / 240.
        self.lst = np.empty((self.num_exp, 2))
        self.lst[:, 0] = wrap(lst_midpt - 0.5 * lst_len)
        self.lst[:, 1] = wrap(lst_midpt + 0.5 * lst_len)

    def init_figure(self, width=1920, height=1080, dpi=32):
        """
        """
        self.dpi = float(dpi)
        # Initialize figure and axes.
        self.figure = plt.figure(
            frameon=False,figsize=(width / self.dpi, height / self.dpi),
            dpi=self.dpi)
        grid = matplotlib.gridspec.GridSpec(3, 3)
        grid.update(left=0, right=1, bottom=0, top=0.97, hspace=0, wspace=0)
        axes = []
        self.scatters = []
        self.lstlines = []
        self.avoids = []
        self.avoid_names = list(self.config.avoid_bodies.keys)
        navoids = len(self.avoid_names)
        assert self.avoid_names[0] == 'moon'
        bgcolor = matplotlib.colors.to_rgba('lightblue')
        self.nowcolor = np.array([0., 0.7, 0., 1.])
        passnum = 0
        for row in range(3):
            for col in range(3):
                # Create the axes for this pass.
                ax = plt.subplot(grid[row, col], facecolor=bgcolor)
                ax.set_xticks([])
                ax.set_yticks([])
                axes.append(ax)
                # Top-right corner is reserved for a plot.
                if row == 0 and col == 2:
                    ax.set_xlim(0, 1)
                    ax.set_ylim(0, 1)
                    plt.plot([0, 1], [0, 1], 'k:')
                    continue
                ax.set_xlim(-55, 293)
                ax.set_ylim(-20, 77)
                # Draw the tile outlines for this pass.
                sel = (self.passnum == passnum)
                ntiles = np.count_nonzero(sel)
                fc = np.zeros((ntiles, 4))
                fc[:, 1] = 1.0
                fc[:, 3] = 0.5
                ec = np.zeros((ntiles, 4))
                ec[:, 3] = 0.25
                s = np.full(ntiles, 85.)
                self.scatters.append(ax.scatter(
                    self.ra[sel], self.dec[sel], s=s, facecolors=fc,
                    edgecolors=ec, lw=1))
                # Initialize positions of moon and planets.
                fc = np.zeros((navoids, 4))
                ec = np.zeros((navoids, 4))
                ec[:, 2:] = 1.
                s = np.full(navoids, 500.)
                s[0] = 1500.
                self.x_avoid = np.zeros(navoids)
                self.y_avoid = np.zeros(navoids)
                self.avoids.append(ax.scatter(
                    self.x_avoid, self.y_avoid, s=s, facecolors=fc,
                    edgecolors=ec, lw=1))
                # Draw LST lines for the current exposure.
                line1 = ax.axvline(0., lw=2, ls=':', color=self.nowcolor)
                line2 = ax.axvline(0., lw=2, ls=':', color=self.nowcolor)
                self.lstlines.append((line1, line2))
                passnum += 1

        # Initialize scheduler score colormap.
        self.scorecmap = matplotlib.cm.get_cmap('hot_r')

        # Add axis above plot to display programs during the night.
        paxes = plt.axes([0, 0.97, 0.66667, 0.03], facecolor='y')
        paxes.set_xticks([])
        paxes.set_yticks([])
        edges = 0.5 + np.linspace(-6., +7., 13 * 12) / 24.
        self.dmjd = 0.5 * (edges[1:] + edges[:-1])
        paxes.set_xlim(edges[0], edges[-1])
        paxes.set_ylim(0., 1.)
        self.pdata = np.zeros(len(self.dmjd), int)
        # Prepare a custom colormap.
        pcolors = desisurvey.plots.program_color
        colors = [bgcolor, pcolors['DARK'], pcolors['GRAY'], pcolors['BRIGHT']]
        pcmap = matplotlib.colors.ListedColormap(colors, 'programs')
        self.programs = paxes.imshow(
            self.pdata.reshape(1, -1), interpolation='none', aspect='auto',
            extent=(edges[0], edges[-1], 0., 1.),
            vmin=-0.5, vmax=3.5, cmap=pcmap)
        self.pline1 = paxes.axvline(0., lw=4, ls='-', color=self.nowcolor)
        self.pline2 = paxes.axvline(0., lw=4, ls='-', color=self.nowcolor)

        # Add text label in the top-right corner.
        self.text = plt.annotate(
            'YYYY-MM-DD #000000', xy=(0.995, 0.997), xytext=(0.995, 0.997),
            xycoords='figure fraction', fontsize=64, family='monospace',
            color='k', horizontalalignment='right', verticalalignment='top')

        # List all animated artists.
        self.artists = self.scatters + self.avoids + [
            self.programs, self.pline1, self.pline2, self.text]
        for l1, l2 in self.lstlines:
            self.artists += [l1, l2]

        # Initialize internal tracking vars.
        self.last_date = None
        self.scores = None
        self.idx0 = None

    def draw_exposure(self, idx, last_date=None, scores=None, idx0=0):
        """
        """
        info = self.exposures[idx]
        mjd = info['mjd']
        date = desisurvey.utils.get_date(mjd)
        assert str(date) == info['night']
        night = self.ephem.get_night(date)
        # Update the top-right label.
        self.text.set_text(
            '{0} {1} #{2:06d}'.format(self.label, date, info['expid']))
        if date != self.last_date:
            # Update the observing program for this night.
            dark, gray, bright = self.ephem.get_program(
                night['noon'] + self.dmjd)
            self.pdata[:] = 0
            self.pdata[dark] = 1
            self.pdata[gray] = 2
            self.pdata[bright] = 3
            self.programs.set_data(self.pdata.reshape(1, -1))
            # Load new scheduler scores for this night.
            scores_name = self.config.get_path('scores_{0}.fits'.format(date))
            if os.path.exists(scores_name):
                hdus = astropy.io.fits.open(scores_name, memmap=False)
                self.scores = hdus[0].data
                hdus.close()
                # Save index of first exposure on this date.
                self.idx0 = np.argmax(self.exposures['night'] == str(date))
            self.last_date = date
        # Update current time in program.
        dt1 = mjd - night['noon']
        dt2 = dt1 + info['exptime'] / 86400.
        self.pline1.set_xdata([dt1, dt1])
        self.pline2.set_xdata([dt2, dt2])
        # Update scores display for this exposure.
        score = self.scores[idx - self.idx0]
        max_score = np.max(score)
        for passnum, scatter in enumerate(self.scatters):
            sel = (self.passnum == passnum)
            fc = self.scorecmap(score[sel] / max_score)
            scatter.get_sizes()[:] = 85.
            if info['pass'] == passnum:
                # Highlight the tile being observed now.
                jdx = np.where(self.tileid[sel] == info['tileid'])[0][0]
                fc[jdx] = self.nowcolor
                scatter.get_sizes()[jdx] = 600.
                scatter.get_edgecolors()[jdx] = self.nowcolor
            scatter.set_facecolors(fc)
        # Update LST lines.
        x1, x2 = self.lst[idx]
        for passnum, (line1, line2) in enumerate(self.lstlines):
            ls = '-' if info['pass'] == passnum else '--'
            line1.set_linestyle(ls)
            line2.set_linestyle(ls)
            line1.set_xdata([x1, x1])
            line2.set_xdata([x2, x2])
        # Update moon and planet locations.
        for i, name in enumerate(self.avoid_names):
            f_obj = desisurvey.ephemerides.get_object_interpolator(night, name)
            # Calculate this object's (dec,ra) path during the night.
            obj_dec, obj_ra = f_obj(mjd)
            self.x_avoid[i] = wrap(obj_ra)
            self.y_avoid[i] = obj_dec
        for scatter in self.avoids:
            scatter.set_offsets([self.x_avoid, self.y_avoid])


def main(args):
    """Command-line driver for updating the survey plan.
    """
    # Set up the logger
    if args.debug:
        log = desiutil.log.get_logger(desiutil.log.DEBUG)
        args.verbose = True
    elif args.verbose:
        log = desiutil.log.get_logger(desiutil.log.INFO)
    else:
        log = desiutil.log.get_logger(desiutil.log.WARNING)

    # Freeze IERS table for consistent results.
    desisurvey.utils.freeze_iers()

    # Set the output path if requested.
    config = desisurvey.config.Configuration()
    if args.output_path is not None:
        config.set_output_path(args.output_path)

    # Load ephemerides.
    ephem = desisurvey.ephemerides.Ephemerides()

    # Load progress.
    progress = desisurvey.progress.Progress(args.progress)

    # Initialize.
    animator = Animator(ephem, progress, args.start, args.stop, args.label)
    log.info('Found {0} exposures from {1} to {2}.'
             .format(animator.num_exp, args.start, args.stop))
    animator.init_figure()

    if args.expid is not None:
        expid = animator.exposures['expid']
        assert np.all(expid == expid[0] + np.arange(len(expid)))
        if (args.expid < expid[0]) or (args.expid > expid[-1]):
            raise RuntimeError('Requested exposure ID {0} not available.'
                               .format(args.expid))
        animator.draw_exposure(args.expid - expid[0])
        save_name = args.save + '.png'
        plt.savefig(save_name)
        log.info('Saved {0}.'.format(save_name))
    else:
        def init():
            return animator.artists
        def update(idx):
            log.info('Drawing frame {0}/{1}'.format(idx + 1, animator.num_exp))
            animator.draw_exposure(idx)
            return animator.artists
        animation = matplotlib.animation.FuncAnimation(
            animator.figure, update, init_func=init, interval=100,
            blit=True, frames=animator.num_exp)
        writer = matplotlib.animation.writers['ffmpeg'](
            bitrate=2400, metadata=dict(artist='surveymovie'))
        save_name = args.save + '.mp4'
        animation.save(save_name, writer=writer, dpi=animator.dpi)
        log.info('Saved {0}.'.format(save_name))
