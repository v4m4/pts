#!/usr/bin/env python
from ase.io import read as read_ase
from pts.common import file2str
import re

def read_geos_from_file(geom_files, format):
    """
    Read in geometries from ASE readable file
    returns one atoms object (with geometry of first minima set)
    and a list of geometries
    """
    res = [read_ase(st1, format = format) for st1 in geom_files]
    atom = res[0]
    geom = [r.get_positions() for r in res]
    return atom, geom

def read_zmt_from_file(zmat_file):
    """
    Read zmatrix from file
    """
    zmat_string = file2str(zmat_file)
    return read_zmt_from_string(zmat_string)

def read_zmt_from_string(zmat_string):
    """
    Read zmat out from a string, convert to easier to interprete results

    give back more results than really needed, to have it easier to use
    them later on

    OUTPUT: [<Name of Atoms>], [Connectivity matrix, format see ZMat input from zmat.py],
            [<variable numbers, with possible repitions>], how often a variable was used more than once,
            [<dihedral angles variable numbers>],
            (number of Cartesian coordinates covered with zmt, number of interal coordinates of zmt)

    Thus for example:
            (['Ar', 'Ar', 'Ar', 'Ar'], [(), (0,), (0, 1), (1, 0, 2)], [0, 0, 1, 0, -1, 2], 3, [2], (12, 6))

    >>> str1 = "H\\nO 1 ho1\\nH 2 ho2 1 hoh\\n"

    >>> str2 = "H\\nO 1 ho1\\nH 2 ho2 1 hoh\\n\\n"

    >>> strAr = 'Ar\\nAr 1 var1\\nAr 1 var2 2 var3\\n \\
    ...          Ar 2 var4 1 var5 3 var6\\n           \\
    ...          \\nvar1 = 1.0\\nvar2 = 1.0\\nvar3 = 1.0\\nvar4 = 1.0\\nvar5 = 1.0\\nvar6 = 1.0\\n'
    >>> strAr2 = 'Ar\\nAr 1 var1\\nAr 1 var2 2 var3\\nAr 2 var4 1 var5 3 var6\\n'
    >>> strAr3 = 'Ar\\nAr 1 var1\\nAr 1 var1 2 var2\\nAr 2 var1 1 -var2 3 var6\\n'


    # read in small H2O, no dihedrals in there
    >>> read_zmt_from_string(str1)
    (['H', 'O', 'H'], [(), (0,), (1, 0)], [1, 2, 3], 0, [], (9, 3))

    # test with an extra blankline
    >>> read_zmt_from_string(str2)
    (['H', 'O', 'H'], [(), (0,), (1, 0)], [1, 2, 3], 0, [], (9, 3))

    # A bit larger Argon Cluster
    >>> read_zmt_from_string(strAr2)
    (['Ar', 'Ar', 'Ar', 'Ar'], [(), (0,), (0, 1), (1, 0, 2)], [1, 2, 3, 4, 5, 6], 0, [5], (12, 6))

    # old format (with random set variables values to omit)
    >>> read_zmt_from_string(strAr)
    (['Ar', 'Ar', 'Ar', 'Ar'], [(), (0,), (0, 1), (1, 0, 2)], [1, 2, 3, 4, 5, 6], 0, [5], (12, 6))

    # reduce variables, set all length to the same value and have also the angles be their negative
    >>> read_zmt_from_string(strAr3)
    (['Ar', 'Ar', 'Ar', 'Ar'], [(), (0,), (0, 1), (1, 0, 2)], [1, 1, 2, 1, 0, 3], 3, [2], (12, 3))
    """

    lines = zmat_string.split("\n")

    # data to extract from the lines
    names = []
    matrix = []
    var_names = {}
    var_numbers = []
    multiplicity = 0
    nums_atom = 0
    dihedral_nums = []
    var_count = -1

    for line in lines:
        fields = line.split()
        if len(fields) == 0:
          # for consistency with older zmat inputs, they might end on an empty line
          # or have an empty line followed by some internal coordinate values
          break
        names.append(fields[0])
        nums_atom = nums_atom + 1
        # There are different line length possible
        # the matrix values are -1, because python starts with 0
        # but it is more convinient to count from atom 1
        if len(fields) == 1: # atom 1
            matrix.append(())
            vname_line = []
        elif len(fields) == 3: # atom 2
            matrix.append((int(fields[1])-1,))
            vname_line = [fields[2]]
        elif len(fields) == 5: # atom 3
            matrix.append((int(fields[1])-1, int(fields[3])-1,))
            vname_line = [fields[2], fields[4]]
        elif len(fields) == 7: # all other atoms
            matrix.append((int(fields[1])-1, int(fields[3])-1, int(fields[5])-1))
            vname_line = [fields[2], fields[4], fields[6]]
        else:
            print "ERROR: in reading the Z-Matrix"
            print "ERROR: line not understood:", line
            abort()

        # now check if there are some variables with multiplicity or if
        # some are dihedrals:
        for i, vname in enumerate(vname_line):
            num = 1
            if vname.startswith("-"):
               # allow setting of a variable to the minus of the
               # values by earlier appearance
               vname = vname[1:]
               num = -1

            if vname in var_names.keys():
                # we have this variable already
                multiplicity = multiplicity + 1
            else:
                var_count = var_count + 1
                var_names[vname] = var_count
                if i == 2: # i == 0 distance, i == 1 angle
                     dihedral_nums.append(var_count)

            # num takes care about inverse
            num = num * var_names[vname]
            # collect all variables but with numbers, not with the names
            var_numbers.append(num + 1)

    return names, matrix, var_numbers, multiplicity, dihedral_nums, (nums_atom*3, var_count + 1)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
