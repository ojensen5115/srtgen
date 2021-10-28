import nltk
import speech_recognition

from alignment.sequence import Sequence
from alignment.vocabulary import Vocabulary
from alignment.sequencealigner import SimpleScoring, GlobalSequenceAligner
from nltk.tokenize import RegexpTokenizer


tokenizer = RegexpTokenizer("[\w']+")

audio_frame_rate = 100



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


# initialize necessary ntlk resources
nltk.download('punkt', quiet=True)

def get_sentences(filename):
    with open(filename, 'r') as file:
        text = file.read().replace('\n', ' ')
    text_sentences = nltk.sent_tokenize(text)
    sentences = []
    script_words = []
    for sentence in text_sentences:
        words = tokenizer.tokenize(sentence)
        lower_words = [x.lower() for x in words]
        lower_words.append('<sil>')
        sentences.append({
            "text": sentence,
            "words": lower_words,
            "segments": [],
        })
    return sentences


def get_recognized_words(filename):
    r = speech_recognition.Recognizer()
    with speech_recognition.AudioFile(filename) as file:
        audio_data = r.record(file)
        decoder = r.recognize_sphinx(audio_data, show_all=True)
        segments = [(seg.word.split('(')[0], seg.start_frame/audio_frame_rate) for seg in decoder.seg()][1:-1]
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
    selected_encoded_sequences = encoded_sequences[0]
    alignment = vocab.decodeSequenceAlignment(selected_encoded_sequences)
    return alignment

def map_alignment(sentences, segments, alignment):
    word_idx = 0
    sentence_idx = 0
    segment_idx = 0
    alignment_idx = 0

    for align in alignment:
        #print("processing {}".format(align))
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


def print_srt(sentences):
    for idx, sentence in enumerate(sentences):
        if len(sentence['segments']) < 2:
            continue
        start_time = sentence['segments'][0][1][1]
        end_time = sentence['segments'][-1][1][1]
        print(idx + 1)
        print('{} --> {}'.format(format_timestamp(start_time), format_timestamp(end_time)))
        print(sentence['text'])
        print('')




def main():
    script_path = 'samples/1.txt'
    audio_path = 'samples/1.wav'

    # get a list of sentences, and annotate them
    sentences = get_sentences(script_path)

    # get a list of recognized words, and their timestamps
    segments = get_recognized_words(audio_path)

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
    print_srt(sentences)


main()
