import asyncio
import os
import sys

import functools
import mido
import mido.backends.rtmidi
import pickle
import hashlib
import websockets
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
        self.connectedDevices = {}
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

        self.loop = asyncio.get_event_loop()
        # factory = loop.create_server(lambda: MidiProtocol(self), hostname, port)
        # server = loop.run_until_complete(factory)
        # print('Starting server on port {}'.format(port))

        startWebSock = websockets.serve(self.websocketHandler, 'localhost', 8765)
        self.loop.run_until_complete(startWebSock)
        print('Starting websocket server on port 8765')

        self.animator = MidiFighterAnimator(self.loop)

        self.loop.call_soon(self.awaitDevices, self.loop)

        try:
            self.loop.run_forever()
        finally:
            print('Shutting down server')
            server.close()
            self.loop.run_until_complete(server.wait_closed())
            print('Closing event loop')
            self.loop.close()


    def awaitDevices(self, loop):
        controllerNames = mido.get_input_names()
        if controllerNames != self.prevControllerNames:
            print('\nConnecting devices:')
            self.connectDevices()
            self.rectifyDeviceState()
            self.animate()
        self.prevControllerNames = controllerNames

        loop.call_later(5, self.awaitDevices, loop)


    def connectDevices(self):
        for existingInport, existingOutport in self.connectedDevices.values():
            existingInport.close()
            if existingOutport:
                existingOutport.close()

        self.knobMap = []
        self.knobOffsets = [0]
        self.connectedDevices = {}

        deviceNames = self.getDeviceNames()

        skipped = 0
        runningOffset = 0
        for (i, (cleanName, inputName, outputName)) in enumerate(deviceNames):
            index = i - skipped
            if cleanName not in self.deviceInfo.keys():
                print('No configuration found for {}; skipping...'.format(cleanName))
                skipped += 1
                continue

            try:
                inport = mido.open_input(inputName, callback=lambda m, cn=index: self.onMessage(cn, m))
                outport = mido.open_output(outputName) if outputName else None
            except Exception as e:
                print('Unable to open MIDI connection to {}\n{}'.format(cleanName, e), file=sys.stderr)
                skipped += 1
                continue

            self.connectedDevices[cleanName] = (inport, outport)
            self.knobMap.extend(
                (None if x is None else x + runningOffset for x in self.deviceInfo[cleanName]['knobMap']))

            for perDeviceKnobIndex, (mappedKnobIndex, knobChannel) in enumerate(zip(self.deviceInfo[cleanName]['knobMap'], self.deviceInfo[cleanName]['channelMap'])):
                if mappedKnobIndex is not None:
                    multiDeviceIndex = mappedKnobIndex + runningOffset
                    self.knobInfo.append((cleanName, multiDeviceIndex, perDeviceKnobIndex, knobChannel))

            self.knobOffsets.append(len(self.deviceInfo[cleanName]['knobMap']))
            runningOffset += self.deviceInfo[cleanName]['numKnobs']
            print('Connected to ' + cleanName)


    def getDeviceNames(self):
        inputNames = mido.get_input_names()
        outputNames = mido.get_output_names()
        deviceNames = []
        for inputName in inputNames:
            cleanName = inputName[:inputName.rfind(' ')]
            outputName = next((oName for oName in outputNames if oName.startswith(cleanName)), None)
            deviceNames.append((cleanName, inputName, outputName))
        return deviceNames


    def rectifyDeviceState(self):
        for deviceName, multiDeviceIndex, perDeviceKnobIndex, knobChannel in self.knobInfo:
            inport, outport = self.connectedDevices.get(deviceName, (None, None))
            if outport:
                message = mido.Message('control_change', channel=knobChannel, control=perDeviceKnobIndex, value=self.knobs[multiDeviceIndex])
                outport.send(message)


    def animate(self):
        for name, (inport, outport) in self.connectedDevices.items():
            if name == 'Midi Fighter Twister':
                self.animator.start(outport)
                break


    def register(self, connection):
        self.clientConnections.append(connection)
        self.push()


    def unregister(self, connection):
        self.clientConnections.remove(connection)
        self.saveKnobs()


    def push(self):
        knobBytes = bytes(self.knobs)
        [client.push(knobBytes) for client in self.clientConnections]


    def onMessage(self, controllerNumber, message):
        if message.type == 'control_change':
            index = self.knobMap[self.knobOffsets[controllerNumber] + message.control]
            channel = self.knobInfo[index][3]
            if message.channel == channel:
                self.knobs[index] = message.value
                self.push()
        elif message.type == 'note_on':
            self.onButton()


    def onButton(self):
        self.saveKnobs()
        self.rectifyDeviceState()


    def printKnobs(self):
        def chunks(iterable, chunkSize, fillvalue=None):
            args = [iter(iterable)] * chunkSize
            return zip_longest(*args, fillvalue=fillvalue)

        columnHeight = 16
        knobStrings = ['{}{:10.8f}'.format('{}:'.format(i).ljust(4), float(b) / 127.0) for i, b in enumerate(self.knobs)]
        columns = chunks(knobStrings, columnHeight, '')
        rows = zip(*columns)
        print('\n'.join('\t'.join(row) for row in rows) + '\n')


    def saveKnobs(self):
        print('\nPersisting knobs to disk:')
        self.printKnobs()
        try:
            with open(self.knobStateFilename, 'wb') as f:
                pickle.dump((self.configHash, self.knobs), f)
        except Exception as e:
            print(e, file=sys.stderr)
            print('\n\nFailed to persist knob state to disk', file=sys.stderr)


    async def websocketHandler(self, handler, path):
        connection = WebSocketConnection(handler, self.loop)
        self.register(connection)
        try:
            while True:
                msg = await handler.recv()
                print("RECEIVED: {}".format(msg))
                await handler.send("poops")
        finally:
            print("WEBSOCK: DISCONNECTED, DEREGISTERING")
            self.unregister(connection)

        # print("< {}".format(name))
        #
        # greeting = "Hello {}!".format(name)
        # await websocket.send(greeting)
        # print("> {}".format(greeting))

class WebSocketConnection(object):
    def __init__(self, handler, loop):
        self.loop = loop
        self.handler = handler

    def push(self, data):
        print("PUSHING")
        print(type(data))
        print(data)
        self.loop.create_task(self.handler.send(str(data)))
        # self.loop.call_soon(self.asyncPush(data))

    # async def asyncPush(self, data):
    #     await self.handler.send("farts")

# class WebSocketMidiProtocol(websockets.WebSocketServerProtocol):
#     # def __init__(self, midi, ws_handler, ws_server, **kwds):
#     def __init__(self, ws_handler, ws_server, **kwds):
#         print("WEBSOCK MIDI:")
#         # print(midi)
#         # self.midi = midi
#         super(WebSocketMidiProtocol, self).__init__(ws_handler, ws_server, **kwds)
#
#     def push(self, data):
#         self.transport.write(data)
#
#     def connection_made(self, transport):
#         self.transport = transport
#         self.address = transport.get_extra_info('peername')
#         print('WEBSOCK: Connection accepted from {}'.format(self.address))
#         # self.transport.set_write_buffer_limits(self.midi.totalKnobs, self.midi.totalKnobs)
#         # self.midi.register(self)
#         super(WebSocketMidiProtocol, self).connection_made(transport)
#
#     # def data_received(self, data):
#     #     print('WEBSOCK: recieved from {}: {}'.format(self.address, data))
#     #     super(WebSocketMidiProtocol, self).data_received(data)
#
#     def connection_lost(self, error):
#         if error:
#             if error.errno == 10054:
#                 print('WEBSOCK: Connection to {} force-closed by client'.format(self.address))
#             else:
#                 print('WEBSOCK: Error from {}: {}'.format(self.address, error))
#         else:
#             print('WEBSOCK: Closing connection to {}'.format(self.address))
#         # self.midi.unregister(self)
#         super(WebSocketMidiProtocol, self).connection_lost(error)


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