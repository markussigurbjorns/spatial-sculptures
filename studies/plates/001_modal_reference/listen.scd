// Load this file after python tools/run_modal_study.py has created results/contact_pickups.wav.
// The channels are normalized contact velocity, not pressure or a binaural rendering.
(
var path = PathName(thisProcess.nowExecutingPath).pathOnly ++ "results/contact_pickups.wav";
if(File.exists(path), {
    s.waitForBoot({
        SynthDef(\modalReferencePlayback, { |out=0, buf=0, level=0.2|
            var signal = PlayBuf.ar(2, buf, BufRateScale.kr(buf), doneAction: 2);
            // Place future artistic DSP here; input comes from the physical reference model.
            Out.ar(out, signal * level);
        }).add;
        s.sync;
        ~modalReferenceBuffer.tryPerform(\free);
        Buffer.read(s, path, action: { |buffer|
            ~modalReferenceBuffer = buffer;
            "Reference pickup file loaded. Evaluate ~playModalReference.value to listen.".postln;
        });
        ~playModalReference = {
            if(~modalReferenceBuffer.notNil, {
                ~modalReferencePlayer.tryPerform(\free);
                ~modalReferencePlayer = Synth(\modalReferencePlayback, [
                    \buf, ~modalReferenceBuffer, \level, 0.2
                ]);
            });
        };
        ~stopModalReference = { ~modalReferencePlayer.tryPerform(\free); };
    });
}, {
    "Generate results/contact_pickups.wav with tools/run_modal_study.py first.".warn;
});
)
