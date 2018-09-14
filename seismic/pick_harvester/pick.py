#!/bin/env python
"""
Description:
    Harvests picks from ASDF data-sets in parallel
References:

CreationDate:   13/09/18
Developer:      rakib.hassan@ga.gov.au

Revision History:
    LastUpdate:     13/09/18   RH
    LastUpdate:     dd/mm/yyyy  Who     Optional description
"""

from mpi4py import MPI
import glob, os, sys
from os.path import join, exists
from collections import defaultdict

from math import radians, cos, sin, asin, sqrt
import numpy as np
import scipy
from scipy.spatial import cKDTree

import xcorqc
from obspy import Stream, Trace, UTCDateTime
import pyasdf
import json
import fnmatch
import operator

from ASDFdatabase.FederatedASDFDataSet import FederatedASDFDataSet

import click
from obspy import UTCDateTime, read_events, read_inventory
from obspy.taup.taup_geo import calc_dist
from obspy.clients.iris import Client as IrisClient
from obspy.clients.fdsn import Client
from obspy.taup import TauPyModel
from obspy.signal.trigger import trigger_onset, z_detect, classic_sta_lta, recursive_sta_lta, ar_pick
from obspy.signal.rotate import rotate_ne_rt
from obspy.core.event import Pick, CreationInfo, WaveformStreamID, ResourceIdentifier, Arrival, Event,\
     Origin, Arrival, OriginQuality, Magnitude, Comment

from utils import EventParser

def recursive_glob(treeroot, pattern):
    results = []
    for base, dirs, files in os.walk(treeroot):
        goodfiles = fnmatch.filter(files, pattern)
        results.extend(os.path.join(base, f) for f in goodfiles)
    return results
# end func

def split_list(lst, npartitions):
    result = defaultdict(list)
    count = 0
    for iproc in np.arange(npartitions):
        for i in np.arange(np.divide(len(lst), npartitions)):
            result[iproc].append(lst[count])
            count += 1
    # end for
    for iproc in np.arange(np.mod(len(lst), npartitions)):
        result[iproc].append(lst[count])
        count += 1
    # end for

    return result
# end func

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('asdf-source', required=True,
                type=click.Path(exists=True))
@click.argument('event-folder', required=True,
                type=click.Path(exists=True))
@click.argument('output-path', required=True,
                type=click.Path(exists=True))
def process(asdf_source, event_folder, output_path):
    """
    ASDF_SOURCE: Text file containing a list of paths to ASDF files
    EVENT_FOLDER: Path to folder containing event files\n
    OUTPUT_PATH: Output folder \n
    """

    comm = MPI.COMM_WORLD
    nproc = comm.Get_size()
    rank = comm.Get_rank()
    proc_workload = None

    if(rank == 0):
        def outputConfigParameters():
            # output config parameters
            fn = 'pick.%s.cfg' % (UTCDateTime.now().strftime("%y-%m-%d.T%H.%M"))
            fn = os.path.join(output_path, fn)

            f = open(fn, 'w+')
            f.write('Parameters Values:\n\n')
            f.write('%25s\t\t: %s\n' % ('ASDF_SOURCE', asdf_source))
            f.write('%25s\t\t: %s\n' % ('EVENT_FOLDER', event_folder))
            f.write('%25s\t\t: %s\n' % ('OUTPUT_PATH', output_path))
            f.close()
        # end func

        outputConfigParameters()

        # retrieve list of all event xml files
        xml_files = recursive_glob(event_folder, '*.xml')

        proc_workload = split_list(xml_files, nproc)
    # end if

    # broadcast workload to all procs
    proc_workload = comm.bcast(proc_workload, root=0)

    print 'Rank %d: processing %d files'%(rank, len(proc_workload[rank]))

    fds = FederatedASDFDataSet(asdf_source, logger=None)
    # Magic numbers
    six_mins = 360
    proc_events_stations = []
    for fn in proc_workload[rank]:
        es = EventParser(fn).getEvents()
        for i, (eid, e) in enumerate(es.iteritems()):
            po = e.preferred_origin

            otime = po.utctime
            stations = fds.get_stations(otime - six_mins, otime + six_mins)
            stations_zch = [s for s in stations if 'Z' in s[3]] # only Z channels

            print 'Rank: %d, Event: %d: Found %d stations'%(rank, i, len(stations_zch))

            for s in stations_zch:
                proc_events_stations.append([[po] + s])
        # end for
    # end for

    proc_events_stations = comm.gather(proc_events_stations, root=0)

    if(rank==0):
        proc_events_stations_all = []
        [proc_events_stations_all.extend(el) for el in proc_events_stations]

        proc_events_stations = split_list(proc_events_stations_all, nproc)
    # end if

    proc_events_stations = comm.bcast(proc_events_stations, root=0)

    print 'Event-stations count on rank %d: %d'%(rank, len(proc_events_stations[rank]))
    del fds
# end func

if (__name__ == '__main__'):
    process()
# end if