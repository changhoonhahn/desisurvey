"""Utility functions for plotting DESI survey progress and planning.
"""
from __future__ import print_function, division

import numpy as np

import astropy.table

import desiutil.plots

import desisurvey.ephemerides


# Color associated with each program in the functions below.
program_color = {'DARK': 'black', 'GRAY': 'gray', 'BRIGHT': 'orange'}


def plot_sky_passes(ra, dec, passnum, z, clip_lo=None, clip_hi=None,
                    label='label', save=None):
    """Plot sky maps for each pass of a per-tile scalar quantity.

    The matplotlib package must be installed to use this function.

    Parameters
    ----------
    ra : array
        Array of RA values to use in degrees.
    dec : array
        Array of DEC values to use in degrees.
    pass : array
        Array of integer pass values to use.
    z : array
        Array of per-tile values to plot.
    clip_lo : float or string or None
        See :meth:`desiutil.plot.prepare_data`
    clip_hi : float or string or None
        See :meth:`desiutil.plot.prepare_data`
    label : string
        Brief description of per-tile value ``z`` to use for axis labels.
    save : string or None
        Name of file where plot should be saved.  Format is inferred from
        the extension.

    Returns
    -------
    tuple
        Tuple (figure, axes) returned by ``plt.subplots()``.
    """
    import matplotlib.pyplot as plt

    z = desiutil.plots.prepare_data(
        z, clip_lo=clip_lo, clip_hi=clip_hi, save_limits=True)
    vmin, vmax = z.vmin, z.vmax
    hopts = dict(bins=50, range=(vmin, vmax), histtype='step')

    fig, ax = plt.subplots(3, 3, figsize=(15, 10))

    # Mapping of subplots to passes.
    pass_map = [(0, 0), (0, 1), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    # Mapping of passes to programs.
    pass_program = ['DARK'] * 4 + ['GRAY'] + ['BRIGHT'] * 3
    max_count = 0.
    for p in range(8):
        color = program_color[pass_program[p]]
        basemap = desiutil.plots.init_sky(ax=ax[pass_map[p]],
                                          ra_labels=[-120, 0, 120],
                                          dec_labels=None,
                                          galactic_plane_color=color)
        # Select the tiles in this pass.
        sel = np.where(passnum == p)[0]
        z_sel = desiutil.plots.prepare_data(
            z[sel], clip_lo=vmin, clip_hi=vmax, save_limits=True)
        # Plot the sky map for this pass.
        desiutil.plots.plot_sky_circles(
            ra_center=ra[sel], dec_center=dec[sel], data=z_sel,
            colorbar=True, basemap=basemap, edgecolor='none', label=label)
        # Plot the histogram of values for this pass.
        counts, _, _ = ax[0, 2].hist(z[sel], color=color, **hopts)
        max_count = max(counts.max(), max_count)

    # Decorate the histogram subplot.
    ax[0, 2].set_xlim(vmin, vmax)
    ax[0, 2].set_ylim(0, 1.05 * max_count)
    ax[0, 2].set_xlabel(label)
    ax[0, 2].get_yaxis().set_ticks([])

    plt.subplots_adjust(wspace=0.1, hspace=0.2)
    # Make extra room for the histogram x-axis label.
    hist_rect = ax[0, 2].get_position(original=True)
    hist_rect.y0 = 0.70
    ax[0, 2].set_position(hist_rect)

    if save:
        plt.savefig(save)

    return fig, ax


def plot_observations(start=None, stop=None, what='EXPTIME',
                      verbose=False, save=None):
    """Plot a summary of observed tiles.

    Reads the file ``obsall_list.fits`` and uses :func:`plot_sky_passes` to
    display a summary of observed tiles in each pass.

    Parameters
    ----------
    start : date or None
        First night to include in the plot or use the start of the
        calculated ephemerides.  Must be convertible to an astropy time.
    stop : date or None
        First night to include in the plot or use the start of the
        calculated ephemerides.  Must be convertible to an astropy time.
    what : string
        What quantity to plot for each planned tile. Must be a
        column name in the obsall_list FITS file.  Useful values include
        EXPTIME, OBSSN2, AIRMASS, SEEING.
    verbose : bool
        Print a summary of observed tiles.
    save : string or None
        Name of file where plot should be saved.

    Returns
    -------
    tuple
        Tuple (figure, axes) returned by ``plt.subplots()``.
    """
    t = astropy.table.Table.read('obslist_all.fits')
    if what not in t.colnames:
        raise ValueError('Valid names are: {0}'
                         .format(','.join(t.colnames)))

    sel = t['STATUS'] > 0
    if start is None:
        start = astropy.time.Time(t['MJD'][0], format='mjd')
    else:
        start = astropy.time.Time(start)
        sel &= t['MJD'] >= start.mjd
    if stop is None:
        stop = astropy.time.Time(t['MJD'][-1], format='mjd')
    else:
        stop = astropy.time.Time(stop)
        sel &= t['MJD'] <= stop.mjd
    date_label = '{0} to {1}'.format(
        start.datetime.date(), stop.datetime.date())
    t = t[sel]

    if verbose:
        print('Observing summary for {0}:'.format(date_label))
        for pass_num in range(8):
            sel_pass = t['PASS'] == pass_num
            n_exps = np.count_nonzero(sel_pass)
            n_tiles = len(np.unique(t['TILEID'][sel_pass]))
            print('Observed {0:7d} tiles with {1:5d} repeats from PASS {2}'
                  .format(n_tiles, n_exps - n_tiles, pass_num))
        n_exps = len(t)
        n_tiles = len(np.unique(t['TILEID']))
        print('Observed {0:7d} tiles with {1:5d} repeats total.'
              .format(n_tiles, n_exps - n_tiles))

    label = '{0} ({1})'.format(what, date_label)
    return desisurvey.plots.plot_sky_passes(
        t['RA'], t['DEC'], t['PASS'], t[what],
        label=label, save=save)


def plot_program(ephem, start=None, stop=None, window_size=7.,
                 num_points=500, save=None):
    """Plot an overview of the DARK/GRAY/BRIGHT program.

    The matplotlib and pytz packages must be installed to use this function.

    Parameters
    ----------
    ephem : :class:`desisurvey.ephemerides.Ephemerides`
        Tabulated ephemerides data to use for determining the program.
    start : date or None
        First night to include in the plot or use the start of the
        calculated ephemerides.  Must be convertible to an astropy time.
    stop : date or None
        First night to include in the plot or use the start of the
        calculated ephemerides.  Must be convertible to an astropy time.
    window_size : float
        Number of hours on both sides of local midnight to display on the
        vertical axis.
    num_points : int
        Number of subdivisions of the vertical axis to use for tabulating
        the program during each night.
    save : string or None
        Name of file where plot should be saved.  Format is inferred from
        the extension.

    Returns
    -------
    tuple
        Tuple (figure, axes) returned by ``plt.subplots()``.
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors
    import matplotlib.dates
    import matplotlib.ticker
    import pytz

    # Determine plot date range.
    t = ephem._table
    sel = np.ones(len(t), bool)
    if start is not None:
        sel &= t['MJDstart'] >= astropy.time.Time(start).mjd
    if stop is not None:
        sel &= t['MJDstart'] <= astropy.time.Time(stop).mjd
    t = t[sel]
    num_nights = len(t)

    # Date labels use the KPNO UTC-7 timezone.
    tz_offset = -7
    tz = pytz.FixedOffset(tz_offset * 60)
    # Convert noon UTC-7 into midnight UTC before and after display range.
    start = astropy.time.Time(
        t['MJDstart'][0] + tz_offset / 24. - 0.5, format='mjd')
    stop = astropy.time.Time(
        t['MJDstart'][-1] + tz_offset / 24. + 0.5, format='mjd')
    # Calculate numerical limits of matplotlib date axis.
    x_lo = matplotlib.dates.date2num(tz.localize(start.datetime))
    x_hi = matplotlib.dates.date2num(tz.localize(stop.datetime))

    # Display 24-hour local time on y axis.
    window_int = int(np.floor(window_size))
    y_ticks = np.arange(-window_int, +window_int + 1, dtype=int)
    y_labels = ['{:02d}h'.format(hr) for hr in (24 + y_ticks) % 24]

    # Build a grid of elapsed time relative to local midnight during each night.
    midnight = t['MJDstart'] + 0.5
    t_edges = np.linspace(-window_size, +window_size, num_points + 1) / 24.
    t_centers = 0.5 * (t_edges[1:] + t_edges[:-1])

    # Loop over nights to build image data to plot.
    program = np.zeros((num_nights, len(t_centers)))
    for i in np.arange(num_nights):
        mjd_grid = midnight[i] + t_centers
        dark, gray, bright = ephem.get_program(mjd_grid)
        program[i][dark] = 1.
        program[i][gray] = 2.
        program[i][bright] = 3.

    # Prepare a custom colormap.
    colors = ['lightblue', program_color['DARK'],
              program_color['GRAY'], program_color['BRIGHT']]
    mycmap = matplotlib.colors.ListedColormap(colors, 'programs')

    # Make the plot.
    fig, ax = plt.subplots(1, 1, figsize=(11, 8.5), squeeze=True)

    ax.imshow(program.T, origin='lower', interpolation='none',
              aspect='auto', cmap=mycmap, vmin=-0.5, vmax=+3.5,
              extent=[x_lo, x_hi, -window_size, +window_size])

    # Display 24-hour local time on y axis.
    ax.set_ylabel('Local Time [UTC{0:+d}]'.format(tz_offset),
                  fontsize='x-large')
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)

    # Display date on x axis.
    ax.set_xlabel('Survey Date', fontsize='x-large')
    ax.set_xlim(tz.localize(start.datetime), tz.localize(stop.datetime))
    if num_nights < 50:
        # Major ticks at month boundaries.
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(tz=tz))
        ax.xaxis.set_major_formatter(
            matplotlib.dates.DateFormatter('%m/%y', tz=tz))
        # Minor ticks at day boundaries.
        ax.xaxis.set_minor_locator(matplotlib.dates.DayLocator(tz=tz))
    elif num_nights <= 650:
        # Major ticks at month boundaries with no labels.
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(tz=tz))
        ax.xaxis.set_major_formatter(matplotlib.ticker.NullFormatter())
        # Minor ticks at month midpoints with centered labels.
        ax.xaxis.set_minor_locator(
            matplotlib.dates.MonthLocator(bymonthday=15, tz=tz))
        ax.xaxis.set_minor_formatter(
            matplotlib.dates.DateFormatter('%m/%y', tz=tz))
        for tick in ax.xaxis.get_minor_ticks():
            tick.tick1line.set_markersize(0)
            tick.tick2line.set_markersize(0)
            tick.label1.set_horizontalalignment('center')
    else:
        # Major ticks at year boundaries.
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(tz=tz))
        ax.xaxis.set_major_formatter(
            matplotlib.dates.DateFormatter('%Y', tz=tz))

    ax.grid(b=True, which='major', color='w', linestyle=':', lw=1)

    # Draw program labels.
    y = 0.025
    opts = dict(fontsize='xx-large', fontweight='bold',
                horizontalalignment='center',
                xy=(0, 0), textcoords='axes fraction')
    ax.annotate('DARK', xytext=(0.2, y), color=program_color['DARK'], **opts)
    ax.annotate('GRAY', xytext=(0.5, y), color=program_color['GRAY'], **opts)
    ax.annotate(
        'BRIGHT', xytext=(0.8, y), color=program_color['BRIGHT'], **opts)

    plt.tight_layout()
    if save:
        plt.savefig(save)

    return fig, ax
