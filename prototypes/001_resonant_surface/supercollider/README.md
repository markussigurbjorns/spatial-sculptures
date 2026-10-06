# Resonant surface — SuperCollider

Python owns the field, Blender visualizes it, and SuperCollider receives state
for a small sonification experiment. This first milestone is **one-way**. No DSP
feedback is sent to Python and no final spatial-audio composition is defined.

## Run

1. Open `main.scd` in the SuperCollider IDE and evaluate the whole block. It loads
   routing and receivers, boots the audio server, and loads the SynthDef. It does
   not start a synth automatically.
2. In the prototype's `config.py`, set `OSC["enabled"] = True`. Match `port` to
   the language port printed by the receiver (normally 57120), then launch Blender
   normally and play the timeline. An ordinary Python loop may step `ResonantField`
   and call `OSCTransport.send_state(state)` instead.
3. Inspect `~hydrophone1`, `~hydrophone2`, `~waterTotalEnergy`, and `~dropImpact`.
   Set `~oscDebug = true` to post incoming values.
4. Optionally evaluate `~startResonantPreview.value` to start the resonant/noise
   listening sketch. Evaluate `~stopResonantPreview.value` to stop it.

For receiver-only use, evaluate `osc.scd` directly. An audio server is unnecessary
for storing values. `sclang`'s language port and `scsynth`'s audio-server port
(normally 57110) are distinct. [SuperCollider NetAddr documentation](https://doc.sccode.org/Classes/NetAddr.html)
describes the language endpoint.

Re-evaluating receiver definitions replaces the prototype's named `OSCdef`s;
it does not accumulate responders. To remove them, free the keys
`resonantHydrophone1`, `resonantHydrophone2`, `resonantWaterEnergy`,
`resonantWaterMaximum`, and `resonantDropImpact`, or quit the language session.
See [OSCdef](https://doc.sccode.org/Classes/OSCdef.html) for named receiver behavior.

## Messages and units

The sender uses Python's standard library to encode OSC 1.0 float32 messages in
one immediate bundle per snapshot, capped at `OSC["send_rate"]` per wall-clock
second. Python needs no `python-osc` package. Packet format follows the
[OSC 1.0 specification](https://opensoundcontrol.stanford.edu/spec-1_0.html).
Simulation time is a payload value, not a scheduled OSC timetag.

| Address | Meaning |
| --- | --- |
| `/simulation/time` | Absolute simulation time, seconds |
| `/hydrophone/1/amplitude`, `/hydrophone/2/amplitude` | Signed sampled water displacement, metres |
| `/exciter/N/amplitude` | Relative artistic wave weight, dimensionless |
| `/exciter/N/frequency` | Configured excitation frequency, Hz; visual phase also uses time_scale |
| `/water/total_energy` | Mean squared displacement over a fixed sampling grid, m²; **not joules** |
| `/water/max_displacement` | Sampled maximum absolute displacement, metres |
| `/drop/impact` | 0..1 envelope, lasting 0.12 seconds after a drip impact |

`N` is one-based, in prototype configuration order. Initial receivers store the
two hydrophone values, energy proxy, maximum displacement, and impact. Other sent
values are available for future receivers.

These are control-rate snapshots, not hydrophone audio samples. The preview maps
absolute displacement magnitudes to a smoothed noise drive, with arbitrary
resonances. Its 180/290/460 Hz tones are listening-sketch choices, not measured
basin modes. A 30 Hz control stream cannot represent the full excitation waveform.
No pressure-to-voltage calibration is claimed.

UDP may lose snapshots. Impact is a short envelope rather than a guaranteed event.
The sender is disabled by default and opens no socket until an enabled send.

## Files

- `main.scd`: file-relative entry point; boots the server and loads the others.
- `osc.scd`: named receivers, stored values, and optional debug posting.
- `synthdefs.scd`: one small preview SynthDef and explicit start/stop functions.
- `spatial.scd`: output bus and temporary stereo monitoring position. Future
  VBAP, Ambisonics, or multichannel layouts remain undecided.

## Future bidirectional loop

```text
Python simulation → virtual hydrophone → OSC → SuperCollider
       ↑                                      │
       │                          DSP / delay / filtering /
       │                              frequency shifting
       │                                      │
       └──────── virtual exciter ← OSC ────────┘
```

Reserved addresses in `transport/messages.py` include
`/feedback/exciter/N/amplitude`, `/feedback/exciter/N/frequency`,
`/exciter/N/position x y z`, and `/hydrophone/N/position x y z`.
There is no Python receiver, position serializer, control loop, or feedback
default yet. Add gain/delay/control semantics as an explicit experiment.

This intentionally mirrors real water/metal → hydrophone → SuperCollider → DSP →
amplifier → contact exciter → metal/water. Reusing artistic DSP with real input
will require a new input mapping and calibration; it should not require rewriting
the artistic processing simply because the source becomes physical.

## Validation status

Python tests validate wire encoding, message values, sensor sampling, disabled
transport, and send-rate limiting. The localhost delivery test runs where sockets
are allowed and skips with a reason where they are blocked. Blender builds are
checked with third-party OSC imports and socket creation blocked.

SuperCollider 3.13 is installed in the development environment, but its startup
probe failed under sandbox networking/process restrictions. UDP socket creation
is denied here. Live reception, audio-server startup, and audible preview runtime
validation were therefore not possible in this environment. Run the receiver
steps above on a normal local setup to complete that check.
