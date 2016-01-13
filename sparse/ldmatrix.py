from __future__ import print_function, division
import numpy as np
import scipy.sparse as sps
import scipy.linalg as spl
from pysnptools.util import IntRangeSet
from pyutils import iter as it


class LdMatrix(object):
    # bandwidth will get adjusted down to the nearest odd number, and other
    # parts of the class assume that bandwidth is odd
    def __init__(self, d, indivs, bandwidth, snpset_irs=None, output=True):
        if snpset_irs is None:
            snpset_irs = IntRangeSet((0, d.M))
        bandwidth = bandwidth+1
        self.bandwidth = 2*int(bandwidth/2)+1
        self.indivs = indivs
        lil_cov = sps.lil_matrix((d.M, d.M))
        def compute_cov_for_slice(s):
            indices = IntRangeSet((s[0] if s[0] == 0 else s[0] + int(bandwidth/2),
                s[1] if s[1] == d.M else s[1] - int(bandwidth/2)))
            indices = indices & snpset_irs

            if indices.isempty: # if there are no indices to analyze then we can move on
                return
            print(s)
            slice_genotypes = d.get_standardized_genotypes(s, indivs=indivs)
            snpset_relative_to_slice = IntRangeSet([
                (x-s[0],y-s[0]) for x,y in snpset_irs.ranges()])

            def compute_cov_for_snp(m):
                # we just compute the numbers needed for the top trianglular half
                # of the LD matrix, then we symmetrize the matrix. (commented line is old)
                # start = max(0, m - int(bandwidth/2))
                start = m
                end = min(slice_genotypes.shape[1], m + int(bandwidth/2))

                window_indices = IntRangeSet((start, end)) & snpset_relative_to_slice
                window = slice_genotypes[:, window_indices]

                cov_to_snps_in_window = slice_genotypes[:,m].T.dot(window) / len(indivs)
                cov_to_snps_in_window[0] /= 2 # since we're going to symmetrize later

                target_indices = IntRangeSet((s[0] + start, s[0] + end)) & snpset_irs
                lil_cov[s[0] + m, target_indices] = cov_to_snps_in_window
            map(compute_cov_for_snp,
                    it.show_progress([x - s[0] for x in indices]))

        map(compute_cov_for_slice,
                d.slices(buffer_size=int(bandwidth/2)))

        from time import time
        t0 = time()
        if output: print('starting symmetrization and conversion to csr')
        self.covcsr = lil_cov.tocsr()
        self.covcsr = self.covcsr + self.covcsr.T
        if output: print('took time:', time() - t0)

    # One of the two functions below doesn't work
    # def restrict_to(self, subset_irs):
    #     complement = IntRangeSet([(0,self.cov.shape[1])]) - subset_irs
    #     for r in complement.ranges():
    #         self.zero_out_rows_and_cols(r)

    # def zero_out_rows_and_cols(self, r):
    #     # zero out rows first
    #     self.cov.data[:,r[0]:r[1]] = 0

    #     # zero out what's left in column space
    #     for n, j in enumerate(range(max(r[0] - int(self.bandwidth/2), 0), r[0])):
    #         for i in range(n+1):
    #             # print(i,j)
    #             self.cov.data[i,j] = 0

    #     for n, j in enumerate(
    #             range(min(r[1] + int(self.bandwidth/2), self.cov.shape[1]), r[1], -1)):
    #         for i in range(n+1):
    #             # print(-i-1,j-1)
    #             self.cov.data[-i-1,j-1] = 0

    # the following two functions modify the data in the scipy.sparse.dia_matrix
    # in order to fit it into the format of scipy.linalg.solve_banded since, unbelievably,
    # the two have different formats
    def __to_sbformat(self):
        for i in range(self.covdia.data.shape[0]):
            self.covdia.data[i] = np.roll(self.covdia.data[i], -self.covdia.offsets[i])

    def __from_sbformat(self):
        for i in range(self.covdia.data.shape[0]):
            self.covdia.data[i] = np.roll(self.covdia.data[i], self.covdia.offsets[i])


    # linear algebra that we need to do efficiently
    def solve_banded(self, b):
        from time import time
        print('starting conversion to diagonal')
        self.covdia = self.covcsr.todia()
        print(time() - t0, 'done')
        self.__to_sbformat()
        result = spl.solve_banded((-self.covdia.offsets[0], self.covdia.offsets[-1]),
                self.covdia.data,
                b)
        self.__from_sbformat()
        return result

    def add_ridge(self, Lambda):
        self.covcsr += Lambda * sps.eye(d.M)


if __name__ == '__main__':
    from primitives import Dataset, GenomicSubset, SnpSubset
    import copy
    from time import time
    import argparse
    np.random.seed(0)
    parser = argparse.ArgumentParser()
    parser.add_argument('--M', type=int, required=True, help='the number of SNPs to use')
    parser.add_argument('-check_dense', action='store_true', default=False)
    args = parser.parse_args()

    d = Dataset('GERA', forced_M=args.M)
    indivs = d.random_indivs(200)

    t0 = time()
    R = LdMatrix(d, indivs, 200)
    R.add_ridge(0.05)
    print('computing R took', time() - t0)
    print('shape of R is:', R.covcsr.shape)

    tiny = GenomicSubset('50')
    tiny = SnpSubset(tiny, d.snp_coords())
    RA = LdMatrix(d, indivs, 200, snpset_irs=tiny.irs, output=False)
    b = np.random.randn(d.M)

    # check inverse computation
    t0 = time()
    Rinvb = R.solve_banded(b)
    print('R^{-1}b took', time() - t0)
    if args.check_dense:
        Rinvb_dense = np.linalg.solve(R.covcsr.toarray(), b)
        print('R^{-1}b behaves well:', np.allclose(Rinvb, Rinvb_dense))

    t0 = time()
    TrRRA = np.sum(R.covcsr.dot(RA.covcsr).diagonal())
    print('Tr(R*RA) took', time() - t0)
    if args.check_dense:
        TrRRA_dense = np.sum(R.covcsr.toarray() * RA.covcsr.toarray())
        print('Tr(R*RA) behaves well:', np.allclose(TrRRA, TrRRA_dense))
