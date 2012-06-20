"""This module defines an ASE interface to Gaussian.
"""

import os
import time
import subprocess
import logging
import glob
import shutil


import numpy

from ase.data import chemical_symbols

# this will break *standalone* comaptibility with ASE 
import pts.common as common

lg = logging.getLogger("pts.gaussian")

class Gaussian:
    """Class for doing Gaussian calculations."""
    def __init__(self, jobname="gaussjob", 
            method="HF", 
            basis="3-21G", 
            gau_command="g03", 
            charge=0, 
            mult=1,
            nprocs=1,
            mem=None,
            add_input=None,
            chkpoint=None):

        """Construct Gaussian-calculator object.

        Parameters
        ==========
        jobname: str
            Prefix to use for filenames

        method: str, e.g. b3lyp, ROHF, etc.
        basis:  str, e.g. 6-31G(d)
            level of theory string is formed from method/basis

        gau_command: str
            command to run gaussian, e.g. g03, g98, etc.

        nprocs: int
            number of processors to use (shared memory)

        add_input: str
            if specified the content of the file given as add_input
            will be used to extend the input file *.com
            It will be put after the blank line follwing the geometry
            data. Be aware that it will add the text in the same form it
            will be found in the add_input file.

        chkpoint: str
            if specified, an initial checkpoint file to read a guess in from.
            Note: it's probably possible to confuse the driver by supplying a 
            checkpoint for a significantly different structure.
        
        """
        
        self.jobname = jobname
        self.method = method
        self.basis = basis
        self.charge = charge
        self.mult = mult
        self.mem = mem

        self.gau_command = gau_command
        self.nprocs = nprocs
        assert nprocs > 0
        assert type(nprocs) == int


        if add_input == None:
            self.inputstring = None
        else:
            file = open(add_input, "r")
            self.inputstring = file.read()
            file.close()
        # see function generate_header() also
        self.max_aggression = 1
        self.runs = 0

        self.chkpoint = None

    def set_chk(self, chkpoint):
        self.chkpoint = chkpoint
       
    def set_nprocs(self, nprocs):
        assert nprocs > 0
        self.nprocs = nprocs

    def set_mem(self, mem):
        self.mem = mem

    def set(self, **kwargs):
        # FIXME: add all keywords
        for key in kwargs:
            if key == 'chkpoint':
                self.set_chk(kwargs[key])
            elif key == 'nprocs':
                self.set_nprocs(kwargs[key])
            elif key == "mem":
                self.set_mem(kwargs[key])
            else:
                raise GaussDriverError(key + " not a valid key")

    def update(self, atoms):
        """If Necessary, runs calculation."""

        # test whether atoms object has changed
        if (self.runs < 1 or
            len(self.numbers) != len(atoms) or
            (self.numbers != atoms.get_atomic_numbers()).any()):
            self.initialize(atoms)
            self.calculate(atoms)

        # test whether positions of atoms have changed
        elif (self.positions != atoms.get_positions()).any():
            self.calculate(atoms)

    def generate_header(self, aggression=0):

        params = []
        chkfile = self.jobname + ".chk"
        if aggression == 0:

            if self.runs > 0:
                params.append("guess=read")
            elif self.chkpoint != None:
                chkfile = self.chkpoint
                print "chkfile", chkfile
                os.system('ls *.chk')
                if os.path.isfile(chkfile):
                    params.append("guess=read")

        elif aggression == 1:
            print "Gaussian: aggression =", aggression
            params.append("scf=qc")
        else:
            raise GaussDriverError("Unsupported aggression level: " + str(aggression))

        params_str = ' '.join(params)

        if self.mem == None:
            job_header = "%%chk=%s\n%%nprocs=%d\n# %s/%s %s force\n\nGenerated by ASE Gaussian driver\n\n%d %d\n" \
                % (chkfile, self.nprocs, self.method, self.basis, params_str, self.charge, self.mult)
        else:
            job_header = "%%chk=%s\n%%nprocs=%d\n%%mem=%s\n# %s/%s %s force\n\nGenerated by ASE Gaussian driver\n\n%d %d\n" \
                % (chkfile, self.nprocs,self.mem, self.method, self.basis, params_str, self.charge, self.mult)

        return job_header

    def initialize(self, atoms):
        self.numbers = atoms.get_atomic_numbers().copy()
        self.runs = 0
        self.converged = False
        
    def get_potential_energy(self, atoms, force_consistent=False):
        self.update(atoms)

        return self.__e

    def get_forces(self, atoms):
        self.update(atoms)
        return self.__forces.copy()
    
    def get_stress(self, atoms):
        raise NotImplementedError

    def calculate(self, atoms):
        self.positions = atoms.get_positions().copy()

        cwd = os.getcwd()
        __, self.jobname = cwd.rsplit("/",1)
        inputfile = cwd + "/" +self.jobname + ".com"

        # first remove old output if existant, as there should'nt be any results using
        # an old version, we have problems that we might wait for a result to come back,
        # this ensures that it is really the result from the current run then
        if os.path.isfile(self.jobname + ".log"):
            os.remove(self.jobname + ".log")

        list = ['%-2s %22.15f %22.15f %22.15f' % (s, x, y, z) for s, (x, y, z) in zip(atoms.get_chemical_symbols(), atoms.get_positions())]
        geom_str = '\n'.join(list) + '\n\n'

        parse_result = None
        ag = 0
        while parse_result == None:
            if ag > self.max_aggression:
                raise GaussDriverError("Unable to converge SCF for geometry and settings in " + inputfile)

            job_str = self.generate_header(aggression=ag) + geom_str
            f = open(inputfile, "w")
            f.write(job_str)
            if not self.inputstring == None:
                 f.write(self.inputstring)
            f.close()

            # pass as argument only the jobname, thus allows to identify the gaussianjob
            # the current proccessor wants to run
            args = [self.gau_command, self.jobname]
            command = " ".join(args)

            lg.info("Running Gau job " + command + " in " + os.getcwd())
            #FIXME: what is the major difference between the two ways of using it?
            #p = subprocess.Popen(command, shell=True)
            #sts = os.waitpid(p.pid, 0)
            p = os.system(command)

            #FIXME: same problem as with ParaGauss. Somehow we need to pass time here,
            # before the results are back, prefer reading to trash over sleeping through
            os.system("ls > /dev/null")
            parse_result = self.read(cwd)

            # next attempt will have higher aggression
            ag += 1

        self.__e, self.__forces = parse_result

        self.converged = True
        self.runs += 1
        
    def read(self, cwd):
        """Read results from Gaussian's text-output file."""
        logfilename = cwd + "/" + self.jobname + '.log'
#        os.system('cp %s ~/%s' % (logfilename, logfilename + str(time.time()))) # HACK for some data gathering
        print "GAUSS_DIRS: Working Dir:", os.getcwd(), "logfile path:", logfilename
        logfile = open(logfilename, 'r')

        line = logfile.readline()

        forces = []
        e = None
        while line != '':
            if line.find("SCF Done") != -1:
                e = line.split()[4]
                e = float(e)
            elif line[37:43] == "Forces":
                header = logfile.readline()
                dashes = logfile.readline()
                line = logfile.readline()
                while line != dashes:
                    n,nuclear,Fx,Fy,Fz = line.split()
                    forces.append([float(Fx),float(Fy),float(Fz)])
                    line = logfile.readline()
            elif line.find("Convergence failure -- run terminated") >= 0 or \
                    line.find("The SCF is confused") >= 0:
                return None

            line = logfile.readline()

        if e == None or forces == []:
            raise GaussDriverError("File not parsed, check " + os.path.join(os.getcwd(), logfilename))

        forces = numpy.array(forces) * common.ANGSTROMS_TO_BOHRS * common.HARTREE_TO_ELECTRON_VOLTS
        e *= common.HARTREE_TO_ELECTRON_VOLTS
        return e, forces

class GaussDriverError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

def copy_chk_gaussian(dir):
    """Finds most recent .chk file in |dir| and copies it to the current 
    directory.
    """
    name = "guess.chk"
    if dir == None:
        return
    print "Searching for .chk file in", dir
    if not os.path.exists(dir):
        lg.warn("Path " + dir + " not found")
        return
    chks = glob.glob(dir + "/*.chk")
    if len(chks) == 0:
        lg.warn("No files " + dir + "/*.chk found")
        return
    if len(chks) > 1:
        lg.warn("More than 1 " + dir + "/*.chk files found, using most recent one")

    chks = [(os.path.getmtime(c), c) for c in chks]
    chks.sort()

    file = chks[-1][1]
    shutil.copy(file, "./" + name)
    lg.info("Created " + name + " to use for guess")
    lg.info("CWD was " + os.getcwd())
    return name
 
def pre_calc_function_g03(calc, data):
    """Function to run just before a calculation is run (i.e. a get_energy() 
    or get_potential_energy() call is made) to perform any final tasks.
    
    Copy chk file to current dir and set number of processors flag.
    """

    assert isinstance(calc, Gaussian), "Using pre_calc_function_g03 for some other calculator: " + str(calc)
    item = data['item']
    lg.info("Running pre_calc_function_g03, data: " + str(data))
#    chkpoint_dir = item.job.prev_calc_dir

    n = len(item.range_global)
    calc.set(nprocs=n)

#    filename = copy_chk_gaussian(chkpoint_dir)
    chkpoint = item.job_name + '.chk'
    calc.set(chkpoint=chkpoint)






