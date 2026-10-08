# A shared gravity/capillary reference for a resonant metal-and-water sculpture

Working research note, October 2026. This is a further model stage, preserved
alongside the [dry shell](../dry_basin/paper.md), [local water columns](../water_loading/study.md)
and [pressure-release fluid](../wet_basin/study.md). Its contribution is an
independent dynamic surface coupled by reciprocal fluid inertia to the shell,
with a shared pressure/motion clock. Numerical verification is distinct from
physical calibration.

## Scope

The supported metal basin is represented by retained dry-shell vector modes.
An incompressible, inviscid, irrotational fluid occupies the resting wet footprint
between graph floor `b(x,y)` and level `H`. Gravity and surface tension restore
small water-surface displacement. The floor is the shell mid-surface; a
half-thickness offset is omitted. The natural capillary condition is zero
normal elevation slope. It is an ideal edge condition, without a measured
wetting/contact-angle or moving-contact-line law.

The structural equilibrium and stiffness stay frozen at the dry reference.
This omits hydrostatic equilibrium deformation, prestress and elastogravity
wall-traction terms. A complete gravity-dependent flexible-vessel formulation
needs those contributions; see Schotté and Ohayon [2]. Adding surface restoring
energy alone is consequently a **declared approximation**, particularly for
very compliant supports or nearly rigid vessel translation. The present model
must not be described as a freely translating body in gravity or a complete
wet structural prediction.

The software boundary is unchanged:

```text
                  Python coupled response
                         q, v, a
                ┌──────────┼───────────┐
                ▼          ▼           ▼
              metal      water     pressure (Pa)
                └────┬─────┘           │
                     ▼                 ▼
                  Blender          WAV / future SC
```

No fluid/structural equations run inside Blender. The saved numerical bank
requires NumPy for playback; it needs neither SciPy nor an external solver.
SuperCollider can later process the same pressure channels. The original
control-rate resonant-noise sketch remains a separate sonification experiment.

## Volume constraint and displacement potential

For upward graph flux from dry vector shape `W_j`,

```text
U_j = Wz_j - b_x Wx_j - b_y Wy_j
c_j = integral_wet(U_j dA) / area_wet
eta(x,y) = sum_j c_j*qwall_j + sum_l F_l(x,y)*asurface_l
integral_wet(F_l dA) = 0
```

Mean surface displacement is tied to wall volume displacement. It is not an
unconstrained constant water mode. Relative elevation functions are zero-mean
horizontal polynomials, orthonormalized in mean-square projected area.

Displacement potential `chi` solves Laplace's equation. Its outward bottom
flux is `-U/sqrt(1+|grad b|²)` and its top flux is `eta`. These fluxes have
zero total integral by the volume constraint. Rigid reference-cell sidewalls
have zero flux; the curved basin closes at its shoreline. Set area-mean top
`chi` to zero to fix the otherwise arbitrary Neumann constant.

With generalized coordinates `r=(qwall, asurface)`:

```text
A_ab = integral_water(grad psi_a · grad psi_b dV)
B_a,jwall = integral_top(psi_a*c_j dA) - integral_floor(psi_a*U_j dA)
B_a,lsurface = integral_top(psi_a*F_l dA)
A*C = B
chi(x,y,z) = sum_a psi_a(x,y,z) * (C*r)_a
Mfluid = rho * B.T * C
```

Polynomial potentials span horizontal total degree and a separate vertical
degree. The global constant is excluded and each trace mean is subtracted.
Vertical Gaussian integration is exact for the trial gradient products;
horizontal and shoreline integration are checked by refinement. Diagonal
scaling improves the fluid solve, but high-order bowl polynomials still have
large condition numbers. Equation residual and observation convergence are
both checked; a small residual alone is insufficient evidence.

Full off-diagonal blocks of `Mfluid` couple shell motion and relative water
motion. The approximation is reciprocal, rather than animating waves from
metal motion without letting fluid inertia act back on metal.

## Restoring energy and dynamics

```text
T = 1/2 * rdot.T * (diag(Mdry, 0) + Mfluid) * rdot
V = 1/2 * qwall.T * Kdry * qwall
  + rho*g/2 * integral_top(eta² dA)
  + sigma/2 * integral_top(|grad eta|² dA)
K*t_j = omega_j² * M*t_j
```

These energies define the frozen-shell approximation above. They do not include
the missing hydrostatic/prestress operators. The undamped assembled system
conserves its declared energy and linear water volume; this is not proof that
all physical vessel forces are represented.

Joint modes are normalized by the larger of sampled metal-vector and
surface-elevation peaks. Mass, force projection, potential, elevation and
pressure weights undergo the same transformation. Normalizing water-dominated
modes by metal motion alone would be unstable and obscure units.

Prescribed modal damping interpolates between the metal ratio and the surface
ratio using each mode's surface-restoring-energy share. This is a practical
phenomenological assumption, not a viscosity or contact-line damping estimate.
The same exact modal step/harmonic response drives every observation. A
mechanical impulse area `J` is represented as force `J/tau` over `tau=10 ms`;
no distributional pressure impulse is silently discarded. Water droplets are
not yet a forcing model in this numerical stage.

## Hydrophone pressure and presentation

Velocity potential is `phi=chi_dot`. In the chosen surface-mean gauge,

```text
p'(x,y,z,t) = -rho*chi_ddot(x,y,z,t) + rho*g*mean(eta(t))
           = Pacceleration*qddot + Pdisplacement*q
```

The gravity mean-pressure term is required. A hydrophone samples pressure
perturbation at a fixed XYZ position strictly inside the resting water; its
third configuration coordinate is depth below `H`. The static hydrostatic
pressure baseline is not audio. Sensor transfer functions and radiated sound
are unmodeled.

Raw pressure remains in pascals. Both channels share one WAV gain. An offline
zero-phase Kaiser FIR passes through 64 Hz and reaches an 80 Hz stop band;
continuation samples avoid truncating the filter at the requested end. It may
ring before force edges. The model is not extended to the whole audible band
by this filter, and no frequency shifting is used in the export.

The picture and pressure use one physical time axis. Blender displays water
elevation, not a derivative of the earlier pressure-release potential. Metal
and water video displacement share exposure averaging and magnification;
unaveraged SI surface displacement is also saved. At 30 fps, video cannot
show every cycle contained in the pressure WAV. Hydrophone markers stay fixed
at their defined positions.

## Verification design

In a rigid rectangular cell with zero-mean cosine elevation,

```text
k = pi * sqrt((m/Lx)² + (n/Ly)²), (m,n) != (0,0)
chi = cos(m*pi*x/Lx) * cos(n*pi*y/Ly) * cosh(k*z)/(k*sinh(k*h))
Mmode = rho * integral_top(F² dA) / (k*tanh(k*h))
omega² = (g*k + sigma*k³/rho) * tanh(k*h)
```

Finite-depth gravity/capillary dispersion provides a closed-form check [1].
Gravity-only, mixed and capillary-only cells check the entire projected mass
matrix, pressure observations and frequencies across trial degrees. This
tests the free-surface formulation rather than imposing the expected dispersion
as the basin's answer.

An independent NGSolve H1/NumberSpace Neumann solve uses a volume-mean gauge,
then subtracts its top mean. Its assembled mass, pressure and restoring-energy
frequencies are compared with the same analytic cell. The weak boundary
treatment follows the official Poisson tutorial [3]. This independently tests
the fluid cell, not the coupled curved basin or missing hydrostatic operators.

The [validation script](../../../tools/validate_free_surface.py) declares
acceptance limits: 5% per-path complex weighted L2 for surface/solid/retained
response, 2% for potential refinement, 1% for integration/grid norms, 1% for
matched frequency differences and MAC >=0.99. Those are numerical study limits,
not physical accuracy estimates. An exploratory degree-6/8 sweep motivated a
degree-10 surface; the acceptance run records successive 8/10/12 cases with
unchanged gates.

Checks separate 0–1, 1–3, 3–20, 20–40 and 40–80 Hz. Six exciter/observer paths
each are compared for contact velocity, pressure and surface elevation, without
listening normalization. Independent potential horizontal/vertical, surface,
quadrature, dry-subspace and shell-mesh refinements prevent one approximation
from hiding another. The lowest six water shapes and metal-dominated modes are
matched separately. Higher-order surface modes have no uniform modal-spectrum
accuracy claim. Retained-mode errors also use identical filtered finite pulses.

See [validation.json](validation.json) for full evidence and
[validation.md](validation.md) for results. Selected bank files are portable,
pickle-free and hashed. Playback rejects changed source, changed artifacts or
failed required gates. Earlier stage sources and their evidence remain intact.

## Next physical and research steps

1. Include resting hydrostatic load, equilibrium deformation, prestress and the
   missing gravity-dependent wall operators; check supported rigid-motion limits.
2. Validate a coupled curved vessel against a separate fluid/solid implementation.
3. Investigate contact-line/meniscus conditions and dissipation before treating
   high-order capillary structure or shoreline motion as predictive.
4. Extend pressure/contact convergence beyond the current 80 Hz wet band.
5. Add explicit localized droplet forcing and bounded DSP feedback experiments.
6. When a real vessel is available, measure modes, transfer paths and water-depth
   dependence, then fit uncertain supports/mountings/damping and correct the model.

## Primary references

1. Howard Georgi, *The Physics of Waves*, section 11.5, water waves and finite-depth
   gravity/capillary dispersion. [MIT-hosted textbook](https://ocw.mit.edu/courses/8-03sc-physics-iii-vibrations-and-waves-fall-2016/ef731c1b91d77a6db003f6c27e300d25_MIT8_03SCF16_Textbook.pdf).
2. J.-S. Schotté and R. Ohayon, *Influence of fuel sloshing on the vibrational
   behaviour of aerospace structures*, EUCASS. Gravity-dependent hydroelastic
   formulation and hydrostatic/prestress/interface corrections.
   [Authors' conference paper](https://www.eucass.eu/component/docindexer/?id=5395&task=download).
3. NGSolve developers, *Poisson equation* tutorial: variational assembly and natural
   Neumann boundary conditions. [Official documentation](https://docu.ngsolve.org/latest/i-tutorials/unit-1.1-poisson/poisson.html).

Reference theory supports the assumptions and checks; it does not certify this
implementation or substitute for an independent vessel result or measurement.
