import asyncio
import random
import traceback
import mido

class MidiFighterAnimator(object):
    tickRate = 0.5
    rainbowRate = 1.5
    rainbowPhase = 5

    shouldRun = True

    loop = None
    port = None
    progress = 0

    diagonalRows = (
        (0,),
        (4, 1),
        (8, 5, 2),
        (12, 9, 6, 3),
        (13, 10, 7),
        (14, 11),
        (15,),
    )

    verticalRows = (
        (0,  1,  2,  3),
        (4,  5,  6,  7),
        (8,  9,  10, 11),
        (12, 13, 14, 15),
    )

    def __init__(self, eventLoop):
        self.loop = eventLoop
        self.progress = 0
        self.colorMap = self._generateColorMap()
        self.loop.create_task(self.animate())


    def start(self, midiPort):
        self.port = midiPort
        self.shouldRun = True


    def stop(self):
        self.shouldRun = False


    async def animate(self):
        while True:
            self._rainbow()
            await asyncio.sleep(self.tickRate)


    def setKnobColor(self, index, color):
        message = mido.Message('control_change', channel=1, control=index, value=color)
        self._send(message)


    def resetKnobColor(self, index):
        message = mido.Message('control_change', channel=1, control=index, value=0)
        self._send(message)


    def _rainbow(self):
        time = self.loop.time() * self.rainbowRate
        for i, row in enumerate(reversed(self.verticalRows)):
            for knob in row:
                color = self._colorFromTime(time + i*self.rainbowPhase)
                self.setKnobColor(knob, color)


    def _randomColor(self):
        for i in range(16):
            self.setKnobColor(i, random.randint(1, 125))


    def _colorFromTime(self, time):
        return self.colorMap[int(time % 125) + 1]


    def _send(self, message):
        if self.port is not None and not self.port.closed and self.shouldRun:
            try:
                self.port.send(message)
            except Exception:
                traceback.print_exc()
                print('Encountered exception whilst animating knobs; animation halted until device is reconnected')
                self.shouldRun = False


    # Generate a lookup table that remaps the Twister's color indices to shorten the amount of the rainbow that is dedicated to blue
    # This is an entirely subjective tweak to account for the fact that blue feels overrepresented in the Twister's LED rainbow
    def _generateColorMap(self):
        blueExtent = 12
        blueCompression = 2.5

        def remap(oldMin, oldMax, newMin, newMax, value):
            return (((value - oldMin) * (newMax - newMin)) / (oldMax - oldMin)) + newMin

        colorMap = [None]
        for i in range(1, 126):
            if 0 < i < blueExtent:
                color = int(remap(1, blueExtent, 1, blueExtent * blueCompression, i))
            else:
                color = int(remap(blueExtent, 125, blueExtent * blueCompression, 125, i))
            colorMap.append(color)

        return colorMap
