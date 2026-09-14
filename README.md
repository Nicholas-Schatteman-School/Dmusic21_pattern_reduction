Music Arrangements For Monophonic Instruments Using Reductions
Overview
This program reduces polyphonic music scores to monophonic or simplified polyphonic arrangements based on user-defined constraints. Using the Music21 library, the program processes MusicXML files, identifies repeated patterns, and applies note prioritization to simplify chords and voices while retaining the essence of the original composition. The results are exported as MusicXML and PDF files for further use or analysis.

To run this program, python 3.9 or higher should be installed.
The Music21 library should be installed as well.
Install using pip: pip install music21
Musescore should be install as well in order to view the files.

There are 4 programs in this repo.
test_cordify.py is a program in order to test if the cordify function in music21 is working properly. Could be useful in the future but is not necessary.
pattern_detection.py is for reducing the score just using the pattern detection method. Could be useful if you would like to refine this technique or use it in conjuction with another reduction method.
voice_separation.py is to split notes that are played at the same time into related sections to better identify motifs.
music21_reductions.py is to do reductions with both pattern detection and note ranking. THIS IS THE MAIN PROGRAM!

IMPORTANT NOTE: 
The program currently is set to detect patterns of 5 notes and marks patterns that appear at least twice in the score. 
To change the pattern length, change the min_length variable in the find_repeated_patterns function. In the same function you can change the significance threshold to be more than 2. 

Running the program:
python music21_reductions.py
The program will ask for a file path location. 
The program will then ask for how many max voices to be retained in the reduced score. 
The program will then complete the reduction and output a new .musicxml file.

KNOWN ISSUES:
Ties: Tied notes are not currently accounted for in voice counting, which may lead to inaccuracies.
Clefs: The program consolidates notes into a single bar line, sometimes changing clefs.
Dynamics: Dynamic markings are not preserved.
