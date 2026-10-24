Mott Studio 2.1 routing / per-track input / metronome patch

Replace mott_studio.py and requirements.txt in your GitHub repository, then rerun your existing GitHub Actions Windows build.

In the mixer, set each track's INPUT dropdown to 1 or 2. Arm both tracks (red round R), set track 1 to input 1 and track 2 to input 2, and press RECORD.

Device 4 (iRig microphone) and device 7 (iRig speakers) are allowed as a full-duplex pair even though their numeric IDs differ. PortAudio must support opening the pair at 44100 Hz. If the driver reports an error, select compatible input/output host-API endpoints (prefer Windows WASAPI or ASIO if available), close other apps holding the interface, and retry.

Click enables an audible metronome while playing or recording; BPM spinbox sets tempo, TAP calculates tempo from repeated clicks.

LIMITATIONS: Count-in, loop-takes cycling, true punch replacement and real-time meter movement are not implemented in this patch. Simultaneous channels are saved to one multichannel WAV with separate per-track clips. Untested with physical iRig hardware. Existing project folders should be backed up before testing.
