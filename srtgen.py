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


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

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

    # map segments to sentence words
    script_idx = 0
    block_idx = 0
    word_idx = 0
    sentence_idx = 0
    sentence = sentences[sentence_idx]
    for block in blocks:
        block_script_idx = block[0]
        block_segment_idx = block[1]
        block_length = block[2]

        # catch up on non-matching area
        if block_script_idx > script_idx:
            for idx in range(script_idx, block_script_idx):
                #eprint("Word '{}' in sentence {} not recognized, filling it in.".format(script_words[idx], sentence_idx + 1))
                sentence['segments'].append([script_words[idx], None, None])
                script_idx += 1
                word_idx += 1
                if word_idx >= len(sentence['words']):
                    word_idx = 0
                    sentence_idx += 1
                    try:
                        sentence = sentences[sentence_idx]
                    except:
                        pass

        # apply the match
        for idx in range(0, block_length):
            sentence['segments'].append((script_words[block_script_idx + idx], segments[block_segment_idx + idx], block_segment_idx + idx))
            script_idx += 1
            word_idx += 1
            if word_idx >= len(sentence['words']):
                word_idx = 0
                sentence_idx += 1
                try:
                    sentence = sentences[sentence_idx]
                except:
                    pass

    sentences = close_sentence_gaps(sentences, segments)
    return sentences


def close_sentence_gaps(sentences, segments):
    # handle gaps
    for idx, sentence in enumerate(sentences):
        if idx == 0:
            continue

        last_sentence = sentences[idx - 1]
        # how many gaps do we have at the end of the last sentence?
        missing_end = 0
        missing_start = 0
        for segment in last_sentence['segments'][::-1]:
            if segment[1] is not None:
                last_claimed_segment = segment[2]
                break
            missing_end += 1

        # how many gaps do we have at the start of this sentence?
        for segment in sentence['segments']:
            if segment[1] is not None:
                first_claimed_segment = segment[2]
                break
            missing_start += 1

        # fix it
        unclaimed_segments = list(range(last_claimed_segment + 1, first_claimed_segment))
        gap_size = missing_end + missing_start

        if gap_size == 0:
            continue

        # determine ratio of segments to put on each side
        distribution_ratio = missing_end / gap_size
        #eprint("Gap after sentence {}, with {}% of the words allocated before the break".format(
        #    idx, round(distribution_ratio * 100)))

        if distribution_ratio == 0:
            sentence['segments'][0][1] = segments[unclaimed_segments[0]]
            sentence['segments'][0][2] = unclaimed_segments[0]
        elif distribution_ratio == 1:
            last_sentence['segments'][-1][1] = segments[unclaimed_segments[-1]]
            last_sentence['segments'][-1][2] = unclaimed_segments[-1]
        else:
            last_sentence_segment = unclaimed_segments[round(distribution_ratio * len(unclaimed_segments))]
            last_sentence['segments'][-1][1] = segments[last_sentence_segment]
            last_sentence['segments'][-1][2] = last_sentence_segment
            try:
                first_sentence_segment = unclaimed_segments[last_sentence_segment + 1]
                sentence['segments'][0][1] = segments[first_sentence_segment]
                sentence['segments'][0][2] = first_sentence_segment
            except:
                # fails if the ratio is super close to 1
                pass

    return sentences


def print_srt(sentences, segments, subtitle_delay, audio_frame_rate):

    if subtitle_delay is None:
        subtitle_delay = 0
    if audio_frame_rate is None:
        audio_frame_rate = 100
    eprint("")

    print("Generated by srtgen.py -- https://github.com/ojensen5115/srtgen")
    print("Audio frame rate: {}/s".format(audio_frame_rate))
    print("Subtitle offset:  {}s".format(subtitle_delay))
    print("")

    for sentence_idx, sentence in enumerate(sentences):
        late_start = 0
        early_end = 0
        # get the start time of the first found segment
        for idx, segment in enumerate(sentence['segments']):
            if segment[1]:
                start_time = segment[1][1] + subtitle_delay
                late_start = idx
                break
        # get the end time of the last found segment
        for idx, segment in enumerate(sentence['segments'][::-1]):
            if segment[1]:
                end_time = segment[1][2] + subtitle_delay
                early_end = idx
                break
        if late_start:
            eprint("Sentence {} has a late start of {} words".format(sentence_idx + 1, late_start))
        if early_end:
            eprint("Sentence {} has an early end of {} words".format(sentence_idx + 1, early_end))

        print(sentence_idx + 1)
        print('{} --> {}'.format(format_timestamp(subtitle_delay + start_time/audio_frame_rate), format_timestamp(subtitle_delay + end_time/audio_frame_rate)))
        print(sentence['text'])
        print('')


def main(args):

    parser = argparse.ArgumentParser(
        description="Match an audio stream with its text to produce a SRT file.",
        usage="python srtgen.py -t samples/1.txt -a samples/1.wav > output.srt")
    parser.add_argument("-t",
        dest="text_path", nargs=1, type=pathlib.Path, required=True,
        help="The text file to use as the source of captions. Captions are separated by sentences and newlines.")
    parser.add_argument("-a",
        dest="audio_path", nargs=1, type=pathlib.Path, required=True,
        help="The audio file to use to determine caption timestamps.")
    parser.add_argument("-f",
        dest="audio_frame_rate", nargs=1, type=float,
        help="Optional parameter to override frames-to-timestamp conversion.")
    parser.add_argument("-d",
        dest="subtitle_delay", nargs=1, type=float,
        help="Optional parameter to delay all subtitles by this many seconds.")

    arguments = vars(parser.parse_args(args))
    text_path = arguments['text_path'][0]
    audio_path = arguments['audio_path'][0]
    subtitle_offset = arguments['subtitle_delay']
    audio_frame_rate = arguments['audio_frame_rate']


    sentences = get_sentences(text_path)
    segments = get_recognized_words(audio_path)
    segments = [s for s in segments if s[0] != '<sil>']

    align_segments(sentences, segments)
    print_srt(sentences, segments, subtitle_offset, audio_frame_rate)


if __name__ == "__main__":
   main(sys.argv[1:])
