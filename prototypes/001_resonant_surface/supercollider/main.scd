// Evaluate this whole block in the SuperCollider IDE. No preview synth starts automatically.
(
var directory = PathName(thisProcess.nowExecutingPath).pathOnly;
~resonantDirectory = directory;
~resonantPreview.tryPerform(\free);
~resonantPreview = nil;
(directory +/+ "spatial.scd").load;
(directory +/+ "osc.scd").load;
s.waitForBoot({
    (directory +/+ "synthdefs.scd").load;
    "Resonant surface ready. Evaluate ~startResonantPreview.value to hear the experiment.".postln;
});
)
