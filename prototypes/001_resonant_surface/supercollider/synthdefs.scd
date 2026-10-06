// Small control-rate sonification experiment. Field displacement is not streamed audio.
(
SynthDef(\resonantSurfacePreview, { |out=0, h1=0, h2=0, impact=0, level=0.04, pan=0|
    var drive, noise, resonances;
    drive = Lag.kr(((h1.abs + h2.abs) * 35).clip(0, 1), 0.08);
    noise = PinkNoise.ar(0.02 + (drive * 0.08) + (Lag.kr(impact, 0.03) * 0.06));
    // Arbitrary resonances for a listening sketch, not estimated basin modes.
    resonances = Ringz.ar(noise, [180, 290, 460], [0.25, 0.35, 0.5]).sum;
    Out.ar(out, Pan2.ar(LeakDC.ar(resonances).tanh * level, pan));
}).add;

~updateResonantPreview = {
    if(~resonantPreview.notNil, {
        ~resonantPreview.set(\h1, ~hydrophone1, \h2, ~hydrophone2, \impact, ~dropImpact);
    });
};

~startResonantPreview = {
    ~resonantPreview.tryPerform(\free);
    ~resonantPreview = Synth(\resonantSurfacePreview, [
        \out, ~resonantOutputBus, \pan, ~resonantPreviewPan,
        \h1, ~hydrophone1, \h2, ~hydrophone2, \impact, ~dropImpact
    ]);
};

~stopResonantPreview = {
    ~resonantPreview.tryPerform(\free);
    ~resonantPreview = nil;
};
)
