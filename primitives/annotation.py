from __future__ import print_function, division
import numpy as np
import pandas as pd
import paths

class Annotation(object):
    def __init__(self, name, path=paths.annotations, signed=True):
        self.stem = path+name
        self.signed = signed
        self.__df = {}

    @property
    def start_colindex(self):
        return 6 if self.signed else 4

    def filestem(self, chrnum=''):
        return '{}{}'.format(self.stem, self.chrnum)
    def filename(self, chrnum):
        if self.signed:
            return self.filestem(chrnum) + '.sannot.gz'
        else:
            return self.filestem(chrnum) + '.annot.gz'
    def sqnorm_filename(self, chrnum):
        return self.filestem(chrnum) + '.sqnorm'
    def size_filename(self, chrnum):
        return self.filestem(chrnum) + '.M'

    def df(self, chrnum):
        if chrnum not in self.__df:
            self.__df[chrnum] = pd.read_csv(self.filename(chrnum),
                    compression='gzip', header=0, sep='\t')
        return self.__df[chrnum]

    def names(self, chrnum):
        return self.df(chrnum).columns.values[self.start_colindex :]

    def sqnorms(self, chrnum):
        return pd.read_csv(self.sqnorm_filename(chrnum), names=self.names(chrnum), sep='\t')
    def sizes(self, chrnum):
        return pd.read_csv(self.size_filename(chrnum), names=self.names(chrnum), sep='\t')


if __name__ == '__main__':
    a = Annotation('1000G3.wim5u/mock/')
    print(a.names(22))
    print(a.df(22))
    print(a.sqnorms(22))
    print(a.sizes(22))