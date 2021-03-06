"""Script wrapper for running survey planning.

To run this script from the command line, use the ``surveyplan`` entry point
that is created when this package is installed, and should be in your shell
command search path.

Note that the fiber-assignment (FA) delay specified via --fa-delay encodes two related parameters: the FA delay (integer >= 0) and the FA cadence (d=daily, m=monthy, q=quarterly). See DESI-doc-3194 for details and the justification for the default "1q" setting.
"""
from __future__ import print_function, division, absolute_import

import argparse
import os
import datetime
import sys

import numpy as np

import astropy.time
import astropy.table

import desiutil.log

import desisurvey.ephem
import desisurvey.old.schedule
import desisurvey.plan
import desisurvey.utils
import desisurvey.config
import desisurvey.rules
import desisurvey.progress


def parse(options=None):
    """Parse command-line options for running survey planning.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose', action='store_true',
        help='display log messages with severity >= info')
    parser.add_argument('--debug', action='store_true',
        help='display log messages with severity >= debug (implies verbose)')
    parser.add_argument(
        '--create', action='store_true', help='create an initial plan')
    parser.add_argument(
        '--rules', metavar='YAML', default='rules.yaml',
        help='name of YAML file with observing priority rules')
    parser.add_argument(
        '--fa-delay', metavar='DELAY', type=str, default='1m',
        help='FA delay in days (7d), full moons (1m) or quarters (0q)')
    parser.add_argument(
        '--output-path', default=None, metavar='PATH',
        help='output path where output files should be written')
    parser.add_argument(
        '--config-file', default='config.yaml', metavar='CONFIG',
        help='input configuration file')

    if options is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(options)

    return args


def main(args):
    """Command-line driver for updating the survey plan.
    """
    # Check for a valid fa-delay value.
    if args.fa_delay[-1] not in ('d', 'm', 'q'):
        raise ValueError('fa-delay must have the form Nd, Nm or Nq.')
    fa_delay_type = args.fa_delay[-1]
    try:
        fa_delay = int(args.fa_delay[:-1])
    except ValueError:
        raise ValueError('invalid number in fa-delay.')
    if fa_delay < 0:
        raise ValueError('fa-delay value must be >= 0.')

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
    config = desisurvey.config.Configuration(file_name=args.config_file)
    if args.output_path is not None:
        config.set_output_path(args.output_path)

    # Load ephemerides.
    ephem = desisurvey.ephem.get_ephem()

    # Initialize scheduler.
    if not os.path.exists(config.get_path('scheduler.fits')):
        # Tabulate data used by the scheduler if necessary.
        desisurvey.old.schedule.initialize(ephem)
    scheduler = desisurvey.old.schedule.Scheduler()

    # Read priority rules.
    rules = desisurvey.rules.Rules(args.rules)

    if args.create:
        # Load initial design hour angles for each tile.
        design = astropy.table.Table.read(config.get_path('surveyinit.fits'))
        # Create an empty progress record.
        progress = desisurvey.progress.Progress()
        # Initialize the observing priorities.
        priorities = rules.apply(progress)
        # Create the initial plan.
        plan = desisurvey.plan.create(design['HA'], priorities)
        # Start the survey from scratch.
        start = config.first_day()
    else:
        # Load an existing plan and progress record.
        if not os.path.exists(config.get_path('plan.fits')):
            log.error('No plan.fits found in output path.')
            return -1
        if not os.path.exists(config.get_path('progress.fits')):
            log.error('No progress.fits found in output path.')
            return -1
        plan = astropy.table.Table.read(config.get_path('plan.fits'))
        progress = desisurvey.progress.Progress('progress.fits')
        # Start the new plan from the last observing date.
        with open(config.get_path('last_date.txt'), 'r') as f:
            start = desisurvey.utils.get_date(f.read().rstrip())

    num_complete, num_total, pct = progress.completed(as_tuple=True)

    # Already observed all tiles?
    if num_complete == num_total:
        log.info('All tiles observed!')
        # Return a shell exit code so scripts can detect this condition.
        sys.exit(9)

    # Reached end of the survey?
    if start >= config.last_day():
        log.info('Reached survey end date!')
        # Return a shell exit code so scripts can detect this condition.
        sys.exit(9)

    day_number = desisurvey.utils.day_number(start)
    log.info('Planning night[{0}] {1} with {2:.1f} / {3} ({4:.1f}%) completed.'
             .format(day_number, start, num_complete, num_total, pct))

    bookmarked = False
    if not args.create:

        # Update the priorities for the progress so far.
        new_priority = rules.apply(progress)
        changed_priority = (new_priority != plan['priority'])
        if np.any(changed_priority):
            changed_passes = np.unique(plan['pass'][changed_priority])
            log.info('Priorities changed in pass(es) {0}.'
                     .format(', '.join([str(p) for p in changed_passes])))
            plan['priority'] = new_priority
            bookmarked = True

        # Identify any new tiles that are available for fiber assignment.
        plan = desisurvey.plan.update_available(
            plan, progress, start, ephem, fa_delay, fa_delay_type)

        # Will update design HA assignments here...
        pass

    # Update the progress table for the new plan.
    ptable = progress._table
    new_cover = (ptable['covered'] < 0) & (plan['covered'] <= day_number)
    ptable['covered'][new_cover] = day_number
    new_avail = (ptable['available'] < 0) & plan['available']
    ptable['available'][new_avail] = day_number
    new_plan = (ptable['planned'] < 0) & (plan['priority'] > 0)
    ptable['planned'][new_plan] = day_number

    # Save updated progress.
    progress.save('progress.fits')

    # Save the plan.
    plan.write(config.get_path('plan.fits'), overwrite=True)
    if bookmarked:
        # Save a backup of the plan and progress at this point.
        plan.write(config.get_path('plan_{0}.fits'.format(start)))
        progress.save('progress_{0}.fits'.format(start))
