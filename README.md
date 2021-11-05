# srtgen

This utility helps you construct a propperly timestamped `srt` file, in order to provide closed captions on videos or audio. It is not a transcription service, and assumes that you already have an (untimestamped) transcript of the video or audio. It takes your transcript and does its best to match each sentence to the times during which it is being spoken, then produces output which can be piped into a `srt` file to be provided with the original video.

If you have a video, you'll need to extract the audio track into a `wav` file first, and then use that `wav` file with this tool.

## Usage

```
python srtgen.py -t input.txt -a input.wav > output.srt
```

For some reason that I haven't been able to figure out yet, sometimes the subtitles are all too early by some amount of time. To account for this, you can supply an optional `-d` parameter to provide an offset (in seconds) by which to delay each subtitle. Also for some other reason that I haven't been able to figure out yet, sometimes the subtitles experience time at a different rate than us humans. To account for this, you can supply an optional `-f` parameter to provide a frame rate (in frames per second). The default frame rate is 100 frames per second, which seems pretty okayish most of the time.

If you don't provide these parameters, the script will ask you for timestamps of two anchor points of sentences towards the beginning and end of the file, and calculates them itself. To save you having to dig through the sample audio for precise timestamps, the sample anchor sentence timestamps are as follows:

* 1.wav:
  * "Hello." begins at `1`
  * "That would be really cool" begins at `8.92`
* 2.wav:
  * "Hello, and welcome to the security reviewer training." begins at `1.56`
  * "It's very important, and you should pay attention." begins at `7.76`
* 3.wav:
  * "Hi." begins at `1.08`
  * "And with a bit of data massaging, the Ratcliff-Obershelp algorithm seems to work well enough." begins at `1:11.68`
* buffalo.wav:
  * ""Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo"" begins at `2.16`
  * ""Buffalo bison that other Buffalo bison bully also bully Buffalo bison."" begins at `1:02.8`

## Dependencies

* `python` (obviously)
* `swig` (for building `speech_recognition`)
* the stuff in the Pipfile
