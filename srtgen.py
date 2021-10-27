import nltk
import speech_recognition as sr

from nltk.tokenize import RegexpTokenizer


tokenizer = RegexpTokenizer("[\w']+")

audio_frame_rate = 100
segment_base_lookahead = 4
segment_max_lookahead = 20
approx_word_seconds = 1



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

# parse the script into sentences
with open('sample_script.txt') as file:
    text = file.read()
sentences = nltk.sent_tokenize(text)

# initialize speech recognition
r = sr.Recognizer()
with sr.AudioFile('sample_audio.wav') as file:
    audio_data = r.record(file)
    decoder = r.recognize_sphinx(audio_data, show_all=True)
    segments = [(seg.word.split('(')[0], seg.start_frame/audio_frame_rate) for seg in decoder.seg()]
    #for s in segments:
    #    print(s)

# match script against audio
annotated_sentences = []
segment_idx = 0
segment_backlog = 0
for sentence in sentences:
    words = tokenizer.tokenize(sentence.lower())
    words.append(None)
    timestamps = []
    for word in words:
        match = False
        lookahead = min(len(segments) - 1, min(segment_max_lookahead, segment_base_lookahead + segment_backlog))
        #print(word)
        #print("{} with max lookahead {}".format(word, lookahead))
        for idx in range(segment_idx, segment_idx + lookahead):
            #print("    {}:{}".format(word, segments[idx][0]))
            if word == segments[idx][0] or (word == None and (segments[idx][0] == '<sil>' or segments[idx][0] == '</s>')):
                #print("        {} at {}".format(word, segments[idx][1]))
                timestamps.append(segments[idx][1])
                if (word is not None):
                    segment_idx = idx + 1
                    segment_backlog = 0
                break
        else:
            segment_backlog += 1
            timestamps.append(None)
            #print("    NOT FOUND")
    annotated_sentences.append({"sentence": sentence, "words": words, "timestamps": timestamps})

# output as a SRT file
for idx, sentence in enumerate(annotated_sentences):
    print(idx + 1)
    print("{} --> {}".format(format_timestamp(sentence["timestamps"][0]), format_timestamp(sentence["timestamps"][-1])))
    print(sentence["sentence"])
    print("")
