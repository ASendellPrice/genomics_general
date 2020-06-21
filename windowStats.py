#!/usr/bin/env python

import argparse
import sys
import gzip
import numpy as np

import genomics

#def nanmin(numbers):
    #try: return numbers[i,:][nanMask[i,:]].min()
    #except: return np.NaN

#def nanmax(numbers):
    #try: return numbers[i,:][nanMask[i,:]].max()
    #except: return np.NaN

####################################################################################################################

parser = argparse.ArgumentParser()

parser.add_argument("--windType", help="Type of windows to make", action = "store", choices = ("sites","coordinate","predefined"), default = "coordinate")
parser.add_argument("-w", "--windSize", help="Window size in bases", type=int, action = "store", required = False, metavar="sites")
parser.add_argument("-s", "--stepSize", help="Step size for sliding window", type=int, action = "store", required = False, metavar="sites")
parser.add_argument("-m", "--minSites", help="Minumum good sites per window", type=int, action = "store", required = False, metavar="sites", default = 1)
parser.add_argument("-O", "--overlap", help="Overlap for sites sliding window", type=int, action = "store", required = False, metavar="sites")
parser.add_argument("-D", "--maxDist", help="Maximum span distance for sites window", type=int, action = "store", required = False)
parser.add_argument("--windCoords", help="Window coordinates file (scaffold start end)", required = False)

parser.add_argument("-i", "--inFile", help="Input genotypes file", required = False)
parser.add_argument("-o", "--outFile", help="Results file", required = False)

parser.add_argument("--columns", help="Columns to analyse, separated by spaces", required = False, nargs="+")

parser.add_argument("--exclude", help="File of scaffolds to exclude", required = False)
parser.add_argument("--include", help="File of scaffolds to analyse", required = False)

parser.add_argument("--verbose", help="Verbose output", action="store_true")
parser.add_argument("--writeFailedWindows", help="Write output even for windows with too few sites.", action="store_true")

args = parser.parse_args()

#window parameters
windType = args.windType

if args.windType == "coordinate":
    assert args.windSize, "Window size must be provided."
    windSize = args.windSize
    stepSize = args.stepSize
    if not stepSize: stepSize = windSize
    assert not args.overlap, "Overlap does not apply to coordinate windows. Use --stepSize instead."
    assert not args.maxDist, "Maximum distance only applies to sites windows."

elif args.windType == "sites":
    assert args.windSize, "Window size (number of sites) must be provided."
    windSize = args.windSize
    overlap = args.overlap
    if not overlap: overlap = 0
    maxDist = args.maxDist
    if not maxDist: maxDist = np.inf
    assert not args.stepSize, "Step size only applies to coordinate windows. Use --overlap instead."
else:
    assert args.windCoords, "Please provide a file of window coordinates."
    assert not args.overlap, "Overlap does not apply for predefined windows."
    assert not args.maxDist, "Maximum does not apply for predefined windows."
    assert not args.stepSize,"Step size does not apply for predefined windows."
    assert not args.include,"You cannot only include specific scaffolds if using predefined windows."
    assert not args.exclude,"You cannot exclude specific scaffolds if using predefined windows."
    with open(args.windCoords,"r") as wc: windCoords = tuple([(x,int(y),int(z),) for x,y,z in [line.split()[:3] for line in wc]])

minSites = args.minSites
if not minSites: minSites = windSize

exclude = args.exclude
include = args.include

verbose = args.verbose


############################################################################################################################################

#open files

if args.inFile: inFile = gzip.open(args.inFile, "r") if args.inFile.endswith(".gz") else open(args.inFile, "r")
else: inFile = sys.stdin

if args.outFile: outFile = gzip.open(args.outFile, "w") if args.ourFile.endswith(".gz") else open(args.outFile, "w")
else: outFile = sys.stdout

outFile.write("scaffold,start,end,mid,sites")

############################################################################################################################################


#scafs to exclude

if exclude:
    scafsFile = open(exclude, "rU")
    scafsToExclude = [line.rstrip() for line in scafsFile.readlines()]
    print >> sys.stderr, len(scafsToExclude), "scaffolds will be excluded."
    scafsFile.close()
else:
    scafsToExclude = None

if include:
    scafsFile = open(include, "rU")
    scafsToInclude = [line.rstrip() for line in scafsFile.readlines()]
    print >> sys.stderr, len(scafsToInclude), "scaffolds will be analysed."
    scafsFile.close()
else:
    scafsToInclude = None


##########################################################################################################

#get windows and analyse
if windType == "coordinate": windowGenerator = genomics.slidingCoordWindows(inFile, windSize, stepSize,
                                                                            args.columns,
                                                                            include = scafsToInclude,
                                                                            exclude = scafsToExclude)
elif windType == "sites": windowGenerator = genomics.slidingSitesWindows(inFile, windSize, overlap,
                                                                         maxDist, minSites, args.columns,
                                                                         include = scafsToInclude,
                                                                         exclude = scafsToExclude)
else: windowGenerator = genomics.predefinedCoordWindows(inFile, windCoords, args.columns)


n=0

for window in windowGenerator:
    #if its the first window, get the headings and write
    if n == 0:
        for name in window.names:
            outFile.write(","+",".join([name + "_mean",name + "_median", name + "_min", name + "_max", name + "_sd", name + "_sum"]))
        outFile.write("\n")
    
    if windType == "coordinate" or windType == "predefined":
        scaf,start,end,mid,sites = (window.scaffold, window.limits[0], window.limits[1], window.midPos(),window.seqLen())
    else: scaf,start,end,mid,sites = (window.scaffold, window.firstPos(), window.lastPos(),window.midPos(),window.seqLen())
    
    outFile.write(",".join([scaf,str(start),str(end),str(mid),str(sites)]) + ",")
    
    if sites >= minSites:
        numDict = window.seqDict()
        numbers = np.array([numDict[name] for name in window.names], dtype = "float")
        nanMask = ~np.isnan(numbers)
        
        outFile.write(",".join([",".join([str(x) for x in [numbers[i,:][nanMask[i,:]].mean(),
                                                           np.median(numbers[i,:][nanMask[i,:]]),
                                                           np.min(numbers[i,:][nanMask[i,:]]),
                                                           np.max(numbers[i,:][nanMask[i,:]]),
                                                           np.std(numbers[i,:][nanMask[i,:]]),
                                                           np.sum(numbers[i,:][nanMask[i,:]])]]) for i in range(window.n)]))
    
    else: outFile.write(",".join([",".join([str(np.NaN)]*5) for i in range(window.n)]))

    outFile.write("\n")
    
    n+=1
    
    if n%100 == 0: sys.stderr.write(str(n) + " windows analysed...\n")

sys.exit()



