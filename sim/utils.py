from __future__ import print_function, division
import numpy as np
from pysnptools.snpreader import Bed
import hyperparams as hp

def get_standardized_genotypes(chrnum):
    genotypes = hp.dataset.genotypes_bedfile(chrnum).read()
    genotypes.standardize(); genotypes.standardize()
    return genotypes.val
