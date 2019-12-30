# WELCOME TO KNOB SOCK
![alt text](http://i.imgur.com/JjJJPkB.jpg "The picture for one konbs")

# WHAT
This is a tool to enable MIDI controllers, specifically those with knobs, to be used in interactive software projects.
It is designed to be dropped into existing codebases with the least possible changes to project configuration.

# USE CASE
Interactive software and shader/tech-art work in particular requires a lot of fiddly subjective variable tweaking.
I have grown accustomed to using a MIDI controller with a bunch of knobs for this purpose.
I do freelance VFX/tech art/creative code/interactive whatever for a living, and wanted to use knobs on my contract projects.
This is somewhat troublesome as I don't want to go adding a bunch of MIDI library dependencies into a mature codebase that I don't own.

Thus, KNOB SOCK: Knobular data supplied via socket server. Socket functionality is built into most languages, so adding a client to an existing project doesn't add any dependencies. In most cases you can just drop the client file into the project, reference it while developing, and never commit it.

Most design decisions have been made in pursuit of this goal of keeping project-side modifications as minimal as possible.


# INSTALLATION
* Install Python. I have only tested on 3.5 under Windows.
* Run `pip install mido`
* Run `pip install python-rtmidi`
* Download the project files bc you'll probably need those I guess
* Plug in one or more MIDI controllers with some knobs (tested: Akai LPD8 and Korg nanoKONTROL2)
* Run configurator.py. It will ask you to fondle all your knobs so the server can identify them
* Run server.py
* Open Clients/Python/debugClient.py and change NUM_KNOBS to the total number of knobs you configured
* Run debugClient.py. It should print values to the console when the knobs are moved.


# MONITOR
Once the server's working, I recommend Using [Knob Monitor](https://github.com/AmazingThew/KnobMonitor) to keep abreast of the knob situation


# USAGE NOTES
## General
* Every client has a NUM_KNOBS constant. You need to set this value to the number of knobs you fondled in the configurator. The clients need to know how much data to expect from the server, so if you set the wrong value you won't get errors but you'll get weird behavior like knobs overwriting each others' values.
* Default port is 8008. If you need to change that just edit the code like a normal person; config files are for nerds.
* MIDI only sends data when a value changes. This means when the server starts it has no way of knowing the knobs' positions until you change them. It works around this by writing all the knob values to disk and loading them on startup. Just don't move the knobs while the server is off and it'll always be correct (values are written to disk every time a client disconnects)

## C# Client
Everything's static; just import the class anywhere you want access to knobs. Call `Knobs.Start()` to initialize and then use the `Get()` functions to retrieve values. `Stop()` disconnects from the server and shuts down the client thread.

## Unity Client
This is just the C# client with some extra Monobehavior functionality for shader dev. Add it as a component to something in your scene; it'll bind all the knob values to global floats in your shaders. Just define `float Knob0; float Knob1; float Knob2` etc at the top of your shader passes to get access to the values. Note the capital K; the bindings are case-sensitive.
There's currently a bug with this code where if you recompile a script while in Play mode it'll get disconnected from the server. Haven't looked into that yet. Recompiling in Play mode crashes the editor more often than anything useful anyway.

## C++ Client
Windows-only at present. Everything's static. Just call `Knobs::start()` when your game starts and use the `get()` functions to retrieve knob values. It spawns a thread to do all the socket blocking and there's currently no way to shut it down short of killing the program but whatever man.

## Python Client
Only useful for quickly verifying that the server's working. It just blocks on socket IO in an infinite loop and prints values to the console.


# BUGS
* Probably


# TODO
Will probably find a way to wrap the server in a WebSocket proxy and make a Javascript client next time I end up in Three.js land.
There are definitely some rough edges right now; I've mostly been adding features as I need them. Feel free to contribute.


## Contact
[Go yell at me on twitter](https://twitter.com/AmazingThew)
