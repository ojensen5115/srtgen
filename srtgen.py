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
            #print("Duration:         {}s".format(source.DURATION))
            #print("Sample rate:      {}/s".format(source.SAMPLE_RATE))
            #print("Frame count:      {}".format(source.FRAME_COUNT))
            #print("")
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
    '''
    for idx, word in enumerate(script_words):
        print("{}: {}".format(idx, word))
    for idx, segment in enumerate(segments):
        print("{}: {}".format(idx, segment))
    '''
    # get matching blocks
    matcher = difflib.SequenceMatcher(isjunk=None, a=script_words, b=audio_words, autojunk=False)
    blocks = matcher.get_matching_blocks()
    #print(blocks)

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

        #print(block)

        # catch up on non-matching area
        #print("{} vs {}".format(block_script_idx, script_idx))
        if block_script_idx > script_idx:
            for idx in range(script_idx, block_script_idx):
                #print("filling in {}".format(script_words[idx]))
                sentence['segments'].append([script_words[idx], None, None])
                script_idx += 1
                word_idx += 1
                if word_idx >= len(sentence['words']):
                    sentence_idx += 1
                    try:
                        sentence = sentences[sentence_idx]
                    except:
                        pass
                    word_idx = 0
                    #print("advancing sentence in fill to {}".format(sentence_idx))
        # apply the match

        for idx in range(0, block_length):
            #print("matching {}".format(script_words[block_script_idx + idx]))
            sentence['segments'].append((script_words[block_script_idx + idx], segments[block_segment_idx + idx], block_segment_idx + idx))
            script_idx += 1
            word_idx += 1
            if word_idx >= len(sentence['words']):
                sentence_idx += 1
                try:
                    sentence = sentences[sentence_idx]
                except:
                    pass
                word_idx = 0
                #print("advancing sentence in match to {}".format(sentence_idx))

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


def print_srt(sentences, segments, offset=0, frame_rate=100):
    for sentence_idx, sentence in enumerate(sentences):
        late_start = 0
        early_end = 0
        # get the start time of the first found segment
        for idx, segment in enumerate(sentence['segments']):
            if segment[1]:
                start_time = segment[1][1] + offset
                late_start = idx
                break
        # get the end time of the last found segment
        for idx, segment in enumerate(sentence['segments'][::-1]):
            if segment[1]:
                end_time = segment[1][2] + offset
                early_end = idx
                break
        print(sentence_idx + 1)
        print('{} --> {}'.format(format_timestamp(offset + start_time/frame_rate), format_timestamp(offset + end_time/frame_rate)))
        #if late_start or early_end:
        #    print("{} :::: {}".format(late_start, early_end))
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

    print("Generated by srtgen.py -- https://github.com/ojensen5115/srtgen")
    print("Audio frame rate: {}/s".format(audio_frame_rate))
    print("Subtitle offset:  {}s".format(subtitle_offset))

    # get a list of sentences, and annotate them
    sentences = get_sentences(script_path)

    # get a list of recognized words, and their timestamps
    segments = get_recognized_words(audio_path)
    segments = [s for s in segments if s[0] != '<sil>']

    # align those two lists of words
    sentences = align_segments(sentences, segments)

    # output the sentences in SRT format
    print_srt(sentences, segments, subtitle_offset, audio_frame_rate)


if __name__ == "__main__":
   main(sys.argv[1:])
