MOTT STUDIO 0.1 - WINDOWS PACKAGING KIT
======================================
This ZIP contains SOURCE CODE and Windows EXE BUILD INSTRUCTIONS.
IT DOES NOT YET CONTAIN A PREBUILT EXE.

OPTION A: Build on a Windows computer (one-time)
1. Install free Python 3.11 or 3.12 on the BUILD computer.
2. Unzip this folder; double-click build_windows.bat.
3. It downloads free dependencies and builds dist\MottStudio\MottStudio.exe.
4. From then on, launch MottStudio.exe without installing Python.
   Keep the whole dist\MottStudio folder together; do not move only the EXE.

OPTION B: Build without installing Python on your PC
A GitHub Actions build workflow is included at .github/workflows/windows-build.yml.
If you have a GitHub account, create a repository and upload the package contents,
then open Actions and run the Windows build. Download the resulting artifact.
This depends on GitHub's then-current free usage terms and requires some setup.

READ BEFORE USING
* Windows build has not been run or tested in this environment.
* This prototype uses sounddevice/PortAudio; it does NOT guarantee ASIO or low latency.
* Recordings have not been tested on an iRig Pro Duo or Focusrite Scarlett.
* Use the interface's hardware direct monitor, rather than relying on software monitoring.
* Software is experimental: back up recordings and test short takes first.
* NO MIDI instruments, Smart Drummer, transcription, lyric sync, mastering or MP3 yet.
* Interface drivers may still be needed even with a packaged EXE.
* Internet is needed to download free build dependencies, but not for ordinary recording.
* The bundled third-party packages have their own licenses.
