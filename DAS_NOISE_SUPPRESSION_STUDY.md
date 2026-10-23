# DAS Noise Suppression: Findings, Methods, and Study Guide

Notes from the analysis of `TST-002d`, third step (`3e stap, hark`), on
2026-10-23.

**You can suppress this kind of noise without relying only on a temporal
bandpass. The most promising route is to exploit the spatial coherence of the
seismic signal, while accounting for the spatial correlation of the noise.**

The analysis inspected both the
[third-step plot](outputs/TST-002d_3e_stap__hark_waterfall_psd.png) and its
underlying HDF5 samples. The observation of broadband noise is supported by
the data, but there is an important additional finding: **the noise is
approximately white in time, but not white across channels.** That distinction
matters when choosing a filter.

No denoising was applied to the output files during this analysis.

## 1. What the recording actually shows

Using the ten seconds before the third-step timestamp:

| Diagnostic | Observation |
|---|---|
| Sampling frequency | 625 Hz |
| Channel spacing, from the distance array | Approximately 2.04 m |
| Gauge length in the recording header | Approximately 4.09 m |
| Median channel standard deviation, 420-480 m | Approximately 1,998 counts |
| Same statistic, 620-780 m | Approximately 23.8 counts |
| Background amplitude ratio between those regions | Approximately **84 times**, or **38.5 dB** |
| Background energy within 270-580 m | Approximately **97%** of the plotted array's squared counts |
| Temporal PSD in the noisy region | Approximately flat over 10-200 Hz |

These are background comparisons, **not a calibrated SNR measurement**:
different cable sections can have different strain responses and coupling,
and the pre-event window is not guaranteed to be completely signal-free.

### The particularly useful finding: short-range spatial correlation

Within 420-480 m, the median correlations between channels were approximately:

| Channel separation | Distance separation | Correlation |
|---|---:|---:|
| 1 | 2.0 m | +0.31 |
| 2 | 4.1 m | -0.30 |
| 3 | 6.1 m | -0.16 |
| 4 | 8.2 m | -0.03 |
| 6 | 12.3 m | Approximately zero |

A similar pattern occurs in another event window.

This suggests a useful working model:

$$
x_i(t)=s_i(t)+n_i(t),
$$

where the noise variance changes strongly with channel, and neighbouring noise
traces are partially correlated.

**It does not establish the physical cause.** Optical fading, interrogator
processing, spatial differencing, and cable/coupling effects are possibilities
to investigate. The negative correlation near one gauge-length separation is
worth noting, but is not proof of a particular mechanism.

Also, the largest mode of the local, standardized channel correlation matrix
explains only about 11% of its variance. That makes **one dominant common-mode
noise trace** an unlikely complete explanation.

### A bandpass can still help, but only partly

In the quieter sections, post-event power increases mainly below approximately
80 Hz. For example, the 10-30 Hz band increases by around 6-10 dB relative to
the pre-event interval, while 80-250 Hz changes little.

So a carefully chosen bandpass could improve visibility. However:

> It cannot separate signal and noise that occupy the same frequencies, and
> it cannot recover signal already buried beneath the remaining in-band noise.

The spatial dimension offers the additional information needed.

## 2. The options to consider

| Method | What distinguishes signal from noise? | Suitability here |
|---|---|---|
| Channel normalization | Nothing: it changes display scaling | Useful diagnostic, **not denoising** |
| Local, slope-aligned stacking / f-k filtering | Propagating wavefronts are spatially coherent | **First method to benchmark** |
| Covariance-aware spatial filtering | Measured noise covariance plus an assumed wavefield | **Especially relevant to the measured noise** |
| Local f-x prediction / SSA / MSSA | Wavefields have predictable spatial structure | **Strong alternative** |
| Curvelet / seislet denoising | Wavefronts are sparse in a directional representation | Good for curved or varying arrivals |
| Guarded self-supervised neural denoising | Signal is predictable beyond the noise-correlation range | Promising, but requires careful mask design |
| Twin-fibre Noise2Noise | Two measurements share signal but have independent noise | Excellent if suitable paired recordings exist |
| Acquisition-side mitigation | Prevent the noise rather than reconstruct through it | Important if the problem persists at fixed locations |

### Option A: Local, slope-aligned stacking and f-k filtering

**This is where I would start.**

A seismic arrival usually appears on several channels with a systematic time
delay. Random noise does not follow that same moveout.

The basic procedure is:

1. Estimate the local arrival slope.
2. Shift neighbouring traces so that the desired arrival aligns.
3. Combine them using suitable weights.
4. Reconstruct the wavefield on the original grid.

This is related to slant stacking, beamforming, local f-k filtering, and
structure-oriented smoothing.

#### Why not just average adjacent channels?

Simple, **unshifted** spatial averaging was tested on the pre-event noisy
interval:

| Averaging aperture | Background standard-deviation reduction |
|---|---:|
| 3 channels, spanning approximately 4.1 m | 4.7 dB |
| 5 channels, spanning approximately 8.2 m | 8.0 dB |
| 9 channels, spanning approximately 16.3 m | 13.9 dB |

Those are real background reductions, **not demonstrated SNR improvements**.

The danger is signal cancellation. For the measured channel spacing, a
nine-channel unshifted average would attenuate an ideal plane wave with a 20 m
spatial wavelength by approximately **21 dB**. It could therefore remove more
signal than noise.

**Aligning the wavefront before averaging is the crucial improvement.**

#### Important limitations

- Different arrivals may have different slopes.
- Near-source wavefronts are curved.
- Dispersive surface waves need frequency-dependent treatment.
- A cable that doubles back must be processed with its geometry in mind.
- Sharp f-k masks can create ringing; use smooth transitions and overlapping
  windows.

For the visible curved/repeated arrivals, **local processing** is preferable
to one global velocity wedge across the whole fibre.

### Option B: Noise-covariance-aware filtering

This is the most directly matched to the short-range, sign-changing noise
correlation found in the data.

Instead of assuming independent, equally noisy channels, estimate a local
noise covariance matrix:

$$
R_n(f)=E\!\left[n(f)n(f)^H\right].
$$

It describes both:

- which channels are noisy;
- how their noise is correlated at each frequency.

An example is **MVDR beamforming**, widely used in array processing, radar and
audio:

$$
w(f)=
\frac{R_n(f)^{-1}a(f)}
{a(f)^H R_n(f)^{-1}a(f)}.
$$

Here, \(a(f)\) describes the phase delays of the desired wavefront. The filter
minimizes output noise while maintaining unit response to that assumed
wavefront.

**Why it is attractive here:** ordinary averaging ignores the measured
positive and negative correlations. Covariance-aware weights can use them.

**Why it is not a magic solution:** preservation is conditional on the
wavefield model being correct. A wrong slope can attenuate a real arrival.
Several crossing arrivals require a more elaborate model than one steering
vector.

Practical requirements:

- Estimate covariance from multiple genuinely quiet windows.
- Estimate it locally, rather than treating 450 m and 700 m as statistically
  equivalent.
- Use regularization, such as shrinkage or diagonal loading.
- For frequency-dependent covariance, collect enough independent spectral
  estimates.
- Evaluate amplitude and phase preservation explicitly.

**Whitening alone is not denoising.** It can make noise easier for a subsequent
algorithm to handle, but a signal model or regularization is still needed.

This is an array-processing recommendation based on the measured statistics,
rather than a claim that one particular DAS paper has already validated it
for this experiment.

### Option C: Local f-x prediction, SSA and MSSA

These are established seismic methods and deserve a serious benchmark before
moving to neural networks.

At a fixed temporal frequency, a locally propagating wave has an approximately
predictable phase progression across channels. A small number of wavefronts
can therefore have a compact representation.

Methods include:

- **f-x predictive filtering:** predict a trace from surrounding traces;
- **SSA/MSSA:** arrange the data into structured matrices and retain the
  signal-related low-rank structure;
- **damped rank reduction:** attenuate components gradually rather than using
  a hard cutoff.

An important distinction:

> The **signal** should have a low-rank representation. The noise does not need
> to be low-rank; higher-rank noise is exactly what these methods aim to
> suppress.

The strong channel-to-channel noise variation means an unweighted decomposition
could be dominated by the bad section. A **noise-weighted or covariance-aware,
local version** would be preferable.

Main risks:

- Too small a retained rank removes weak arrivals.
- Too large a rank retains noise.
- Curved, crossing or rapidly changing wavefronts require smaller windows or
  richer models.
- Reconstruction over extremely noisy channels is an estimate, not a recovered
  independent observation.

A foundational reference is **Oropeza & Sacchi (2011),
[Simultaneous seismic data denoising and reconstruction via multichannel
singular spectrum analysis](https://doi.org/10.1190/1.3552706).**

### Option D: Curvelets and seislets

These exploit a different property: **seismic wavefronts are geometrically
organized**, even when they are broadband.

- **Curvelets** represent structures at multiple scales and directions
  efficiently.
- **Seislets** adapt the representation to estimated local seismic slopes.

The workflow is to transform the data, suppress coefficients consistent with
noise, and reconstruct.

These methods can be useful when a single f-k wedge is too restrictive, for
example, with curved arrivals or varying slopes.

For these data, thresholds should depend on location and scale. One global
threshold would either:

- leave much of the 450 m noise untouched; or
- over-suppress useful signal in quieter sections.

They are not automatically amplitude preserving. Weak high-frequency arrivals
can be removed along with noise.

Relevant primary sources:

- **Fomel & Liu (2010),
  [Seislet transform and seislet frame](https://doi.org/10.1190/1.3380591).**
- **Herrmann & Hennenfent (2008),
  [Non-parametric seismic data recovery with curvelet frames](https://doi.org/10.1111/j.1365-246X.2007.03698.x).**

### Option E: Self-supervised neural denoising, with correlation-aware masking

This is a genuinely useful modern direction, especially when clean training
data are unavailable.

A network predicts a withheld part of the recording from surrounding data.
The intended principle is:

- neighbouring observations contain information about the signal;
- they should not contain predictable copies of the withheld noise.

The second condition is the problem here.

**The adjacent channels have measurable noise correlation.** A network that
hides only one sample, or one channel while retaining immediately adjacent
channels, can learn to reproduce some of that noise.

For this recording, investigate:

- wider spatial blind masks;
- temporal guard intervals where needed;
- masks based on measured local correlation, not just gauge length;
- different noise models for different cable sections.

The observed correlation extending through roughly three channel offsets means
a single-pixel blind spot is not a safe default. The actual guard zone should
be determined from spatial and temporal cross-correlation diagnostics, not
fixed from these few summary numbers.

There is also a trade-off: a wider mask removes noisy predictors, but also
removes nearby signal information. Highly localized events may then become
difficult to reconstruct faithfully.

Relevant research:

- **van den Ende et al.,
  [A Self-Supervised Deep Learning Approach for Blind Denoising and Waveform
  Coherence Enhancement in Distributed Acoustic Sensing
  Data](https://doi.org/10.1109/TNNLS.2021.3132832)**: the jDAS approach;
  assumes spatio-temporally incoherent noise.
- **Birnie & Ravasi (2022 preprint),
  [Transfer learning for self-supervised, blind-spot seismic
  denoising](https://arxiv.org/abs/2209.12210)**: explicitly addresses
  degradation in the presence of correlated noise.
- **Birnie & Ravasi (2023 preprint),
  [Explainable Artificial Intelligence driven mask design for self-supervised
  seismic denoising](https://arxiv.org/abs/2307.06682)**: uses network Jacobians
  to help identify an effective blind-mask shape.

**The last approach is particularly relevant to this problem:** it addresses
how to choose the mask when noise has structure, rather than assuming that
neighbouring samples are independent.

It should still be benchmarked against classical methods. A network trained
on earthquakes is not automatically reliable for rake/footstep-type sources.

### Option F: Twin-fibre Noise2Noise

**Potentially excellent if the acquisition supports it.**

If two fibres in the same cable record approximately the same ground
deformation but have independent observational noise, they can provide paired
noisy training examples.

**DAS-N2N uses precisely this idea.** It is not simply an odd/even-channel
split.

The paper uses two spliced fibres within one cable to record the same
underlying signal with different noise realizations. After training, only a
single noisy fibre is required.

Reference: **Lapins et al.,
[DAS-N2N: Machine learning Distributed Acoustic Sensing signal denoising without
clean data](https://arxiv.org/abs/2304.08120)**: 2023 preprint, published in
*GJI* in 2024.

This could be attractive if the fibre layout includes appropriately colocated
repeat measurements. However, establish:

- physical correspondence;
- timing alignment;
- compatible directional response and amplitude scaling;
- sufficiently independent noise.

**Different footsteps or rake strokes are not automatically valid Noise2Noise
pairs.** They need not share the same underlying waveform.

## 3. Methods not to use as the main solution

### Channel normalization

The existing `NORMALIZE_CHANNELS` option can make the bands less visually
dominant. But it scales signal and noise together.

**It does not improve the SNR of an individual channel.**

In the current plot, approximately 90% of samples in the 420-480 m region
exceed the displayed colour limit. That explains some of the visual severity,
but changing the colour scale does not recover buried signal.

### Subtracting one common trace or principal component

This works when a genuinely coherent nuisance dominates the array. The local
statistics do not indicate that this explains most of the noisy band.

It can also remove real, spatially coherent seismic signal.

A useful recent contrast is **Forbriger et al. (2026 preprint),
[Cemented fibers as a testbed for distributed acoustic sensing](https://arxiv.org/abs/2603.24353)**.
They demonstrate common-mode laser-noise subtraction in their acquisition.
That supports the method **when its physical/statistical assumptions hold**,
not applying it indiscriminately here.

### Aggressive generative or diffusion denoising

These are research options, but they would not be the starting point for
quantitative measurements. A plausible-looking reconstructed wavefield is not
evidence that its detailed amplitudes or arrivals were present in the
measurement.

At the low local signal visibility here, that distinction becomes especially
important.

## 4. How to verify that noise was removed, not signal

This should be part of the method selection, not an afterthought.

### A. Inject known signals into real background data

Use actual quiet recordings from the noisy section, then add synthetic
arrivals with known:

- amplitudes and frequency content;
- slopes and curvature;
- onset times;
- crossing arrivals;
- spatial localization.

Include signals substantially weaker than the noise and signals unlike those
used for tuning.

Measure reconstruction error against the known injection.

### B. Inspect the removed component

Always inspect:

$$
r=x-\hat{s}.
$$

If the residual contains recognizable propagating arrivals, the filter has
removed signal.

But a noise-looking residual alone does not prove fidelity; also measure
amplitude, phase, timing and spectral errors.

### C. Evaluate locally

The array-wide PSD is currently dominated by the noisy band. Report results
separately for:

- the bad section;
- transition sections;
- quieter sections.

A large reduction in global RMS can conceal loss of weak signals.

### D. Preserve measurement provenance

Keep separate products for:

1. original calibrated/raw data;
2. denoised estimates;
3. quality masks and processing parameters.

If some channels cannot support a reliable estimate, marking them as
unreliable is scientifically preferable to silently filling them with plausible
waveforms.

## 5. Recommended order for this dataset

1. **Build a channel-noise and correlation map** from several quiet intervals.
2. **Benchmark local slope-aligned filtering**, with conservative apertures
   and smooth transitions.
3. Compare it against **noise-weighted local MSSA/f-x processing**.
4. Add **covariance-aware weighting** where the measured short-range noise
   correlations materially improve the result.
5. Only then test **correlation-aware self-supervised denoising**, using
   injection tests and held-out events.
6. Investigate optical quality and coupling around the persistent bad section,
   because preventing the noise may outperform any post-processing.

**Bottom line:** the strongest opportunity is not "find a better temporal
filter." It is **combine neighbouring measurements according to the
wavefield's propagation, while explicitly modelling how the noise varies and
correlates across the fibre**. The data show enough spatial noise structure
that this is worth testing, and enough noise severity that signal-preservation
checks are essential.
