# First dry-vessel measurement

Status: **planned; no real-vessel data collected**. The next physical milestone
requires a vessel, its mounting arrangement and calibrated observations. The
[specimen template](specimen_template.json) records unknown values as `null` rather
than treating the provisional simulation settings as measurements.

1. Record specimen identity, material evidence, mass, thickness at several points,
   rim construction and a profile/scan. Photograph support positions, pads and
   mounting. Record each exciter housing mass and contact footprint. Keep raw
   observations under `data/measurements/<specimen-id>/`, with calibration records,
   acquisition settings and repeat identifiers.
2. Start dry, with a fixed support arrangement. Identify two response positions and
   three excitation positions in the same coordinate system. Measure repeatable
   small-signal responses before introducing water or electronic feedback.
3. Acquire applied force and response on synchronized channels. An instrumented
   impact or force-measured drive gives an input in newtons. A calibrated velocity
   observation gives m/s. With calibrated acceleration, use
   `H_velocity/force = H_acceleration/force / (i*2*pi*f)` at positive frequencies,
   while retaining sensor polarity, phase calibration and channel timing.
4. Repeat each of the six paths, inspect force coverage and response noise, reject
   double impacts/clipping and retain raw records. Choose recording length and
   frequency resolution from observed decay and peak widths. Coherence is a useful
   diagnostic with averaging, but by itself does not establish model accuracy.
5. Compare resonance locations, damping and complex mobility with the dry model.
   Change one documented parameter family at a time. Keep some repeat runs or
   response locations out of fitting, then compare those observations separately.

The measurement principles follow the manufacturer's
[mechanical-mobility testing guide](https://www.bksv.com/doc/br0458.pdf) and
[NI's experimental modal-analysis overview](https://www.ni.com/en/shop/labview/modal-analysis-in-labview.html).
These are method references, not a requirement to purchase particular equipment.

The current model applies a total force uniformly by surface area across an exciter
patch. A hammer's localized contact or an actuator's real force distribution may
not match that assumption. Record the difference and adapt the force observation
before claiming matched transfer accuracy. Sensor mass, glue compliance and rim
reinforcement can also change the real response and are currently absent from the
model. Exciter amplifier voltage does not determine applied newtons without a
mechanical/electrical calibration. A normalized contact-microphone WAV can help
locate peaks, but cannot supply calibrated mobility amplitude or phase.

Use the [exchange tool](external_validation.md) once SI complex mobility is available.
Its fixed-grid format is the comparison boundary, not a raw acquisition format;
any FRF estimation, resampling and uncertainty assessment must be recorded with
the source. The tool does not fit parameters or estimate coherence automatically.

Dry measurements should first correct geometry, supports and damping. Water work
then adds fluid loading and a pressure observation model. Drawing water over a
dry shell, or relabelling metal velocity as hydrophone pressure, cannot establish
that coupling.
