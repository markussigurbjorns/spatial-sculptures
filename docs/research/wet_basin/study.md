# A shared wet-basin model for motion, surface elevation and hydrophone pressure

Working research note, October 2026. This stage extends the verified dry graph-shell
reference and the provisional water-column study. It introduces spatial fluid
inertia and pressure, while retaining an explicit linear pressure-release surface
approximation. The equations describe a model; physical vessel calibration remains
deferred.

## Physical and software boundary

Python assembles the fluid and structural models and solves one modal response.
Metal displacement, kinematic water-surface elevation and interior pressure are
observations of that response. Blender consumes precomputed coordinates. The WAV
contains normalized pressure samples, with one common gain for both hydrophones.
It does not contain the original SuperCollider noise sketch or inferred radiated
sound. SuperCollider can later process those same pressure channels.

```text
 dry shell + spatial fluid inertia
                 │
         common q(t), v(t), a(t)
                 │
      ┌──────────┼────────────┐
      ▼          ▼            ▼
 metal motion  elevation   probe pressure (Pa)
      │          │            │
      └────┬─────┘            ▼
           ▼               WAV / future DSP
        Blender
```

## Resting geometry and assumptions

The water lies between the existing graph shell mid-surface `z=b(x,y)` and mean
level `H=min(b)+depth`. The wet footprint is `b<H`, clipped inside the vessel.
Using the shell mid-surface for the fluid floor neglects the half-thickness offset.
Depth, density, hydrophone coordinates, fluid polynomial degrees, retained dry
subspace and playback count are explicit prototype configuration.

The structural material, profile, thickness, supports and exciter masses remain
provisional. Water loading contributes inertia only: hydrostatic weight, equilibrium
deflection and geometric prestress are absent. Fluid viscosity and damping are
absent; modal damping remains the prescribed structural ratio.

Incompressible, irrotational small-amplitude flow admits a velocity potential.
Standard potential formulations also introduce gravity-dependent free-surface
conditions and frequency-dependent hydrodynamics; our zero-potential mean surface
is a deliberate simplification of those conditions. See [MIT's seakeeping notes,
sections on potential flow and linear free-surface conditions](https://ocw.mit.edu/courses/2-019-design-of-ocean-systems-spring-2011/0a8db4679928bbf62bc46addbc709432_MIT2_019S11_SK1.pdf).
This is not CFD and contains **no gravity or capillary surface eigenmodes**.

## Nonlocal fluid inertia

For Cartesian wall displacement shapes `W_j=(Wx,Wy,Wz)`, the upward graph flux is

```text
U_j = Wz_j - b_x Wx_j - b_y Wy_j
```

On the bottom, fluid outward flux is `-U_j/sqrt(1+b_x²+b_y²)`; the graph area
Jacobian cancels in its weak integral. Trial functions `ψ_a=(z-H) P_i(x) P_j(y)
P_k(z)` vanish on the mean surface. Shifted/scaled Legendre polynomials span total
horizontal degree and a separate vertical degree.

```text
A_ab = ∫water ∇ψ_a · ∇ψ_b dV
B_aj = -∫wet_floor ψ_a U_j dx dy
A C = B
M_fluid = ρ Bᵀ C
```

The matrix is reciprocal and nonnegative, and includes interactions between
different wall regions. This replaces the local column formula. The bowl has no
artificial vertical sides; the flat reference cell uses rigid vertical sides.
Vertical quadrature exactly integrates the trial gradient products; shoreline
and horizontal structural projections are checked by refinement.

Fluid inertia is projected into a retained dry modal subspace. There,

```text
M = diag(m_dry) + M_fluid
K = diag(m_dry ω_dry²)
K T = M T diag(ω_wet²)
```

Wet structural and fluid shapes share the same modal transformation and amplitude
normalization. Retaining more dry modes changes the approximation and requires a
separate response check. This is a reduced coupled model rather than a monolithic
fluid/solid FEM solve.

## Observations and force pulses

For zero initial displacement and velocity:

```text
φ(x,y,z,t) = Σ_j φ_j(x,y,z) qdot_j(t)
p'(x,y,z,t) = -ρ Σ_j φ_j(x,y,z) qddot_j(t)       [Pa]
η(x,y,t) = Σ_j ∂zφ_j(x,y,H) q_j(t)             [m]
metal displacement = Σ_j W_j(x,y) q_j(t)       [m]
```

Pressure is the dynamic perturbation about resting pressure. Each hydrophone has
an actual XYZ position strictly inside the resting fluid, configured by x/y and
depth below the mean surface. No hydrophone frequency response is inferred.
Elevation follows the pressure-release kinematic condition, with a fixed resting
footprint and no moving contact line. It must not be described as a solved
gravity/capillary ripple field. Behavior near the shoreline needs a later model.

An ideal instantaneous mechanical impulse would create a distributional pressure
term through acceleration. Export instead uses a finite box pulse: impulse area
`J` becomes force `J/τ` for duration `τ`, initially 10 ms. Modal step responses
provide continuous displacement and velocity; pressure may jump at pulse edges.
The default pulse is applied at an underside exciter, not modeled as a water drop.

## Numerical verification

The [validation tool](../../../tools/validate_wet_basin.py) declares tolerances
before evaluating cases. Evidence retains failed upper-frequency intervals rather
than inheriting the dry contact model's 200 Hz band.

1. Known harmonic potentials in the actual asymmetric wet bowl verify pressure
   signs, units, graph coupling and rigid-translation inertia `ρ*volume`.
2. Six separated cosine solutions in a rigid-sided rectangular cell verify the
   entire added-inertia matrix and two interior pressure observations. The exact
   modal inertia per area is `ρ tanh(kh)/k`, with limit `ρh` at `k=0`.
3. Optional independent NGSolve tetrahedral H1 solves use the same rigid-cell
   boundary conditions. The weak-form and natural-Neumann treatment follow the
   [official NGSolve Poisson tutorial](https://docu.ngsolve.org/latest/i-tutorials/unit-1.1-poisson/poisson.html).
   This verifies fluid-cell mass and pressure; it does not constitute an independent
   curved wet-basin validation.
4. Fluid horizontal degree, vertical degree, integration, dry modal subspace and
   shell mesh refinements compare all six exciter-to-sensor paths in SI units.
   Contact velocity, hydrophone pressure and surface elevation have separate
   complex relative L2 errors on each frequency interval. Low resonances cannot
   hide a failure in an upper interval.
5. Mode correspondence through the selected band plus the next complete cluster,
   resonance-grid refinement, retained-bank response and identically filtered
   finite-pulse pressure provide additional checks.

These are sampled numerical convergence criteria, not an absolute continuum-error
bound or physical calibration. Point observations of pressure need stronger basis
refinement than frequency changes alone suggest. High-degree polynomial energy
matrices can be ill-conditioned; the report records their scaled condition numbers
and equation residuals alongside observable convergence.

The [verification record](validation.md) reports passing evidence through 80 Hz,
including independent cell pressures, retained-bank checks and actual Blender
audio/render validation. The [convergence figure](convergence.png) retains the
failed upper intervals. Portable playback modes and fluid observation weights are
saved beside the report and checked by hash before export.

## Presentation and future work

Both visible surfaces use the same exposure-averaged modal displacement and a
documented visual magnification. Audio uses the physical acceleration clock.
Offline common-channel FIR filtering preserves the time origin but is noncausal,
so ringing can precede an impact. Normalization is a listening gain in inverse Pa,
not a measured playback calibration. Video cannot display every audio oscillation.

Next physical stages are gravity/capillary surface dynamics, coupled free-surface
response, an independent curved wet-vessel solver, and eventually physical
measurements. Acoustic radiation, real hydrophone transfer, nonlinear/contact-line
behavior, drip forcing and DSP feedback each need their own assumptions and
validation. The present state/observation boundary leaves those additions in Python
without placing simulation equations in Blender.
