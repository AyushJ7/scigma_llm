# SCIGMA Manual Reference For LLM Command Generation

Source: `manual/manual.tex`

This Markdown file is a compact, LLM-friendly reference for generating SCIGMA
console commands. It is not a full replacement for the PDF/manual; it preserves
the operational details most useful for translating natural language requests
into SCIGMA commands.

## What SCIGMA Does

SCIGMA is a Python package for interactive exploration and visualization of
dynamical systems. It can:

- define ordinary differential equations and iterated maps
- visualize phase space and parameter space
- select initial conditions and parameters interactively
- plot trajectories and map iterates
- find stationary states
- inspect stability through eigenvalues/eigenvectors
- plot stable and unstable invariant manifolds
- construct stroboscopic maps and Poincare maps of ODEs
- perform continuation of steady states through AUTO
- automate workflows through SCIGMA command scripts or Python

The user normally interacts through the SCIGMA console in the graphics window.
Commands are plain text lines.

## Basic Workflow

Typical SCIGMA workflow:

```text
1. Set the mode: ode, map, strobe, or Poincare.
2. Define equations and initial values.
3. Set view/range/style options.
4. Run numerical commands such as plot, guess, mstable, munstable, or cont.
5. Inspect/select generated objects and continue analysis.
```

Example ODE setup:

```text
mode ode
x' = -y
y' = omega**2*x
omega = sqrt(k/m)
k = 1
m = 2
x = 1
y = 0
plot 1000
```

## Equation Syntax

SCIGMA distinguishes between:

- variables: dynamic state coordinates
- parameters: time-independent values
- functions: expressions depending on variables, parameters, or both

### Define Variables

For an ODE, define a variable by giving its time derivative:

```text
x' = x - 1
```

For a map, use the same syntax for the iterative update:

```text
n' = n*2 + 1
```

How `x' = ...` is interpreted depends on `mode`.

### Set Variable Or Parameter Values

Set the current value of a variable or define/set a parameter:

```text
x = 0.5
a = 2
```

If a new symbol is assigned a constant value, it becomes a parameter.

### Define Functions

If the right-hand side depends on at least one existing symbol, SCIGMA creates a
function:

```text
xSquare = x**2
omega = sqrt(k/m)
```

Functions update automatically when dependencies are changed or redefined.

### Implicit Parameters

If an expression references an unknown symbol, SCIGMA creates it as a parameter
with value `0`.

Example:

```text
y' = x**2 + a**b
```

If `a` exists and `b` does not, `b` is created as a parameter with value `0`.

### Evaluation Operator

Use `$` to evaluate an expression immediately:

```text
$(a**2)
```

Do not use `$` on the right side of equations unless the goal is to freeze the
current numeric value.

Useful examples:

```text
period $(2*pi/omega)
secval $x
```

### Delete Symbols

Delete a symbol completely:

```text
!x
```

Remove a variable from the dynamical system but keep it as a parameter:

```text
!x'
```

### Supported Math Operations

SCIGMA's internal parser supports:

```text
+ - * / **
sqrt exp ln log10
sin cos tan asin acos atan atan2
sinh cosh tanh asinh acosh atanh
pow sigmoid pulse abs sign step mod
```

Notes:

- `**` is exponentiation.
- `sigmoid(x,beta)` is `(1 + exp(-x/beta))^-1`.
- `pulse(x,beta)` is the derivative-like pulse associated with sigmoid.
- `step` behaves like GLSL `step`.
- `mod` is equivalent to C `fmod`.

## Python Equation Files

Use the `equations` command to load equations from a Python file:

```text
equations filename.py
```

The Python file may define:

```python
v_names = ['x', 'y']
v_values = [0, 0]
p_names = ['a', 'b']
p_values = [1, 2]
f_names = ['energy']
```

Required function:

```python
def f(x, xdot):
    ...
```

Possible signatures:

```python
def f(x, xdot):          # autonomous, no parameters
def f(x, p, xdot):       # autonomous, with parameters
def f(t, x, xdot):       # non-autonomous, no parameters
def f(t, x, p, xdot):    # non-autonomous, with parameters
```

Optional Jacobian:

```python
def dfdx(x, jac):
    ...
```

or with the same signature style as `f`.

Optional additional functions:

```python
def func(x, values):
    ...
```

If `f_names` is non-empty, `func` must be defined. Additional functions cannot
be used inside `f` or `dfdx`.

## Modes

Set the type of dynamical problem with:

```text
mode map
mode ode
mode strobe
mode Poincare
```

Abbreviations:

```text
mode m
mode o
mode s
mode p
```

Meaning:

- `map`: equations are interpreted as a discrete map.
- `ode`: equations are interpreted as ordinary differential equations.
- `strobe`: ODEs are sampled at a fixed period to form a stroboscopic map.
- `Poincare`: ODEs are sampled at crossings of a Poincare section.

Default mode is `ode`.

## General Commands

### `axis parameter`

Change the variable on specified axis.

Examples:
to change the parameter on y-axis from y to p use:
```text
y p
```

### `equations ['internal'|filename]`

Set equation source.

Examples:

```text
equations internal
equations lorenz.py
```

Abbreviation: `eq`

### `load [filename]`

Load and run a SCIGMA script file. If no filename is given, SCIGMA opens a file
dialog.

Abbreviation: `l`

### `select <name>`

Make an object the currently selected object.

Abbreviation: `sel`

### `delete <name>`

Delete an orbit, manifold, or special point from memory.

Abbreviation: `del`

### `clear`

Delete all orbits, manifolds, and special points.

Abbreviation: `cl`

### `reset`

Delete all objects, delete current equations, and reset the view to 2D `x` vs
`y` on `[-1,1] x [-1,1]`.

Abbreviation: `res`

### `quit`

Close the current SCIGMA window.

Abbreviations: `q`, `bye`, `end`

## Numerical Commands

For some commands, an asterisk form exists. The `*` form shows all iterates when
`nperiod` is not `1`; the non-star form shows only every `nperiod`-th iterate.

### `plot [n] [name]`

Also:

```text
plot* [n] [name]
```

Take the current state as initial condition and plot `n` steps. If `n` is not
given, one step is taken. A negative `n` reverses direction.

Generated default object name: `trN`

Abbreviations:

```text
p
p*
```

Mode-specific behavior:

- `mode map`: iterate the map and plot every `nperiod`-th point.
- `mode ode`: integrate for `n` time steps of size `dt`.
- `mode strobe`: plot every `nperiod`-th point of the stroboscopic map with
  period `period`.
- `mode Poincare`: construct a Poincare map at `secvar = secval`; use
  `secdir` for crossing direction and `maxtime` as the maximum integration time
  before giving up.

Style settings affecting new plots:

```text
color
marker.style
marker.size
point.style
point.size
delay
```

### `guess [name]`

Also:

```text
guess* [name]
```

Use the current state as a starting point and run Newton iteration to find a
stationary state.

Generated default names:

- `fpN` for fixed points of ODEs
- `ppN` for periodic points/maps

Abbreviations:

```text
g
g*
```

If `mode` is not `ode`, SCIGMA finds a stationary state of the `nperiod`-th
iterate of the map.

### `evals [name]`

Print eigenvalues of the named object. If no name is given, use the selected
object.

### `evecs [name]`

Print eigenvectors of the named object. If no name is given, use the selected
object.

### `mstable [n] [origin] [name]`

Also:

```text
mstable* [n] [origin] [name]
```

Plot a one-dimensional stable manifold from a stationary state found with
`guess`. If `origin` is omitted, use the selected object. If `name` is omitted,
generate a name like `mfN`.

Abbreviations:

```text
ms
ms*
```

Relevant settings:

```text
evec1
dt
nperiod
arc
alpha
color
marker.style
marker.size
point.style
point.size
delay
```

Notes:

- In `ode` mode, one step corresponds to integration by approximately `+/- dt`.
- In map-like modes, the manifold of the `nperiod`-th iterate is constructed.
- Both sides of the eigenvector are drawn.

### `munstable [n] [origin] [name]`

Also:

```text
munstable* [n] [origin] [name]
```

Same as `mstable`, but for unstable manifolds.

Abbreviations:

```text
mu
mu*
```

### `rtime [name]`

Print the return time for an orbit or stationary state of a stroboscopic map or
Poincare map. If no name is given, use the selected object.

Abbreviation: `rt`

### `circle <diameter> [n]`

Place `n` initial conditions equally spaced on a circle centered at the current
position. Diameter is in units of the visible phase-space region. Default
`n = 100`.

Abbreviation: `cir`

### `fill <n>`

Insert `n` equally distributed points between consecutive pairs of selected
points. Requires at least two selected points.

### `cont <n> <name>`

Reset the user sepcified axis to be the bifurcation parameter `name` before running continuation

Continue a steady state by changing parameter `name` for `n` steps using
pseudo-arclength continuation.

For two-parameter continuation, specify two names separated by a comma.

Relevant continuation settings:

```text
a0
a1
ds
dsmin
dsmax
epsl
epsu
epss
rl0
rl1
```

After a continuation run, SCIGMA auto-selects the end point of the run.

### `cycle <n> <name>`

Continue a limit cycle by changing parameter `name` for `n` steps. First select
a Hopf bifurcation point. Reports the maximum of the limit cycle.

## View And Display Commands

### `hide <name>`

Hide an object while keeping it in memory.

### `show <name>`

Show a previously hidden object.

### `2d`

Use two-dimensional projection.

### `3d`

Use three-dimensional projection.

### `xrange <min> <max>`

Set x-axis range.

### `yrange <min> <max>`

Set y-axis range.

### `zrange <min> <max>`

Set z-axis range.

### `crange <min> <max>`

Set color-axis range.

### `fit`

Adjust the viewing volume to include all visible objects.

Abbreviation: `f`

## Settings

Settings can be queried by entering the setting name alone:

```text
mode
dt
color
```

Settings can be changed by entering the setting name followed by a value:

```text
dt 0.01
color blue
axes xyz
```

Settings are also available in SCIGMA option panels.

## Numerical Settings

### `mode <map|ode|strobe|Poincare>`

Select dynamical system interpretation. Default: `ode`.

### `period <value>`

Return time for stroboscopic maps. Default: `1.0`.

### `nperiod <integer>`

Number of map periods/iterates used by algorithms. Default: `1`.

### `dt <value>`

Integrator time step for ODE-like modes. Must be positive. To plot backward in
time, use negative `n` in `plot`. Default: `0.001`.

### `secvar <varname>`

Variable defining the Poincare section. Default: `x`.

### `secval <value>`

Value defining the Poincare section. Default: `0.0`.

### `secdir <+|->`

Direction for Poincare section crossings. Default: `+`.

### `maxtime <value>`

Maximum integration time when searching for a Poincare section crossing.
Default: `100.0`.

### `eps <value>`

Initial distance for deprecated one-sided manifold commands `mu1` and `ms1`.
Default: `0.0001`.

### `ds <value>`

Arc-length step for map manifolds or pseudo-arclength continuation. Default:
`0.01`.

### `dsmin <value>`

Minimum continuation step size. Default: `1E-06`.

### `dsmax <value>`

Maximum continuation step size. Default: `1`.

### `arc <value>`

Approximate distance between points on manifolds created by `mstable` and
`munstable`.

### `rl0 <value>`

Lower bound on continuation parameter. Default: `-1E300`.

### `rl1 <value>`

Upper bound on continuation parameter. Default: `1E300`.

### `epsl <value>`

Relative convergence criterion for continuation parameters. Default: `1E-07`.

### `epsu <value>`

Relative convergence criterion for continuation solution components. Default:
`1E-07`.

### `epss <value>`

Relative convergence criterion for arclength component. Default: `1E-06`.

Recommended to be 100 to 1000 times larger than `epsl` and `epsu`.

### `alpha <value>`

Maximum accepted angle between consecutive line segments on map manifolds.
Default: `0.3` radians.

### `evec1 <integer>`

Eigenvector index used for invariant manifolds. Eigenvalues are sorted by
stability: ascending real value for ODEs and ascending modulus for maps.
Default: `1`.

### `Newton.tol <value>`

Tolerance for Newton-Raphson stationary-state search and Poincare-plane
convergence. Default: `1e-9`.

### `atol <value>`

Absolute tolerance for the ODESSA integrator. Default: `1e-9`.

### `rtol <value>`

Relative tolerance for the ODESSA integrator. Default: `1e-9`.

### `type <non-stiff|stiff>`

Select non-stiff or stiff ODESSA integration. Default: `stiff`.

### `mxiter <integer>`

Maximum internal ODESSA integration steps before giving up. Default: `500`.

## View And Style Settings

### `axes <xy|xyz|xyc|xyzc>`

Select projection:

- `xy`: 2D
- `xyz`: 3D
- `xyc`: 2D plus color map
- `xyzc`: 3D plus color map

Default: `xy`.

### `color <name|r g b [a]|index>`

Set drawing color for new objects.

Named colors:

```text
red green blue yellow pink lime azure orange brown forest navy teal rose aqua
sky beige black dark_gray gray light_gray white cyan magenta
```

RGB examples:

```text
color 1 0 1
color 1 0 1 1
```

Index form:

```text
color 6
```

Default: `red`.

### `delay <value>`

Artificial plotting delay in seconds. Default: `0.0`.

### `marker.style <style>`

Marker style for delayed plotting and stationary-state markers.

Available styles:

```text
dot plus ring rdot rplus rcross quad qdot qplus qcross hash star none
```

Default: `star`.

### `marker.size <value>`

Marker size for delayed plotting and stationary-state markers. Default: `16.0`.

### `point.style <style>`

Point style for plotting orbits, trajectories, and one-dimensional manifolds.

Available styles:

```text
dot plus ring rdot rplus rcross quad qdot qplus qcross hash star none
```

Default: `none`, which connects points with line segments.

### `point.size <value>`

Point size for plotting orbits, trajectories, and one-dimensional manifolds.
Default: `8.0`.

## LLM Command Generation Guidelines

When generating SCIGMA commands:

- Output one SCIGMA console command per line.
- Prefer full command names over abbreviations unless examples use
  abbreviations.
- Do not generate prose mixed with commands if the caller expects executable
  commands.
- Do not generate shell commands.
- Do not generate Python code unless the user explicitly asks to create or load
  a Python equation file.
- Avoid `load`, `equations <filename>`, `reset`, `quit`, and file-writing
  commands unless the user explicitly asks for them.
- If the request depends on a selected object and no selected object is known,
  ask for clarification instead of inventing an object name.
- If the request depends on an existing equation system and none is known,
  first generate equation definitions or ask for the desired system.
- Use `mode ode` for differential equations and `mode map` for iterated maps
  when the user intent is clear.
- For Poincare maps, set `mode Poincare`, `secvar`, `secval`, `secdir`, and
  possibly `maxtime`.
- For stroboscopic maps, set `mode strobe`, `period`, and possibly `nperiod`.
- For invariant manifolds, first ensure there is a stationary object from
  `guess`; then use `mstable` or `munstable`.
- For continuation, first ensure there is a steady state or bifurcation point
  selected; then use `cont` or `cycle`.

## LLM Output Contract Recommendation

For an LLM assistant, prefer structured output:

```json
{
  "type": "commands",
  "commands": [
    "mode ode",
    "x' = -y",
    "y' = omega**2*x",
    "omega = sqrt(k/m)",
    "k = 1",
    "m = 2",
    "plot 1000"
  ]
}
```

If more information is needed:

```json
{
  "type": "clarification",
  "message": "Which stationary point should I use as the origin?"
}
```

Generated commands should be passed back through SCIGMA's normal command
processor, not executed through a separate path.
