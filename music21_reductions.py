# Program that reduces a score (.musicxml file) using pattern detection and note ranking.  
from sys import argv, platform
import subprocess
import os
import music21
from importlib import util
from collections import Counter

# Verify that music21 is installed
print("Checking if 'music21' is installed...")
if util.find_spec("music21") is not None:
    print("'music21' is installed and ready to use.")
else:
    print("Error: 'music21' is not installed.")
    exit()

# Set up MuseScore paths
if platform == 'win32':
    # Windows
    music21.environment.set('musicxmlPath', r'C:/Program Files/MuseScore 4/bin/Musescore4.exe')
    music21.environment.set('musescoreDirectPNGPath', r'C:/Program Files/MuseScore 4/bin/Musescore4.exe')
elif platform == 'darwin':
    # Mac OS - TODO
    pass
else:
    # assume Linux
    music21.environment.set('musicxmlPath', r'/usr/bin/mscore')
    music21.environment.set('musescoreDirectPNGPath', r'/usr/bin/mscore')


# Read the input music xml file and get the user's desired number of parts
if argv[1]:
    file = argv[1]
else:
    file = input("Please enter a filename:\n")
print(f"You entered {file}")
if argv[2]:
    limit = int(argv[2])
else:
    limit = int(input("Enter the maximum number of notes played simultaneously.\n"))
print(f"{limit} voices of polyphony will be preserved.")
print("Running converter...\n")

# Parse the file using music21
try:
    song = music21.converter.parse(file)
    song = song.chordify()  # Chordify the song
    print("File parsed and chordified successfully.")
except Exception as e:
    print(f"Error parsing the file: {e}")
    exit()

# Extract tempo, time signature, dynamics, and song title
tempo_indications = song.metronomeMarkBoundaries()
original_tempo = tempo_indications[0][2] if tempo_indications else None

time_signature = song.recurse().getElementsByClass(music21.meter.TimeSignature)
original_time_signature = time_signature[0] if time_signature else None

dynamics = song.recurse().getElementsByClass(music21.dynamics.Dynamic)

song_title = "Unknown Title"
if song.metadata and song.metadata.title:
    song_title = song.metadata.title

# Generate file names for saving
filename = file.split(".")
title_pdf = filename[0] + ".pdf"
title_xml = filename[0] + ".xml"
separated_xml = filename[0] + "_separated.musicxml"

#Create seperated music
print("\nmusic21_voice_separation start(\n")
seperation_status = subprocess.run(["python", "./music21_voice_separation-master/voice_separation.py", file, filename[0]], capture_output=True, text=True)
seperation_status.check_returncode()
print(seperation_status.stdout)
print(")music21_voice_separation finished\n")

print("Reading " + filename[0] + "_separated.musicxml")
try:
    seperated_song = music21.converter.parse(filename[0] + "_separated.musicxml")
    print("Seperated file parsed and chordified successfully.")
except Exception as e:
    print(f"Error parsing the seperated file: {e}")
    exit()

# Remove existing files if they exist
for output_file in [title_pdf, title_xml, 'dropped_notes.pdf', 'dropped_notes.xml']:
    if os.path.exists(output_file):
        os.remove(output_file)
        print(f"Deleted existing file: {output_file}")

# Save the original results as PDF and XML
try:
    print("Attempting to write original score as MusicXML and PDF...")
    song.write('musicxml', fp='MuTrans.xml')
    song.write('musicxml.pdf', fp='MuTrans.pdf')
    print("MusicXML and PDF written successfully.")
except Exception as e:
    print(f"Error writing files: {e}")
    exit()

# Rename files if they exist
if os.path.exists('MuTrans.xml'):
    os.rename('MuTrans.xml', title_xml)
    print(f"Renamed MuTrans.xml to {title_xml}")
else:
    print("Error: 'MuTrans.xml' was not created.")

if os.path.exists('MuTrans.pdf'):
    os.rename('MuTrans.pdf', title_pdf)
    print(f"Renamed MuTrans.pdf to {title_pdf}")
else:
    print("Error: 'MuTrans.pdf' was not created.")

print("Done saving original score as PDF and XML.")

# Function to prioritize melody notes in the reduced notes based on the found repeated patterns
def prioritize_melody(score_obj, reduced_notes, repeated_patterns, max_voices):
    priority_notes = set()
    for pattern in repeated_patterns:
        priority_notes.update(pattern)  # Add all notes in the pattern to the priority set
    
    # Keep notes from the reduced chord based on priority
    prioritized_notes = [note for note in reduced_notes if note.name in priority_notes]
    
    remaining_notes = [note for note in reduced_notes if note not in prioritized_notes]
    while len(prioritized_notes) < max_voices and remaining_notes:
        prioritized_notes.append(remaining_notes.pop(0))
    
    return prioritized_notes[:max_voices]  # Ensure the list never exceeds max_voices

# Function to reduce a chord to a specific number of voices
def reduce_chord(score_obj, score_notes, chord_obj, max_voices, repeated_patterns):
    notes = chord_obj.notes
    reduced_notes = []

    # Prioritize melody notes first
    prioritized_notes = prioritize_melody(score_obj, notes, repeated_patterns, max_voices)
    
    # Limit the number of notes based on max_voices
    reduced_notes = prioritized_notes[:max_voices]

    # If the chord is too short (i.e., fewer notes than max_voices), only use the original notes
    return music21.chord.Chord(reduced_notes)


# Function to reduce a music21 score to a specific number of voices (without adding extra notes)
def reduce_score(score_obj, max_voices, repeated_patterns):
    reduced_stream = music21.stream.Part()

    # Preserve the time signature and tempo
    time_signature = score_obj.flatten().getElementsByClass(music21.meter.TimeSignature)
    tempo_mark = score_obj.flatten().getElementsByClass(music21.tempo.MetronomeMark)

    # Add time signature and tempo to the reduced stream if found
    if time_signature:
        reduced_stream.append(time_signature[0])  
    if tempo_mark:
        reduced_stream.append(tempo_mark[0])  

    score_notes = score_obj.flatten().notesAndRests
    
    # Loop through the original score
    for i in range(len(score_notes)):
        if isinstance(score_notes[i], music21.chord.Chord):
            reduced_chord = reduce_chord(score_obj, score_notes, pos, max_voices, repeated_patterns)
            # Only append if the reduced chord has notes (no artificial additions)
            if reduced_chord.notes:
                reduced_stream.append(reduced_chord)
            else:
                # If no notes are left in the chord, append rests to meet the limit
                for _ in range(max_voices - len(reduced_chord.notes)):
                    reduced_stream.append(music21.note.Rest(quarterLength=score_notes[i].quarterLength))
        else:
            reduced_stream.append(score_notes[i])  # Append rests or other elements

    return reduced_stream


def reduce_seperated_score(score_obj, prioritized_score, remainder_score, max_voices):
    reduced_stream = music21.stream.Part()
    p_reduced_stream = music21.stream.Part()
    r_reduced_stream = music21.stream.Part()

    # Preserve the time signature and tempo
    time_signature = score_obj.flatten().getElementsByClass(music21.meter.TimeSignature)
    tempo_mark = score_obj.flatten().getElementsByClass(music21.tempo.MetronomeMark)

    # Add time signature and tempo to the reduced stream if found
    if time_signature:
        reduced_stream.append(time_signature[0])  
    if tempo_mark:
        reduced_stream.append(tempo_mark[0])


    score_notes = score_obj.flatten().notesAndRests

    priority_notes = prioritized_score.flatten().notesAndRests
    remainder_notes = remainder_score.flatten().notesAndRests

    if len(priority_notes) > len(remainder_notes):
        length = len(priority_notes)
    else:
        length = len(remainder_notes)


    for i in range(length):
        p_notes = []
        r_notes = []

        if isinstance(priority_notes[i], music21.chord.Chord):
            p_notes.extend(priority_notes[i].notes)
        else: 
            if isinstance(priority_notes[i], music21.note.Note):
                p_notes.append(priority_notes[i])

        if (len(p_notes) < max_voices and len(remainder_notes) > i):
            if isinstance(remainder_notes[i], music21.chord.Chord):
                r_notes.extend(remainder_notes[i].notes[:max_voices - len(p_notes)])
            else: 
                if isinstance(remainder_notes[i], music21.note.Note):
                    r_notes.append(remainder_notes[i])
        
        
        p_reduced_chord = music21.chord.Chord(p_notes[:max_voices])
        r_reduced_chord = music21.chord.Chord(r_notes)
        
        
        if p_reduced_chord.notes:
            p_reduced_stream.append(p_reduced_chord)
        else:
            # If no notes are left in the chord, append rests to meet the limit
            for _ in range(max_voices - len(p_reduced_chord.notes)):
                p_reduced_stream.append(music21.note.Rest(quarterLength=priority_notes[i].quarterLength))
        

        if r_reduced_chord.notes:
            r_reduced_stream.append(r_reduced_chord)
        else:
            # If no notes are left in the chord, append rests to meet the limit
            for _ in range(max_voices - len(r_reduced_chord.notes)):
                r_reduced_stream.append(music21.note.Rest(quarterLength=priority_notes[i].quarterLength))

    
        

    #p_reduced_stream.show()
    #r_reduced_stream.show()

    reduced_stream.insert(0, p_reduced_stream)
    reduced_stream.insert(0, r_reduced_stream)

    ret = reduced_stream.flatten().chordify()

    return ret


    


# Function to make array of notes always have lowest note be A
def normalize_pattern(notes):
    pitches = []

    for n in notes:
        pitches.append(music21.pitch.Pitch(n.octave))
    
    to_be_lowest = music21.pitch.Pitch('A0')
    lowest = pitches[0]

    for p in pitches:
        if (p < lowest):
            lowest = p

    factor = lowest.pitchClass - to_be_lowest.pitchClass

    for p in pitches:
        p.pitchClass -= factor

    return pitches


# Function to find repeated patterns of notes in the score
def find_repeated_patterns(score_obj, min_length=5):
    patterns = []
    
    # Flatten the score to analyze notes
    notes = [n for n in score_obj.flatten().notes if n.isNote]
    
    for i in range(len(notes)):
        for j in range(i + min_length, len(notes) + 1):
            pattern = tuple(normalize_pattern([n for n in notes[i:j]]))  # Create a tuple of note names
            patterns.append(pattern)

    # Count occurrences of each pattern
    pattern_counts = Counter(patterns)
    
    # Filter patterns to include only those that occur more than once
    repeated_patterns = {p: count for p, count in pattern_counts.items() if count > 4}
    
    return repeated_patterns


def in_repeated_patterns(score_obj, pos, repeated_patterns):
    notes = [n for n in score_obj.flatten().notes if n.isNote]
    for pattern in repeated_patterns:
        for i in range(len(pattern)):
            if pos - i >= 0 and pos - i + len(pattern) < len(notes) and repeated_patterns.count(tuple(normalize_pattern([n for n in notes[pos - i:pos - i + len(pattern)-1]]))) > 0:
                return True
                
    return False



def find_priority_notes(score_obj):
    repeated_patterns = find_repeated_patterns(score_obj)
    priority_notes = []
    
    # Flatten the score to analyze notes
    notes = [n for n in score_obj.flatten().notes if n.isNote]
    
    for p in repeated_patterns:
        for i in range(len(notes)):
            if (tuple(normalize_pattern(notes[i, i + len(p)])) == p):
                for j in range(i, i+len(p)):
                    priority_notes.append({j, notes[j]})
    
    return priority_notes


def seperate_prioritised(score_obj, repeated_patterns):
    prioritized_stream = music21.stream.Part()
    remainder_stream = music21.stream.Part()

    score_notes = score_obj.flatten().notesAndRests
    #score_obj.show()
    i = 0
    for n in score_notes:
        if n.isRest:
            prioritized_stream.append(music21.note.Rest(quarterLength=n.quarterLength))
            remainder_stream.append(music21.note.Rest(quarterLength=n.quarterLength))
        else:
            i += 1
            if in_repeated_patterns(score_obj, i, repeated_patterns):
                prioritized_stream.append(n)
                remainder_stream.append(music21.note.Rest(quarterLength=n.quarterLength))
            else:
                prioritized_stream.append(music21.note.Rest(quarterLength=n.quarterLength))
                remainder_stream.append(n)

    #remainder_stream.show()
    
    return prioritized_stream, remainder_stream


# Main processing of chords
# repeated_patterns = find_repeated_patterns(seperated_song.parts[0])

# for i in range(1, len(seperated_song.parts)):
#     repeated_patterns.join(find_repeated_patterns(seperated_song.parts[i]))
repeated_patterns = []
for p in seperated_song.parts:
    repeated_patterns.extend(find_repeated_patterns(p))


prioritized_score = music21.stream.Score(id='prioritized_score')
remainder_score = music21.stream.Score(id='remainder_score')

time_signature = song.flatten().getElementsByClass(music21.meter.TimeSignature)
tempo_mark = song.flatten().getElementsByClass(music21.tempo.MetronomeMark)

if time_signature:
    prioritized_score.append(time_signature[0])
    remainder_score.append(time_signature[0])
if tempo_mark:
    prioritized_score.append(tempo_mark[0])
    remainder_score.append(tempo_mark[0])

for p in seperated_song.parts:
    parts = seperate_prioritised(p, repeated_patterns)
    prioritized_score.insert(0, parts[0])
    remainder_score.insert(0, parts[1])

# prioritized_score.show()
# print(len(prioritized_score.getElementsByClass(music21.stream.Part)))
# remainder_score.show()
chordied_prioritized_score = prioritized_score.chordify()
chordied_remainder_score = remainder_score.chordify()
# chordied_prioritized_score.flatten().show()
# chordied_remainder_score.flatten().show()


if limit <= 1:
    part = music21.stream.Part()
    new_score = music21.stream.Score(id='main_score')
    new_score.insert(0, part)

    # Add tempo and time signature if available
    if original_tempo:
        part.append(original_tempo)
    if original_time_signature:
        part.append(original_time_signature)

    for thisChord in song.recurse().getElementsByClass(['Chord', 'Rest']):
        count = 0
        ranked_list = []
        if thisChord.isChord:
            print(thisChord.pitchedCommonName)
            if (thisChord.containsTriad() or thisChord.isIncompleteMajorTriad() or thisChord.isIncompleteMinorTriad() or thisChord.isSeventh()) and count < limit:
                note = music21.note.Note(thisChord.third, quarterLength=thisChord.quarterLength)
                ranked_list.append(note)
                count += 1

            if (thisChord.containsSeventh() or thisChord.isDominantSeventh() or thisChord.isSeventh()) and count < limit:
                note = music21.note.Note(thisChord.seventh, quarterLength=thisChord.quarterLength)
                ranked_list.append(note)
                count += 1

            if (thisChord.containsTriad() or thisChord.isIncompleteMajorTriad() or thisChord.isIncompleteMinorTriad()) and count < limit:
                note = music21.note.Note(thisChord.root(), quarterLength=thisChord.quarterLength)
                ranked_list.append(note)
                count += 1

            if thisChord.containsTriad() and count < limit:
                note = music21.note.Note(thisChord.fifth, quarterLength=thisChord.quarterLength)
                ranked_list.append(note)
                count += 1

            if not (thisChord.containsTriad() or thisChord.isIncompleteMajorTriad() or thisChord.isIncompleteMinorTriad()) and count < limit:
                note = music21.note.Note(thisChord.root(), quarterLength=thisChord.quarterLength)
                ranked_list.append(note)
                count += 1

        if thisChord.isRest:
            rest = music21.note.Rest(quarterLength=thisChord.quarterLength)
            ranked_list.append(rest)
            count += 1

        while count < limit:
            rest = music21.note.Rest(quarterLength=thisChord.quarterLength)
            ranked_list.append(rest)
            count += 1
        
        # Add the reduced notes to the part
        for note in ranked_list:
            part.append(note)

else:
    #reduced_score = reduce_score(song, limit, repeated_patterns)
    reduced_score = reduce_seperated_score(song, chordied_prioritized_score, chordied_remainder_score, limit)
    new_score = music21.stream.Score(id='main_score')
    new_score.append(reduced_score)  # Append the reduced score directly

# Apply dynamics to each part
for dynamic in dynamics:
    new_score.insert(dynamic.offset, dynamic)

# Output new file
output = new_score.chordify()
output.insert(0, music21.metadata.Metadata())
output.metadata.title = f"{song_title} - Reduced to {limit} voices"
output.write('musicxml.pdf', fp='MuTest')
os.rename('MuTrans.pdf', 'dropped_notes.pdf')
os.rename('MuTrans.xml', 'dropped_notes.xml')
print("Done!")
