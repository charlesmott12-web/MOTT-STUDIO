MOTT STUDIO 2.0 BETA

Replace mott_studio.py and requirements.txt in your existing GitHub repository with these files.
Your existing GitHub Actions workflow builds a Windows executable automatically.
Download the new artifact from the Actions tab and extract it before running.

Features: waveform timeline, track arm/mute/solo, VU-style mixer, faders, pan, multichannel recording, overdub monitoring, normal/time-selection/punch recording, right-click clip editing, WAV import/export, project save.

IMPORTANT BETA LIMITATIONS:
- Requires a single full-duplex device for recording and monitoring. For iRig, choose iRig for BOTH input and output.
- Punch and time-selection currently add takes over existing clips (non-destructive), rather than deleting/replacing the old region. Mute old takes manually.
- Loop-takes mode currently records one loop pass only; automatic multiple cycles are not implemented.
- Count-in and metronome controls are UI placeholders and do not produce clicks yet.
- Needle meters are visual placeholders pending connection to audio RMS data.
- Track input defaults to 1/2 and can be changed in project.json (track input value).
- Output device must provide stereo output for best compatibility.
- ASIO, latency calibration, take lanes, clip drag, and full scrolling are not yet implemented.
- 44.1 kHz WAV import only.
- Do not rely on this beta for irreplaceable recordings; test with disposable sessions first.
- Always keep a backup of your original repository and song project folders.
