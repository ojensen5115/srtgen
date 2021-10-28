# srtgen

This utility helps you construct a propperly timestamped `srt` file, in order to provide closed captions on videos or audio. It is not a transcription service, and assumes that you already have an (untimestamped) transcript of the video or audio. It takes your transcript and does its best to match each sentence to the times during which it is being spoken, then produces output which can be piped into a `srt` file to be provided with the original video.

If you have a video, you'll need to extract the audio track into a `wav` file first, and then use that `wav` file with this tool.

## Usage

```
python srtgen.py input.txt input.wav > output.srt
```

For some reason that I haven't been able to figure out yet, sometimes the subtitles are all too early by some amount of time. To account for this, you can supply an optional third parameter which is interpreted as an offset (in seconds) by which to delay each subtitle:

Also for some other reason that I haven't been able to figure out yet, sometimes the subtitles experience time at a different rate than us humans. To account for this, you can supply an optional fourth parameter which is interpreted as a frame rate (in frames per second). The default frame rate is 100 frames per second, which seems okay most of the time.

Some examples (on the sample files):
```
python srtgen.py samples/1.txt samples/1.wav 0 93 > samples/1.srt
python srtgen.py samples/2.txt samples/2.wav 1.4 95 > samples/2.srt
```

## Dependencies

* `python` (obviously)
* `swig` (for building `speech_recognition`)
* the stuff in the Pipfile
* you'll also need to pip install `six` and `numpy` because `annotate` doesn't declare its dependencies correctly
