import mido
import sys
import pickle

class SparseList(list):
    def __setitem__(self, index, value):
        missing = index - len(self) + 1
        if missing > 0:
            self.extend([None] * missing)
        list.__setitem__(self, index, value)
    def __getitem__(self, index):
        try: return list.__getitem__(self, index)
        except IndexError: return None

class Configurator:
    lastMessage = None
    currMessage = None

    deviceInfo = {}

    def configure(self):
        self.connect()
        self.getMapping()
        self.save()


    def connect(self):
        print('Connecting MIDI devices')
        mido.set_backend('mido.backends.rtmidi')
        controllerNames = mido.get_input_names()

        if not controllerNames: return

        for name in controllerNames:
            try:
                cleanName = name[:name.rfind(' ')]
                print("Connecting " + cleanName)
                mido.open_input(name, callback=lambda m, cn=cleanName: self.onMessage(cn, m))
            except Exception as e:
                print('Unable to open MIDI input: {}'.format(name), file=sys.stderr)


    def getMapping(self):
        while True:
            mappedKnobs = 0
            currentDevice = ''
            expectedKnobs = input("\nEnter the number of knobs on this controller (0 to finish): ")
            try:
                expectedKnobs = int(expectedKnobs)
            except ValueError:
                continue

            if expectedKnobs < 1: break

            self.lastMessage = None
            self.currMessage = None
            knobMap = SparseList()
            channelMap = SparseList()
            print("Turn all knobs in the order you want them mapped")

            while mappedKnobs < expectedKnobs:
                if self.currMessage != self.lastMessage:
                    name, knob, channel = self.currMessage

                    if mappedKnobs == 0:
                        currentDevice = name
                        self.deviceInfo[currentDevice] = { 'numKnobs' : expectedKnobs }
                    else:
                        if name != currentDevice:
                            continue
                        if knobMap[knob] is not None:
                            continue

                    print("{0} - knob {1}, channel {2} mapped to index {3}".format(name, knob, channel, mappedKnobs))
                    knobMap[knob] = mappedKnobs
                    channelMap[knob] = channel
                    mappedKnobs += 1

                    self.lastMessage = self.currMessage

            self.deviceInfo[currentDevice]['knobMap'] = list(knobMap)
            self.deviceInfo[currentDevice]['channelMap'] = list(channelMap)


    def save(self):
        with open('knobConfig', 'wb') as f:
            pickle.dump(self.deviceInfo, f)
        print('Done!')


    def onMessage(self, name, message):
        if message.type == 'control_change':
            self.currMessage = (name, message.control, message.channel)



if __name__ == '__main__':
    Configurator().configure()