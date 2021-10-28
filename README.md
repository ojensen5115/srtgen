# Srtgen

Say you have a video and a script for said video, and you want to produce a SRT file to provide closed captioning. Well, you could sit there typing in timestamps until the cows come home, or you could use this script.

_This is still like SUPER alpha and mostly doesn't work yet._ But I'm still putting it up in case anyone finds the approach helpful.

System Dependencies:

* python (obviously)
* swig
* the stuff in the Pipfile
* annotate doesn't install its deps correctly, so also `six` and `numpy`
