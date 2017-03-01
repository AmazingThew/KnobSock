import asyncio, asyncore, asynchat, socket
import os
import sys
import mido
import pickle
import hashlib


class MidiServer(asyncore.dispatcher):

    knobStateFilename = 'knobState'
    knobConfigFilename = 'knobConfig'

    def __init__(self, hostname, port):
        try:
            # Load device config
            with open(self.knobConfigFilename, 'rb') as f:
                self.configHash = hashlib.md5(f.read()).hexdigest()
            with open(self.knobConfigFilename, 'rb') as f:
                self.deviceInfo = pickle.load(f)
        except Exception as e:
            print(e, file=sys.stderr)
            print('\n\nConfig file is missing or unparsable. Please run configurator.py to generate it', file=sys.stderr)
            sys.exit(-1)

        self.subSockets = []
        self.totalKnobs = sum((device['numKnobs'] for device in self.deviceInfo.values()))
        self.knobMap = []
        self.knobOffsets = [0]
        self.connectedDevices = []
        self.prevControllerNames = []
        self.knobs = bytearray([0] * self.totalKnobs)

        try:
            # Load previous knob state
            if os.path.exists(self.knobStateFilename):
                with open(self.knobStateFilename, 'rb') as f:
                    configHash, knobState = pickle.load(f)
                    if configHash == self.configHash:
                        print('Restoring knob values from disk')
                        self.knobs = knobState
                    else:
                        print('Knob configuration has changed; discarding preexisting knob values')
            else:
                print('No preexisting knob values on disk; values will read 0 until knobs are moved')
        except Exception as e:
            print(e, file=sys.stderr)
            print('\n\nFailed to load preexisting knob values from disk; values will read 0 until knobs are moved', file=sys.stderr)

        print('Starting socket server')
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind((hostname, port))
        self.listen(5)

        mido.set_backend('mido.backends.rtmidi')
        loop = asyncio.get_event_loop()
        loop.call_soon(self.awaitDevices, loop)
        loop.run_forever()
        loop.close()


    def awaitDevices(self, loop):
        controllerNames = mido.get_input_names()
        if controllerNames != self.prevControllerNames:
            self.connectDevices(controllerNames)
        self.prevControllerNames = controllerNames

        loop.call_later(5, self.awaitDevices, loop)


    def connectDevices(self, controllerNames):
        [port.close() for port in self.connectedDevices]
        self.knobMap = []
        self.knobOffsets = [0]
        self.connectedDevices = []

        skipped = 0
        runningOffset = 0
        for (i, name) in enumerate(controllerNames):
            index = i - skipped
            cleanName = name[:name.rfind(' ')]
            if cleanName not in self.deviceInfo.keys():
                print("No configuration found for {}; skipping...".format(cleanName))
                skipped += 1
                continue

            try:
                print("Connecting to " + cleanName)
                port = mido.open_input(name, callback=lambda m, cn=index: self.onMessage(cn, m))
                self.connectedDevices.append(port)
                self.knobMap.extend(
                    (None if x is None else x + runningOffset for x in self.deviceInfo[cleanName]['knobMap']))
                self.knobOffsets.append(len(self.deviceInfo[cleanName]['knobMap']))
                runningOffset += self.deviceInfo[cleanName]['numKnobs']
            except Exception as e:
                print('Unable to open MIDI input: {}'.format(name), file=sys.stderr)


    def handle_accepted(self, sock, address):
        print('Accepted connection from {}'.format(address))
        self.subSockets.append(SubSocket(sock, self, self.totalKnobs))
        self.push()


    def unregister(self, subSocket):
        self.subSockets.remove(subSocket)
        self.saveKnobs()


    def push(self):
        [sock.push(self.knobs) for sock in self.subSockets]


    def onMessage(self, controllerNumber, message):
        if message.type == 'control_change':
            self.knobs[self.knobMap[self.knobOffsets[controllerNumber] + message.control]] = message.value
            self.push()
        elif message.type == 'note_on':
            self.printKnobs()


    def printKnobs(self):
        print('\n'.join("{}:\t{}".format(i, float(b) / 127.0) for i, b in enumerate(self.knobs)) + '\n')


    def saveKnobs(self):
        print('\nPersisting knobs to disk:')
        self.printKnobs()
        try:
            with open(self.knobStateFilename, 'wb') as f:
                pickle.dump((self.configHash, self.knobs), f)
        except Exception as e:
            print(e, file=sys.stderr)
            print('\n\nFailed to persist knob state to disk', file=sys.stderr)




class SubSocket(asynchat.async_chat):
    def __init__(self, sock, midiServer, bufferSize):
        print('Starting subsocket')
        asynchat.async_chat.__init__(self, sock)
        self.midiServer = midiServer
        self.ac_out_buffer_size = bufferSize

    def collect_incoming_data(self, data):
        pass
    def found_terminator(self):
        pass
    def handle_close(self):
        print('Disconnecting')
        self.midiServer.unregister(self)
        self.close()



if __name__ == '__main__':
    MidiServer('localhost', 8008)
    asyncore.loop()