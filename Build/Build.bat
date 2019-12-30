pyinstaller --onefile --icon Icon.ico --hidden-import=mido.backends.rtmidi ..\configurator.py
pyinstaller --onefile --icon Icon.ico ..\server.py