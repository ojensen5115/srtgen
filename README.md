# srtgen

This utility helps you construct a propperly timestamped `srt` file, in order to provide closed captions on videos or audio. It is not a transcription service, and assumes that you already have an (untimestamped) transcript of the video or audio. It takes your transcript and does its best to match each sentence to the times during which it is being spoken, then produces output which can be piped into a `srt` file to be provided with the original video.

If you have a video, you'll need to extract the audio track into a `wav` file first, and then use that `wav` file with this tool.

## Usage

```
python srtgen.py -t input.txt -a input.wav > output.srt
```

For some reason that I haven't been able to figure out yet, sometimes the subtitles are all too early by some amount of time. To account for this, you can supply an optional third parameter which is interpreted as an offset (in seconds) by which to delay each subtitle. Also for some other reason that I haven't been able to figure out yet, sometimes the subtitles experience time at a different rate than us humans. To account for this, you can supply an optional fourth parameter which is interpreted as a frame rate (in frames per second). The default frame rate is 100 frames per second, which seems okay most of the time.

Some examples (on the sample files):
```
python srtgen.py -t samples/1.txt -a samples/1.wav -d 0 -f 93 > samples/1.srt
python srtgen.py -t samples/2.txt -a samples/2.wav -d 1.4 -f 95 > samples/2.srt
python srtgen.py -t samples/buffalo.txt -a samples/buffalo.wav -d 2 -f 95 > samples/buffalo.srt
```

If you don't provide these parameters, the script will ask you for timestamps of two anchor points of sentences towards the beginning and end of the file, and calculates them itself.

## Dependencies

* `python` (obviously)
* `swig` (for building `speech_recognition`)
* the stuff in the Pipfile
* you'll also need to pip install `six` and `numpy` because `annotate` doesn't declare its dependencies correctly
