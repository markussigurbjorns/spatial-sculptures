// Receiver-only setup: this file works without booting the audio server.
// Python's OSC port must match the language port shown below, not scsynth's port.
(
~hydrophone1 = 0.0;
~hydrophone2 = 0.0;
~waterTotalEnergy = 0.0;
~waterMaxDisplacement = 0.0;
~dropImpact = 0.0;
~oscDebug = false;
~resonantOscPort = NetAddr.langPort;

~notifyResonant = { |path, value|
    if(~oscDebug, { [path, value].postln });
    if(~updateResonantPreview.notNil, { ~updateResonantPreview.value });
};

OSCdef(\resonantHydrophone1, { |msg|
    ~hydrophone1 = msg[1].asFloat;
    ~notifyResonant.value(msg[0], ~hydrophone1);
}, '/hydrophone/1/amplitude', recvPort: ~resonantOscPort);

OSCdef(\resonantHydrophone2, { |msg|
    ~hydrophone2 = msg[1].asFloat;
    ~notifyResonant.value(msg[0], ~hydrophone2);
}, '/hydrophone/2/amplitude', recvPort: ~resonantOscPort);

OSCdef(\resonantWaterEnergy, { |msg|
    ~waterTotalEnergy = msg[1].asFloat;
    ~notifyResonant.value(msg[0], ~waterTotalEnergy);
}, '/water/total_energy', recvPort: ~resonantOscPort);

OSCdef(\resonantWaterMaximum, { |msg|
    ~waterMaxDisplacement = msg[1].asFloat;
}, '/water/max_displacement', recvPort: ~resonantOscPort);

OSCdef(\resonantDropImpact, { |msg|
    ~dropImpact = msg[1].asFloat;
    ~notifyResonant.value(msg[0], ~dropImpact);
}, '/drop/impact', recvPort: ~resonantOscPort);

("Resonant surface OSC receivers listening on UDP " ++ ~resonantOscPort).postln;
)
