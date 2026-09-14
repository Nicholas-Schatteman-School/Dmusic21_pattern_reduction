from sys import argv, platform
from music21 import *
import random
import string
from statistics import mean
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import directed_hausdorff
import math

''' 
Old Version Starts Here
'''
# assign voices based on a reference group of notes to notes in the contig
    # start has a reference note for all of the voices
    # look at crawlScore for direction
def assignVoices(start, contig, dir):
    dest = [f[-1] if dir == "l" else f[0] for f in contig[2]]
    toAssign = [] # dest notes
    toConnect = [] # start notes
    assignedPairs = [[],[]] # keep track of bin,group pairs already assigned

    # populate toAssign with target notes
        # visited notes (groups already assigned) should be excluded and registered in assignedPairs
    for n in dest:
        if not len(n.groups) and not n.id in start:
            toAssign.append(n)  
        elif len(n.groups):
            assignedPairs[0].append(n)
            assignedPairs[1].append(n.groups[0])
    if not len(toAssign):# all notes assigned already
        return
    # populate toConnect with reference notes
        # visited notes (groups already assigned) are excluded
    for n in start:
        if n.groups[0] not in assignedPairs[1]:
            toConnect.append(n)

    # possible combinations of choices
    cost_matrix = [[interval.Interval(a, c).generic.undirected for a in toAssign] for c in toConnect]
    start_ind, dest_ind = linear_sum_assignment(cost_matrix)

    # assign voices to the correct fragments
    for i in range(len(start_ind)):
        voice = toConnect[start_ind[i]].groups[0]
        toAssign[dest_ind[i]].groups.append(voice)
    groupFragments(contig)

# score bfs
    # frontier: [(contig, direction, ref)]
        # should be initialized outside this function
    # assign notes bordering the contig given a reference group of voices
    # groupFragments
    # update ref voices to the most recent notes
def crawlScore(frontier, contigs, partdict):
    while len(frontier):
        item = frontier.pop(0)
        leftIndex = contigs.index(item[0]) - 1
        rightIndex = contigs.index(item[0]) + 1
        if item[1] == "m": # both directions (maxcontigs)
            if leftIndex >= 0:
                start = [t.element for t in item[0][0][0].startAndOverlapTimespans]
                assignVoices(start, contigs[leftIndex], "l")
                curr = [t.element for t in contigs[leftIndex][0][0].startAndOverlapTimespans]
                ref = [next(n for n in curr if n.groups[0] == s.groups[0]) if s.groups[0] in [n.groups[0] for n in curr] else s for s in start]
                frontier.append((contigs[leftIndex], "l", ref))
            if rightIndex < len(contigs):
                start = [t.element for t in item[0][0][-1].startAndOverlapTimespans]
                assignVoices(start, contigs[rightIndex], "r")
                curr = [t.element for t in contigs[rightIndex][0][-1].startAndOverlapTimespans]
                ref = [next(n for n in curr if n.groups[0] == s.groups[0]) if s.groups[0] in [n.groups[0] for n in curr] else s for s in start]
                frontier.append((contigs[rightIndex], "r", ref))
        elif item[1] == "l": # go left
            if leftIndex >= 0:
                assignVoices(ref, contigs[leftIndex], "l")
                curr = [t.element for t in contigs[leftIndex][0][0].startAndOverlapTimespans]
                ref = [next(n for n in curr if n.groups[0] == s.groups[0]) if s.groups[0] in [n.groups[0] for n in curr] else s for s in ref]
                frontier.append((contigs[leftIndex], "l", ref))
        elif item[1] == "r": # go right
            if rightIndex < len(contigs):
                assignVoices(ref, contigs[rightIndex], "r")
                curr = [t.element for t in contigs[rightIndex][0][-1].startAndOverlapTimespans]
                ref = [next(n for n in curr if n.groups[0] == s.groups[0]) if s.groups[0] in [n.groups[0] for n in curr] else s for s in ref]
                frontier.append((contigs[rightIndex], "r", ref))   



''' 
Current Version Starts Here
'''

# features: range of notes, average, start and last notes, length (for updating average)
# return dictionary with # fragments as keys: {voice: {fragment: val, feature1: val1, feature2: val2, ...}}
# arbitrary=false is for contigs where the fragments are expected to be already assigned
def getFeatures(contig, arbitrary=False):
    features = {}
    i = 0
    for fragment in contig[2]:
        if arbitrary:
            features[str(i)] = {"fragment": fragment}
            i += 1
        else:
            features[fragment[0].groups[0]] = {"fragment": fragment}

    for f in features:
        # range
        features[f]["min"] = int(min([n.pitch.ps for n in features[f]["fragment"]]))
        features[f]["max"] = int(max([n.pitch.ps for n in features[f]["fragment"]]))
        # # notes (for updating the average)
        features[f]["length"] = len(features[f]["fragment"])
        # average
        features[f]["average"] = mean([n.pitch.ps for n in features[f]["fragment"]])
        # first note
        features[f]["first note"] = features[f]["fragment"][0]
        # last note
        features[f]["last note"] = features[f]["fragment"][-1]
    return features

# update the features of voices with incoming features dictionary
# assuming that the features are not arbitrary and could not equal the total voices, match the voices
def updatePartFeatures(features, partdict):
    for v in features:
        ref = partdict[v]["features"]
        dict = features[v]
        if not len(ref):
            partdict[v]["features"] = dict
        else:
            # range
            ref["min"] = min(dict["min"], ref["min"])
            ref["max"] = max(dict["max"], ref["max"])
            # average
            ref["average"] = (ref["average"] * ref["length"] + sum([n.pitch.ps for n in dict["fragment"]])) / (ref["length"] + dict["length"])
            # # notes
            ref["length"] += dict["length"]
            # last note
            ref["last note"] = dict["last note"]

# get distance between feature vectors
#   connecting notes (s[last], d[first])
#   average
#   range
def distanceWithFeatures(s, d):
    # weights for the distance vector
    w1, w2, w3 = (1.0, 1.0, 1.0)

    # use directed hausdorff to compare the ranges
    # dist = [interval.Interval(s["last note"], d["first note"]).generic.undirected, abs(s["average"] - d["average"]), directed_hausdorff([[p] for p in range(s["min"], s["max"] + 1)], [[p] for p in range(d["min"], d["max"] + 1)])[0]]

    # for comparing ranges, take the area that d falls outside s 
    dist = [interval.Interval(s["last note"], d["first note"]).generic.undirected, abs(s["average"] - d["average"]), s["min"] - min(s["min"], d["min"]) + max(s["max"], d["max"]) - s["max"]]

    # calculate distance (euclidean for now)
    # TODO: change to something relative like cosine or normalize vector somehow 
    return math.sqrt((w1 * dist[0])**2 + (w2 * dist[1])**2 + (w3 * dist[2])**2)

# assign voices in partdict to the fragments in contig
def assignVoicesWithFeatures(contig, partdict):
    # get features for both
    start = {k: partdict[k]["features"] for k in partdict}
    dest = getFeatures(contig, True)

    # assigned fragments (already connected previously, or part of a held note) should be excluded
    for k in dest.copy():
        refNote = dest[k]["fragment"][0]
        if len(refNote.groups):
            del dest[k]
            start.pop(refNote.groups[0])
    if not len(dest):# all notes assigned already
        return

    # assignment problem
    # cost matrix (start x dest)
    start_array = [[k, start[k]] for k in start]
    dest_array = [dest[k] for k in dest]
    cost_matrix = [[distanceWithFeatures(s[1], d) for d in dest_array] for s in start_array]
    start_ind, dest_ind = linear_sum_assignment(cost_matrix)
    
    # assign voices to the correct fragments
    for i in range(len(start_ind)):
        voice = start_array[start_ind[i]][0]
        dest_array[dest_ind[i]]["fragment"][0].groups.append(voice)
    groupFragments(contig)

# assign voices across fragments (in the notes' groups)
    #*** sorting order is important (notes with the same pitch and duration are considered equal even if they are different instances)
# TODO: experiment with sorting order (something to do with melody being high notes, or soprano and bass notes varying more)
def groupFragments(contig, isMaxContig=False):
    fragments = contig[2]

    if isMaxContig: # populate maximum contigs
        i = 0
        used = set(eval(n.groups[0]) for f in fragments for n in f if len(n.groups))
        for n in [n for n in [f[0] for f in fragments] if not len(n.groups)]:
            while i in used:
                i = (i + 1) % len(fragments)
            n.groups = [str(i)]
            used.add(i)
    startV = contig[0][0]
    destV = contig[0][-1]

    # assign across fragments
    for f in fragments:
        startN = None
        destN = None
        for n in f:
            if n.id in [t.element.id for t in startV.startAndOverlapTimespans]: 
                startN = n
            if n.id in [t.element.id for t in destV.startAndOverlapTimespans]: 
                destN = n
        if startN and len(startN.groups): voice = startN.groups 
        if destN and len(destN.groups): voice = destN.groups 
        for n in f:
            n.groups = voice 

# for each iteration:
#   get features of incoming contig (put in array of tuples)
#   run assignvoices
#   tweak features
def scanContigs(maxcontigs, contigs, partdict):
    for c in contigs:
        # maxcontigs already assigned
        if c in maxcontigs: continue
        assignVoicesWithFeatures(c, partdict)
        updatePartFeatures(getFeatures(c), partdict)

# return array of fragments for the contig
# these should be in order of verticality
def getFragments(contig):
    grouphash = [] # verticalities with fragments as columns
    fragments = [] # transposed

    # make sure that held notes stay in same fragment (column)
    prev = [None] * len(contig[0][0].startAndOverlapTimespans)
    for v in contig[0]:
        temp = [None] * len(prev)
        curr = [t.element for t in sorted(v.startAndOverlapTimespans, key=lambda n: n.element.id)]
        curr = sorted(curr, key=lambda n: n.pitch)
        # curr = sorted(curr, key=lambda n: n.duration.quarterLength)
        for i,n in enumerate(prev):
            if n and n.id in [c.id for c in curr]:
                temp[i] = n
        e = (n for n in curr if n.id not in [p.id if p else None for p in prev])
        for i,n in enumerate(temp):
            if not temp[i]: temp[i] = next(e)
        grouphash.append(temp)
        prev = temp
    # transpose grouphash -> fragments
    for i in range(len(grouphash[0])):
        fragments.append([])
        for row in grouphash:
            fragments[-1].append(row[i])

    return fragments    

# given a part/score return 
    # contigs  [[verticalities], (startBoundary, endBoundary), fragments]
    # maximal contigs (contigs having maximal overlap)
    # dictionary of voices (which will be separated into parts): {stream, color, features}
# TODO?: recognize rests
# TODO?: figure out how to recognize ties, slurs, beams, tuplets, etc (this might fix the broken tuplet problem) (also look into music21 Spanners?)
def segmentContigs(part):
    f = (note.Note,) # music21 class filter
    timespans = part.asTimespans(classList=f)
    verticalities = list(timespans.iterateVerticalities())
    maxOverlap = timespans.maximumOverlap()
    maxContigs = []
    contigs = []
    boundaries = set()
    partdict = {}

    # make contigs instead of using verticalities
    ## step 1. put boundaries at places where the number of overlaps changes
    i = 0
    while i < len(verticalities):
        refV = verticalities[i]
        boundaries.add(refV.offset)
        while i < len(verticalities) and (refV == verticalities[i] or len(verticalities[i].startAndOverlapTimespans) == len(refV.startAndOverlapTimespans)):
            i += 1
    boundaries.add(timespans.endTime)
    ## step 2. look at notes overlapping boundaries, put another boundary at that note's start and end (where there aren't already boundaries)
    for o in boundaries.intersection(set(timespans.overlapTimePoints(includeStopPoints=True))):
        for e in timespans.elementsOverlappingOffset(o):
            boundaries.add(e.offset)
            boundaries.add(e.endTime)
    bList = sorted(boundaries)
    ## populate contigs using boundaries as reference
    vi = 0
    bi = 1
    while vi < len(verticalities) and bi < len(bList):
        contigs.append([[], (bList[bi - 1], bList[bi]), None])
        while vi < len(verticalities) and bi < len(bList) and verticalities[vi].offset < bList[bi]:
            contigs[-1][0].append(verticalities[vi])
            vi += 1
        if not len(contigs[-1][0]):
            contigs.pop()
            bi += 1
            continue
        if len(contigs[-1][0][0].startAndOverlapTimespans) == maxOverlap:
            maxContigs.append(contigs[-1])
        bi += 1

    # generate dictionary of voices with streams, colors, and empty features array
    for i in range(maxOverlap):
        partdict[str(i)] = {"stream": part.template(fillWithRests=False), "color": "", "features": {}}
        newcolor = ''
        while (True):
            newcolor = f"#{''.join(random.choices(string.hexdigits, k=6))}"
            if newcolor not in [k["color"] for k in partdict.values()]:
                break
        partdict[str(i)]["color"] = newcolor

    # label contigs
    i = 0
    for c in contigs:
        for v in c[0]:
            for n in v.startTimespans:
                n.element.addLyric(f"{i}")
        i += 1
        c[2] = getFragments(c)
    for c in maxContigs:
        for v in c[0]:
            for n in v.startTimespans:
                n.element.addLyric("m")
        groupFragments(c, True)
        updatePartFeatures(getFeatures(c), partdict)

    return (maxContigs, contigs, partdict)

# main algorithm
# generate a new part for each group
# FIXME: some timing (like broken tuples, etc) are broken
# FIXME: notation for output3 messed up (notes changed octave in the crazy part, might have to do with the range being super outside the staff)
def separateVoices(part, version):
    (maxcontigs, contigs, partdict) = segmentContigs(part)
    match version:
        case 1:
            frontier = []
            for m in maxcontigs:
                frontier.append((m, "m"))
            crawlScore(frontier, contigs, partdict)
        case _:
            # scan contigs
            scanContigs(maxcontigs, contigs, partdict)

    parts = [p["stream"] for p in partdict.values()]
    # assign, color, and insert notes into their respective voices
    for (n, o, t) in [(t.element, t.offset, t) for t in part.asTimespans(classList=(note.Note,))]:
        n.style.color = partdict[n.groups[0]]["color"]
        n.addLyric(n.groups)
        partdict[n.groups[0]]["stream"].measure(t.measureNumber).insert(n)

    # FIXME: dynamics are off (maybe just copy them to all of the outputted parts)
    # # insert dynamics (and expressions?) into all voices
    # for (n, o, t) in [(t.element, t.offset, t) for t in part.asTimespans(classList=(dynamics.Dynamic,expressions.Expression))]:
    #     for p in partdict:
    #         next(m for m in partdict[p]["stream"].getElementsByClass(stream.Measure) if m.number >= t.measureNumber).insert(n)
            
    return parts

# parse through music21 score to use in algorithm (in-place)
    # grace notes are on the same offset as the note, this messes up the maximal contigs
# FIXME: Notation messed up for output4 (this has to do with how music21 imports the musicxml)
# FIXME: Repeats are messed up (this might have to do with how music21 imports the musicxml)
# FIXME: combine ties into single notes (some of them are separated out into multiple notes)
# TODO: recurse parts and clefs (turn into parts and insert back into score)
# TODO?: as well as segments the song structure (where melodies and voicing change)
def preprocessScore(song):
    # dechordify
    for m in song.recurse(classFilter=(stream.Measure, stream.Voice)):
        for c in m.getElementsByClass(chord.Chord):
            for n in c.notes:
                d = duration.Duration(c.quarterLength)
                n = note.Note(n.pitch)
                n.duration = d
                m.insert(c.getOffsetBySite(m), n)
            m.remove(c)
        m.makeVoices(inPlace=True)
    # fix voices nested within other voices
    for v in song.recurse(classFilter=(stream.Voice,)):
        if v.hasVoices():
            m = v.activeSite
            flat = m.flatten()
            voiced = flat.makeVoices()
            m.activeSite.replace(m, voiced)
    # remove grace notes
    graceNotes = []
    for n in song.recurse().notes:
        if n.duration.isGrace:
            graceNotes.append(n)
            n.activeSite.remove(n, shiftOffsets=True)


# set up the environment
if platform == 'win32':
    # Windows
    path = 'C:/Program Files/MuseScore 4/bin/Musescore4.exe' # (TODO?: not hardcode the musicxml reader path?)
elif platform == 'darwin':
    # Mac OS - TODO
    pass
else:
    # assume Linux
    path = '/usr/bin/musescore'
env = environment.Environment()
env['musicxmlPath'] = path

# choose version of algorithm 
''' put "--v1" in command-line arguments to run the old version '''
version = 2
if "--v1" in argv:
    version = 1
    argv.remove("--v1")

# tie adjacent notes
''' put "--tie" in command-line arguments to tie together adjacent notes '''
tie = False
if "--tie" in argv:
    tie = True
    argv.remove("--tie")

argc = len(argv)
if argc < 3:
    print('arguments: [input file] [output name (no extension)]')
else:
    print(f"Running version {version}")
    if tie: print("Tying adjacent notes")
    # parse musicxml
    song = converter.parse(argv[1])
    preprocessScore(song)
    # song.show()
    print(f"starting at {len(song.parts)} parts")
    # result score with top-level notation
    final = song.template()
    for p in final.parts:
        final.remove(p)
    for s in final.getElementsByClass("StaffGroup"):
        final.remove(s)

    # run algorithm
    # run for each "part"
    if song.hasPartLikeStreams():
        for p in song.parts:
            reduced = separateVoices(p, version)
            for r in reduced:
                if tie: r.extendTies()
                r.makeBeams(inPlace=True)
                final.insert(r)
    else: # single-part score
        reduced = separateVoices(song, version)
        for r in reduced:
            if tie: r.extendTies()
            r.makeBeams(inPlace=True)
            final.insert(r)
    final.makeNotation(refStreamOrTimeRange=song, inPlace=True, bestClef=True)

    print(f"{len(final.parts)} parts produced")
    # FIXME: this doesn't work for output8 for some reason (something wrong with makeNotation?)
        # also find out why the three-part invention turns into 4 parts
    # song.write("musicxml", argv[2] + '_labeled.musicxml')
    for n in final.flatten().notes: # lyrics take up space
        n.lyrics = []
    # fix broken tuplets etc. 
    final.write("musicxml", argv[2] + '_separated.musicxml')
    final.write("txt", argv[2] + "_separated.txt")