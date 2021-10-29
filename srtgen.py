import hashlib
import pathlib
import pickle
import re
import sys

import nltk
import speech_recognition

from alignment.sequence import Sequence
from alignment.vocabulary import Vocabulary
from alignment.sequencealigner import SimpleScoring, GlobalSequenceAligner
from nltk.tokenize import RegexpTokenizer


tokenizer = RegexpTokenizer("[\w']+")
nltk.download('punkt', quiet=True)


def format_timestamp(timestamp):
    if not timestamp:
        return "???"

    seconds = int(timestamp)
    milliseconds = int(1000 * (timestamp - seconds))

    mins = seconds // 60
    seconds = seconds % 60

    hours = mins // 60
    mins = mins % 60

    return "{:02d}:{:02d}:{:02d},{:03d}".format(hours, mins, seconds, milliseconds)



def get_sentences(filename):
    with open(filename, 'r') as file:
        text = file.read()
    text_sentences = nltk.sent_tokenize(text)
    # introduce additional splits on newlines
    text_segments = []
    for sentence in text_sentences:
        parts = re.split("\n+", sentence)
        for part in parts:
            text_segments.append(part.strip())

    sentences = []
    script_words = []
    for sentence in text_segments:
        words = tokenizer.tokenize(sentence)
        lower_words = [x.lower() for x in words]
        sentences.append({
            "text": sentence,
            "words": lower_words,
            "segments": [],
        })
    return sentences


def get_recognized_words(filename):
    with open(filename, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:8]
    pickle_filename = "{}-{}.pickle".format(pathlib.Path(filename).stem, digest)

    try:
        # check for pickled instance of speech recognition
        with open(pickle_filename, 'rb') as p:
            segments = pickle.load(p)
    except FileNotFoundError:
        # perform speech recognition
        r = speech_recognition.Recognizer()
        with speech_recognition.WavFile(filename) as source:
            print("Duration:         {}s".format(source.DURATION))
            print("Sample rate:      {}/s".format(source.SAMPLE_RATE))
            print("Frame count:      {}".format(source.FRAME_COUNT))
            print("")
            audio_data = r.record(source)
        decoder = r.recognize_sphinx(audio_data, show_all=True)
        segments = [(seg.word.split('(')[0], seg.start_frame, seg.end_frame) for seg in decoder.seg()][1:]
        # pickle it for next time
        with open(pickle_filename, 'wb') as p:
            pickle.dump(segments, p)
    return segments


def align_wordlists(wordlist_1, wordlist_2):
    script_sequence = Sequence(wordlist_1)
    audio_sequence = Sequence(wordlist_2)
    vocab = Vocabulary()
    encoded_script_sequence = vocab.encodeSequence(script_sequence)
    encoded_audio_sequence = vocab.encodeSequence(audio_sequence)
    scoring = SimpleScoring(2, -1)
    aligner = GlobalSequenceAligner(scoring, -2)
    score, encoded_sequences = aligner.align(encoded_script_sequence, encoded_audio_sequence, backtrace=True)
    #import pdb; pdb.set_trace()
    selected_encoded_sequences = encoded_sequences[0]
    alignment = vocab.decodeSequenceAlignment(selected_encoded_sequences)
    return alignment

def map_alignment(sentences, segments, alignment):
    word_idx = 0
    sentence_idx = 0
    segment_idx = 0
    alignment_idx = 0

    for align in alignment:
        #print("processing {} --- {} {} {} {} ".format(align, word_idx, sentence_idx, segment_idx, alignment_idx))
        annotated_segment = [align[0], None]
        if align[1] != '-':
            # segment exists, so we consume it
            if align[1] != segments[segment_idx][0]:
                # if alignment works how I think it does, this should be impossible
                print("SEGMENT MISMATCH! {} != {}".format(align[1], segments[segment_idx][0]))
            annotated_segment[1] = segments[segment_idx]
            #print("    consumed segment: {}".format(segments[segment_idx]))
            segment_idx += 1
        # at this point, annotated_segment is {script_word: segment_if_any} and we've consumed the segment
        if align[0] != '-':
            # script word exists, so we consume it
            if align[0] != sentences[sentence_idx]['words'][word_idx]:
                # if alignment works how I think it does, this should also be impossible
                print("SCRIPT WORD MISMATCH! {} != {}".format(align[0], sentences[sentence_idx]['words'][word_idx]))
            #print("    consumed word: {}".format(sentences[sentence_idx]['words'][word_idx]))
            word_idx += 1
        # claim the segment for the active sentence
        sentences[sentence_idx]['segments'].append(annotated_segment)

        # if we've consumed the last word in a sentence, advance to the next sentence
        if word_idx == len(sentences[sentence_idx]['words']):
            #print("        consumed sentence: {}".format(sentences[sentence_idx]['text']))
            sentence_idx += 1
            word_idx = 0

    return sentences


def print_srt(sentences, offset=0, frame_rate=100):
    for idx, sentence in enumerate(sentences):
        if len(sentence['segments']) < 2:
            continue
        #import pdb;pdb.set_trace()
        # get the start time of the first found segment
        for segment in sentence['segments']:
            if segment[1]:
                start_time = segment[1][1] + offset
                break
        # get the end time of the last found segment
        for segment in sentence['segments'][::-1]:
            if segment[1]:
                end_time = segment[1][2] + offset
                break
        print(idx + 1)
        print('{} --> {}'.format(format_timestamp(offset + start_time/frame_rate), format_timestamp(offset + end_time/frame_rate)))
        print(sentence['text'])
        print('')

def usage():
    print("\nUsage:")
    print("  python srtgen.py script.txt audio.wav [offset=0] [framerate=100]")
    print("")
    print("You can use the optional offset and framerate arguments to tune the result. "
          "Supply an offset to push all subtitles off by that many seconds. "
          "Supply a framerate to change the number of frames per second in your wav file.")
    print("")
    print("I'd sure love to calculate these values automatically, but :shrug:")
    print("")
    print("Examples:")
    print("    python srtgen.py samples/1.txt samples/1.wav 0 93 > samples/1.srt")
    print("    python srtgen.py samples/2.txt samples/2.wav 1.4 95 > samples/2.srt\n")

def main(args):
    if len(args) < 2:
        return usage()
    script_path = args[0]
    audio_path = args[1]

    subtitle_offset = 0
    audio_frame_rate = 100
    try:
        subtitle_offset = float(args[2])
        audio_frame_rate = float(args[3])
    except:
        pass

    print("Audio frame rate: {}/s".format(audio_frame_rate))
    print("Subtitle offset:  {}s".format(subtitle_offset))

    # get a list of sentences, and annotate them
    sentences = get_sentences(script_path)

    # get a list of recognized words, and their timestamps
    segments = get_recognized_words(audio_path)
    segments = [s for s in segments if s[0] != '<sil>']

    # build out a flat ordered list of words for both the script and audio
    audio_words = [x[0] for x in segments]
    script_words = []
    for sentence in sentences:
        script_words += sentence['words']

    # align those two lists of words
    alignment = align_wordlists(script_words, audio_words)

    # map the alignment back to the sentences and segments
    sentences = map_alignment(sentences, segments, alignment)

    # output the sentences in SRT format
    print("")
    print_srt(sentences, subtitle_offset, audio_frame_rate)


if __name__ == "__main__":
   main(sys.argv[1:])
