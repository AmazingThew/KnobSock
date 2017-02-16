#pragma once

#define NUM_KNOBS 24
#define KNOB_PORT "8008"
#define KNOB_HOST "localhost"

class Knobs
{
private:
	static void loop();
	static int knobs[NUM_KNOBS];

public:
	static void start();
	static void stop();

	static float get(int index);
	static float get(int index, float max);
	static float get(int index, float min, float max);
};