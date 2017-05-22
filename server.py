import asyncio
import os
import sys
import mido
import pickle
import hashlib
from itertools import zip_longest
from animator import MidiFighterAnimator


class MidiServer(object):

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

        self.clientConnections = []
        self.totalKnobs = sum((device['numKnobs'] for device in self.deviceInfo.values()))
        self.knobMap = []
        self.knobInfo = []
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

        mido.set_backend('mido.backends.rtmidi')

        loop = asyncio.get_event_loop()
        factory = loop.create_server(lambda: MidiProtocol(self), hostname, port)
        server = loop.run_until_complete(factory)
        print('Starting server on port {}'.format(port))

        self.animator = MidiFighterAnimator(loop)

        loop.call_soon(self.awaitDevices, loop)

        try:
            loop.run_forever()
        finally:
            print('Shutting down server')
            server.close()
            loop.run_until_complete(server.wait_closed())
            print('Closing event loop')
            loop.close()


    def awaitDevices(self, loop):
        controllerNames = mido.get_input_names()
        if controllerNames != self.prevControllerNames:
            print('\nConnecting devices:')
            self.connectDevices(controllerNames)
            self.rectifyDeviceState()
            self.animate()
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
                port = mido.open_input(name, callback=lambda m, cn=index: self.onMessage(cn, m))
                self.connectedDevices.append(port)
                self.knobMap.extend(
                    (None if x is None else x + runningOffset for x in self.deviceInfo[cleanName]['knobMap']))

                for perDeviceKnobIndex, (mappedKnobIndex, knobChannel) in enumerate(zip(self.deviceInfo[cleanName]['knobMap'], self.deviceInfo[cleanName]['channelMap'])):
                    if mappedKnobIndex is not None:
                        multiDeviceIndex = mappedKnobIndex + runningOffset
                        self.knobInfo.append((cleanName, multiDeviceIndex, perDeviceKnobIndex, knobChannel))

                self.knobOffsets.append(len(self.deviceInfo[cleanName]['knobMap']))
                runningOffset += self.deviceInfo[cleanName]['numKnobs']
                print("Connected to " + cleanName)
            except Exception as e:
                print('Unable to open MIDI input: {}\n{}'.format(name, e), file=sys.stderr)


    def rectifyDeviceState(self):
        outputPorts = {}
        controllerNames = mido.get_output_names()
        for name in controllerNames:
            cleanName = name[:name.rfind(' ')]
            if cleanName not in self.deviceInfo.keys():
                continue

            try:
                outputPorts[cleanName] = mido.open_output(name)
            except Exception as e:
                print('Unable to open MIDI output: {}\n{}'.format(name, e), file=sys.stderr)

        for deviceName, multiDeviceIndex, perDeviceKnobIndex, knobChannel in self.knobInfo:
            if deviceName in outputPorts.keys():
                message = mido.Message('control_change', channel=knobChannel, control=perDeviceKnobIndex, value=self.knobs[multiDeviceIndex])
                outputPorts[deviceName].send(message)

        for port in outputPorts.values():
            port.close


    def animate(self):
        controllerNames = mido.get_output_names()
        for name in controllerNames:
            if 'Midi Fighter Twister' in name:
                port = mido.open_output(name)
                self.animator.setDevice(port)
                break


    def register(self, connection):
        self.clientConnections.append(connection)


    def unregister(self, connection):
        self.clientConnections.remove(connection)
        self.saveKnobs()


    def push(self):
        [client.push(self.knobs) for client in self.clientConnections]


    def onMessage(self, controllerNumber, message):
        if message.type == 'control_change':
            self.knobs[self.knobMap[self.knobOffsets[controllerNumber] + message.control]] = message.value
            self.push()
        elif message.type == 'note_on':
            self.onButton()


    def onButton(self):
        self.saveKnobs()
        # self.rectifyDeviceState() #TODO REENABLE AND FIX


    def printKnobs(self):
        def chunks(iterable, chunkSize, fillvalue=None):
            args = [iter(iterable)] * chunkSize
            return zip_longest(*args, fillvalue=fillvalue)

        knobStrings = ["{}:\t{:10.8f}".format(i, float(b) / 127.0) for i, b in enumerate(self.knobs)]
        columnHeight = 16
        columns = chunks(knobStrings, columnHeight, "")
        rows = zip(*columns)
        print('\n'.join('\t'.join(row) for row in rows) + '\n')
        # print('\n'.join(knobStrings) + '\n')


    def saveKnobs(self):
        print('\nPersisting knobs to disk:')
        self.printKnobs()
        try:
            with open(self.knobStateFilename, 'wb') as f:
                pickle.dump((self.configHash, self.knobs), f)
        except Exception as e:
            print(e, file=sys.stderr)
            print('\n\nFailed to persist knob state to disk', file=sys.stderr)



class MidiProtocol(asyncio.Protocol):
    def __init__(self, midi):
        self.midi = midi

    def push(self, data):
        self.transport.write(data)

    def connection_made(self, transport):
        self.transport = transport
        self.address = transport.get_extra_info('peername')
        print('Connection accepted from {}'.format(self.address))
        self.transport.set_write_buffer_limits(self.midi.totalKnobs, self.midi.totalKnobs)
        self.midi.register(self)

    def data_received(self, data):
        print('recieved from {}: {}'.format(self.address, data))

    def eof_received(self):
        pass

    def connection_lost(self, error):
        if error:
            if error.errno == 10054:
                print('Connection to {} force-closed by client'.format(self.address))
            else:
                print('Error from {}: {}'.format(self.address, error))
        else:
            print('Closing connection to {}'.format(self.address))
        self.midi.unregister(self)
        super().connection_lost(error)



if __name__ == '__main__':
    MidiServer('localhost', 8008)