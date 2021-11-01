import argparse
import difflib
import hashlib
import pathlib
import pickle
import re
import sys

import nltk
import speech_recognition

from nltk.tokenize import RegexpTokenizer


tokenizer = RegexpTokenizer("[\w']+")
nltk.download('punkt', quiet=True)
verbose = False


def eprint(*args, **kwargs):
    if verbose or kwargs.get('force'):
        print(*args, file=sys.stderr)

def seconds_to_srt_ts(timestamp):
    if not timestamp:
        return "???"
    seconds = int(timestamp)
    milliseconds = int(1000 * (timestamp - seconds))
    mins = seconds // 60
    seconds = seconds % 60
    hours = mins // 60
    mins = mins % 60
    return "{:02d}:{:02d}:{:02d},{:03d}".format(hours, mins, seconds, milliseconds)

def input_ts_to_seconds(input_ts):
    # format: HH:MM:SS.mmm
    parts = input_ts.split(":")[::-1]

    seconds = float(parts[0])
    try:
        seconds += int(parts[1]) * 60
        seconds += int(parts[2]) * 3600
    except:
        pass
    return seconds


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
    for sentence in text_segments:
        words = tokenizer.tokenize(sentence)
        lower_words = [x.lower() for x in words]
        sentences.append({
            "text": sentence,
            "words": lower_words,
            "segments": [],
        })
    return sentences


def get_sentence_map(sentences):
    sentence_map = []
    for idx, sentence in enumerate(sentences):
        for _ in sentence['words']:
            sentence_map.append(idx)
    return sentence_map


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
        with speech_recognition.WavFile(str(filename)) as source:
            audio_data = r.record(source)
        decoder = r.recognize_sphinx(audio_data, show_all=True)
        segments = [(seg.word.split('(')[0], seg.start_frame, seg.end_frame) for seg in decoder.seg()][1:]
        # pickle it for next time
        with open(pickle_filename, 'wb') as p:
            pickle.dump(segments, p)
    return segments


def align_segments(sentences, segments):
    # build out a flat ordered list of words for both the script and audio so we can match them
    audio_words = [x[0] for x in segments]
    script_words = []
    for sentence in sentences:
        script_words += sentence['words']

    # get matching blocks
    matcher = difflib.SequenceMatcher(isjunk=None, a=script_words, b=audio_words, autojunk=False)
    blocks = matcher.get_matching_blocks()

    # get a map of word idx -> sentence idx
    sentence_map = get_sentence_map(sentences)

    # map segments to sentence words
    script_idx = 0
    block_idx = 0
    word_idx = 0
    sentence_idx = 0
    last_block_script_idx = 0
    last_block_segment_idx = 0

    for block in blocks:
        block_script_idx = block[0]
        block_segment_idx = block[1]
        block_length = block[2]

        # catch up non-matching area
        missing_script_words = block_script_idx - last_block_script_idx
        missing_segment_words = block_segment_idx - last_block_segment_idx
        # TODO: we're just front-loading the gaps here -- not ideal
        eprint("Missing {} script words, {} segment words".format(missing_script_words, missing_segment_words))
        for num in range(missing_script_words):
            script_idx = last_block_script_idx + num
            segment_idx = last_block_segment_idx + num
            sentence = sentences[sentence_map[script_idx]]
            word = script_words[script_idx].upper()

            if num < missing_segment_words:
                segment = segments[segment_idx]
            else:
                segment = None
            eprint(" _: {} :: {} ({})".format(word, segment, segment_idx))
            sentence['segments'].append((
                word,
                segment,
                False
                ))
        for num in range(missing_segment_words - missing_script_words):
            eprint("  X: skipping segment {}".format(segments[last_block_segment_idx + missing_script_words + num]))

        # apply the match
        for num in range(block_length):
            script_idx = block_script_idx + num
            segment_idx = block_segment_idx + num
            sentence = sentences[sentence_map[script_idx]]
            word = script_words[script_idx]
            eprint(" M: {} :: {} ({})".format(word, segments[segment_idx], segment_idx))
            sentence['segments'].append((
                word,
                segments[segment_idx],
                segment_idx))

        last_block_script_idx = block_script_idx + block_length
        last_block_segment_idx = block_segment_idx + block_length

    #sentences = close_sentence_gaps(sentences, segments)
    return sentences


def mark_sentence_frames(sentences):
    for sentence_idx, sentence in enumerate(sentences):
        late_start = 0
        early_end = 0
        # get the start time of the first found segment
        for idx, segment in enumerate(sentence['segments']):
            if segment[1]:
                sentence['start_frame'] = segment[1][1]
                late_start = idx
                break
        # get the end time of the last found segment
        for idx, segment in enumerate(sentence['segments'][::-1]):
            if segment[1]:
                sentence['end_frame'] = segment[1][2]
                early_end = idx
                break
        if late_start:
            eprint("Sentence {} has a late start of {} words".format(sentence_idx + 1, late_start))
        if early_end:
            eprint("Sentence {} has an early end of {} words".format(sentence_idx + 1, early_end))
    return sentences


def get_delay_and_rate(sentences, segments):
    eprint("At what timestamp does this sentence from the beginning of the audio begin? (HH:MM:SS.mmm)", force=True)
    eprint("    " + sentences[0]['text'], force=True)
    first_ts = input_ts_to_seconds(input())

    eprint("At what timestamp does this sentence from the end of the audio begin? (HH:MM:SS.mmm)", force=True)
    eprint("    " + sentences[-1]['text'], force=True)
    last_ts = input_ts_to_seconds(input())

    interval_frames = sentences[-1]['start_frame'] - sentences[0]['start_frame']
    interval_seconds = last_ts - first_ts
    frame_rate = interval_frames / interval_seconds

    raw_first_ts = sentences[0]['start_frame'] / frame_rate
    delay = first_ts - raw_first_ts

    return (round(delay, 3), round(frame_rate, 3))


def print_srt(sentences, segments, subtitle_delay, audio_frame_rate):

    if subtitle_delay is None and audio_frame_rate is None:
        (subtitle_delay, audio_frame_rate) = get_delay_and_rate(sentences, segments)
    else:
        if subtitle_delay is None:
            subtitle_delay = 0
        else:
            subtitle_delay = subtitle_delay[0]
        if audio_frame_rate is None:
            audio_frame_rate = 100
        else:
            audio_frame_rate = audio_frame_rate[0]
    eprint("")

    print("Generated by srtgen.py -- https://github.com/ojensen5115/srtgen")
    print("Audio frame rate: {}/s".format(audio_frame_rate))
    print("Subtitle offset:  {}s".format(subtitle_delay))
    print("")

    sentence_num = 0
    for sentence in sentences:
        sentence_num += 1
        print(sentence_num)
        print('{} --> {}'.format(
            seconds_to_srt_ts(subtitle_delay + sentence['start_frame'] / audio_frame_rate),
            seconds_to_srt_ts(subtitle_delay + sentence['end_frame'] / audio_frame_rate)))
        print(sentence['text'])
        print('')


def pprint(sentence):
    print(sentence['text'])
    for segment in sentence['segments']:
        print("    {}".format(segment))

def main(args):

    parser = argparse.ArgumentParser(
        description="Match an audio stream with its text to produce a SRT file.")
    parser.add_argument("-t",
        dest="text_path", nargs=1, type=pathlib.Path, required=True,
        help="The text file to use as the source of captions. Captions are separated by sentences and newlines.")
    parser.add_argument("-a",
        dest="audio_path", nargs=1, type=pathlib.Path, required=True,
        help="The audio file to use to determine caption timestamps.")
    parser.add_argument("-d",
        dest="subtitle_delay", nargs=1, type=float,
        help="Optional parameter to delay all subtitles by this many seconds.")
    parser.add_argument("-f",
        dest="audio_frame_rate", nargs=1, type=float,
        help="Optional parameter to override frames-to-timestamp conversion.")
    parser.add_argument("-v",
        action="count", default=0,
        help="Verbose mode")

    arguments = vars(parser.parse_args(args))
    text_path = arguments['text_path'][0]
    audio_path = arguments['audio_path'][0]
    subtitle_offset = arguments['subtitle_delay']
    audio_frame_rate = arguments['audio_frame_rate']
    global verbose
    verbose = arguments['v']

    sentences = get_sentences(text_path)
    segments = get_recognized_words(audio_path)
    segments = [s for s in segments if s[0] != '<sil>' and s[0] != '[NOISE]']

    align_segments(sentences, segments)
    mark_sentence_frames(sentences)

    print_srt(sentences, segments, subtitle_offset, audio_frame_rate)


if __name__ == "__main__":
   main(sys.argv[1:])
