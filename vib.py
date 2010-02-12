#!/usr/bin/python
"""
  Module for calculating the frequencies of a system. The main routine is
  vibmodes(atoms, func, delta = 0.01, p_map = ps_map  , direction = 'central', alsovec = False)

  atoms: atomic system to look at, the position of it has to be set (it will be
  the place where the frequencies are calculated)

  func is the function which gives the gradients of the atom object at an given
  position x

  delta and direction are values of the derivatef function used to build up
  the hessian matrix direction = 'central' is highly recommended, delta gives
  the size of the steps taken to approximate the curvature

  p_map says how the different calculations needed for the numerical approximating
  the hessian are calculated, if it is a parallel map function this actions will be
  calculated in parallel, as default it is set to a function of the paramap module, which
  runs every calculation on its own process

  There is also inlcuded  the calculating of a
  numerical derivative (a hessian if the target function is the gradient)
  of a function, by using one of the map functions of paramap.py
  for the running of all the needed jobs.

  Test of the Module:

  First test the derivates of a function

       >>> def g(x):
       ...     return [ 2 * x[0] * x[1] * x[2]  , x[1]**2 , x[2] ]


       >>> hessian = derivatef(g, [1.0, 2.0, 1.0],direction = 'forward' )
       >>> print hessian
       [[ 4.    0.    0.  ]
        [ 2.    4.01  0.  ]
        [ 4.    0.    1.  ]]

       >>> hessian = derivatef(g, [1.0, 2.0, 1.0] )
       >>> print hessian
       [[ 4.  0.  0.]
        [ 2.  4.  0.]
        [ 4.  0.  1.]]

       >>> hessian = derivatef(g, [1.0, 2.0, 1.0],direction = 'backward' )
       >>> print hessian
       [[ 4.   -0.   -0.  ]
        [ 2.    3.99 -0.  ]
        [ 4.   -0.    1.  ]]


Ar4 Cluster as first simple atomic/molecule test system with
  LennardJones-potential.

    >>> from ase import Atoms

  One equilibrium:

    >>> w=0.39685026
    >>> A = ([[ w,  w,  w],
    ...            [-w, -w,  w],
    ...            [ w, -w, -w],
    ...            [-w,  w, -w]])

    >>> ar4 = Atoms("Ar4", A)

  Define LJ-PES:

    >>> from qfunc import QFunc

    >>> pes = QFunc(Atoms("Ar4"))
    >>> fun = pes.fprime

  Calculate the vibration modes

    >>> vibmodes(ar4, fun)
    ====================================================
     Number  imag.   Energy in eV      Energy in cm^-1
    ----------------------------------------------------
      0       yes      0.0021796         17.5798776
      1       yes      0.0021796         17.5798776
      2       yes      0.0021796         17.5798776
      3       yes      0.0000000          0.0000058
      4       no       0.0000000          0.0000106
      5       no       0.0000000          0.0000141
      6       no       0.0773558        623.9162798
      7       no       0.0773558        623.9162798
      8       no       0.1094714        882.9459913
      9       no       0.1094714        882.9459913
     10       no       0.1094714        882.9459913
     11       no       0.1548129       1248.6494855
    ----------------------------------------------------


  second test System: N-N with EMT calculator

    >>> from ase.calculators.emt import EMT

    >>> n2 = Atoms('N2', [(0, 0, 0), (0, 0, 1.1)])

    >>> pes = QFunc(Atoms("N2"),EMT() )
    >>> fun = pes.fprime
    >>> vibmodes(n2, fun)
    ====================================================
     Number  imag.   Energy in eV      Energy in cm^-1
    ----------------------------------------------------
      0       yes      0.0398776        321.6345510
      1       yes      0.0398776        321.6345510
      2       yes      0.0000000          0.0000048
      3       no       0.0000000          0.0000000
      4       no       0.0000000          0.0000000
      5       no       0.2540363       2048.9398454
    ----------------------------------------------------


    >>> n2.set_positions([[  0.00000000e+00,   0.00000000e+00,  -1.48015778e-02],
    ...                   [  1.49425969e-19,   0.00000000e+00,   1.11480158e+00]])

    >>> vibmodes(n2, fun)
    ====================================================
     Number  imag.   Energy in eV      Energy in cm^-1
    ----------------------------------------------------
      0       no       0.0000000          0.0000001
      1       no       0.0000000          0.0000121
      2       no       0.0000000          0.0000294
      3       no       0.0016245         13.1023923
      4       no       0.0016245         13.1023923
      5       no       0.2327449       1877.2138914
    ----------------------------------------------------
"""
import numpy as np
from math import sqrt
import ase
import ase.units as units
from aof.paramap import pa_map, ps_map, td_map, pmap

def derivatef( g0, x0, delta = 0.01, p_map = ps_map  , direction = 'central' ):
    '''
    Derivates another function numerically,

    g is the function or a vector of them
    x0 is the geometry (as a list) on which the minimum
    should be found
    delta is the step size
    direction: central uses formula (f(r+d) - f(r-d)) / 2d
               forward            ( f(r+d) - f(r)) / d
               backward is forward with -d

    gives back the derivatives as a matrix
    nabla gi/ nabla x0j

    There are two possibilities tested as types for x which work: x is a list
    or x is an array, if it is an array, the isarray Flag will be set by the system
    and it will be made sure, that the input also gives arrays to the qc-calculators/functions

    The gradient/derivative given back can also be an array
    '''
    assert direction in ['central', 'forward', 'backward']

    if direction =='backward':
    # change sign of delta if other direction is wanted
         delta = -delta
    xs = []
    # find out how many geoemtry elements there are
    # different treatments for arrays, lists of single
    # elements
    # if x was an array, the system has to remember it
    # to converge x back for the function calculation
    try:
        (dirone, dirtwo) = x0.shape
        geolen = dirone * dirtwo
        isarray = True
    except AttributeError:
        isarray = False
        try:
           geolen = len(x0)
        except TypeError:
           geolen = 1
           x0 = [x0]

    def newgeo( xmidd, num, delta, plus, isarr):
        # makes a new element for the lists of
        # requiered geometries, considers
        # array treatment, and directions for the
        # displacement of the i'th element
        xwk = []
        if isarr:
            xwk.extend(xmidd.flatten())
        else:
            xwk.extend(xmidd)
        if plus:
            xwk[num] += delta
        else:
            xwk[num] -= delta
        if isarr:
            xwk = np.array(xwk)
            xwk = np.reshape(xwk,(dirone, dirtwo))
        return xwk

    # building up the list of wanted geometries
    # consider the different directions
    if direction == 'central':
        # two inputs per geometry values
        # one in each direction
        for  i in range(0, geolen):
            xwork = newgeo(x0, i, delta, True, isarray )
            xs.append(xwork)
            xwork = newgeo(x0, i, delta, False, isarray )
            xs.append(xwork)
    else:
        # first for the middle geometry the value is
        # needed
        xs.append(x0)
        # for the rest only one per geometry
        for  i in range(0, geolen):
            xwork = newgeo(x0, i, delta, True, isarray )
            xs.append(xwork)

    # calculation of the functionvalues for all the geometries
    # at the same time
    g1 = p_map(g0, xs)
    # now it is possible to find out, how big g1 is
    # g1 may be an array (then we want the total length
    # not only in one direction
    try:
        derlen = len(g1[0].flatten())
    except AttributeError:
        derlen = len(g1[0])

    # deriv is the matrix with the derivatives
    # for g = deriv * geo
    deriv = np.zeros([geolen, derlen])

    # again the direction makes a difference
    # compare the formulas given above
    if direction == 'central':
        for i in range(0, geolen):
        # alternate the values for plus and minus are stored
        # if the g elements are arrays they have to be converged
            try:
                gplus = g1[2*i].flatten()
                gminus = g1[2*i+1].flatten()
            except AttributeError:
                gplus = g1[2*i]
                gminus = g1[2*i+1]

            for j in range(0,len(gplus)):
                 deriv[i,j] = ( gplus[j] - gminus[j]) / (2 * delta)
    else:
        # first one is the middle one, then the others in a line
        gmiddle = g1[0]
        # if gmiddle is an array:
        try:
            gmiddle = gmiddle.flatten()
        except AttributeError:
            pass

        for i, gval  in enumerate(g1[1:]):
            # if g is an array
            try:
                 gval = gval.flatten()
            except AttributeError:
                 pass

            for j in range(0,len(gval)):
                 deriv[i,j] = (gval[j] - gmiddle[j]) / delta
    return deriv

def vibmodes(atoms, func, delta = 0.01, p_map = pa_map, direction = 'central', alsovec = False):
     """
     calculates the vibration modes in harmonic approximation

     atoms is the atom system (ase.atoms) with positions set to the geometry, on which the
     frequencies are wanted

     func should do the gradient call on a given geometry

     if p_map is choosen as a parallel variant, all gradient calculations will be performed
     in parallel
     direction = 'central' should be the most accurate one but 'forward'/'backward' needs 
     fewer calculations all together (but the results may be really much worse, compare the results
     from the derivatef tests in the doctests.
     delta is the defaultvalue for delta in the derivatef function

     alsovec says that not only the frequencies of the mode but also the eigenvectors are 
     wanted
     """

     # define the place where the calculation should run
     xcenter = atoms.get_positions()
     # the derivatives are needed
     hessian = derivatef( func, xcenter, delta = delta, p_map = p_map, direction = direction )
     # make sure that the hessian is hermitian:
     hessian = 0.5 * (hessian + hessian.T)

     # include the mass elements
     mass1 = atoms.get_masses()
     massvec = np.repeat(mass1**-0.5, 3)
     eigvalues, eigvectors = np.linalg.eigh(massvec.T * hessian * massvec)

     # scale eigenvalues in different units:
     # E = hbar * omega [eV] = hvar * [1/s]
     # omega = sqrt(H /m), [H] = [kJ/Ang^2] , [m] = [amu], [omega] = [1/s] = [ J/m^2 /kg]
     scalfact = units._hbar * 1e10 / units.Ang * sqrt( units.kJ /( units._amu * 1000 ) )
     modeenerg =  scalfact *  eigvalues.astype(complex)**0.5
     modeincm  = modeenerg * units._e / units._c / units._hplanck * 0.01
     print "===================================================="
     print " Number  imag.   Energy in eV      Energy in cm^-1"
     print "----------------------------------------------------"
     for i, mode_e  in enumerate(modeenerg):
           if mode_e.imag != 0:
               print "%3d       yes     %10.7f       %12.7f" % (i,  mode_e.imag, modeincm[i].imag)
           else:
               print "%3d       no      %10.7f       %12.7f" % (i,  mode_e.real, modeincm[i].real)
     print "----------------------------------------------------"

     if (alsovec):
          print "The corresponding eigenvectors are:"
          print "Number   Vector"
          for i, mode_e  in enumerate(modeenerg):
               print "%3d     " % i, eigvectors[i]
          print "----------------------------------------------------"

# python vib.py [-v]:
if __name__ == "__main__":
    import doctest
    doctest.testmod()

