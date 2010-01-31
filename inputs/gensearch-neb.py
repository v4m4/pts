#!/usr/bin/env python

import sys
import os
import aof
from aof.common import file2str
import ase

name, params_file, mol_strings, init_state_vec = aof.setup(sys.argv)

# bring in custom parameters parameters
exec(file2str(params_file))

# set up some objects
mi          = aof.MolInterface(mol_strings, params)
calc_man    = aof.CalcManager(mi, procs_tuple)

# setup searcher i.e. String or NEB
if init_state_vec == None:
    init_state_vec = mi.reagent_coords

"""CoS = aof.searcher.GrowingString(init_state_vec, 
          calc_man, 
          beads_count,
          growing=growing,
          parallel=True)"""

CoS = aof.searcher.NEB(mi.reagent_coords, 
          calc_man, 
          spr_const,
          beads_count,
          parallel=True)


# callback function
def cb(x, tol=0.01):
    return aof.generic_callback(x, mi, CoS, params, tol=tol)

runopt = lambda: aof.runopt(opt_type, CoS, tol, maxit, cb, maxstep=0.2)

# main optimisation loop
cb(CoS)
print runopt()

# get best estimate(s) of TS from band/string
tss = CoS.ts_estims(mode='splines')

# print cartesian coordinates of all transition states that were found
print "Dumping located transition states"
for ts in tss:
    e, v = ts
    cs = mi.build_coord_sys(v)
    print cs.xyz_str()
