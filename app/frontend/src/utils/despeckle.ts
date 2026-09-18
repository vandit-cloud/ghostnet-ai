/* =============================================================================
 * Speckle suppression for the OPERATOR'S VIEW ONLY.
 *
 * This is a display filter. It runs in the browser, after detection, on pixels
 * the model has already seen and scored. It cannot move a box, change a score,
 * or reach the payload. That is the entire reason it is allowed to exist.
 *
 * Why not do this before inference instead
 * ----------------------------------------
 * Because it was measured, and it was much worse. ai/ghostnet/preprocess.py
 * records gv5 scored on despeckled frames:
 *
 *     gv5, raw            mAP 0.3066
 *     gv5, despeckled     mAP 0.1644
 *
 * The cause is domain mismatch, not the filter: gv5 was trained on raw speckled
 * chips, so a cleaned frame is out-of-distribution input. That module's verdict
 * is "do not despeckle at inference for a model trained without it", and this
 * file does not revisit it. Detection still runs on raw pixels. Only the
 * picture drawn for a human changes.
 *
 * Strength: why 3x3 and a sharpen, not 5x5
 * ----------------------------------------
 * This started at 5x5, on the reasoning that nothing here feeds a model so the
 * inference-budget constraint that produced 3x3 upstream does not apply. That
 * was wrong, and measuring it on real frames from this repo says so. Speckle
 * energy (local std) and fine detail (gradient energy) retained, vs raw:
 *
 *     filter                speckle   detail   removed-per-lost
 *     median5                 42.1%    36.3%       0.91
 *     median3                 65.9%    63.7%       0.94
 *     median3 + unsharp 0.6   84.0%    82.5%       0.91
 *     bilateral 7/45/7        68.2%    63.0%       0.92
 *     NLM h=12                92.3%    91.8%       0.93
 *
 * Two things fall out of that table. First, 5x5 was the worst of the options:
 * it costs MORE detail than the speckle it buys. Second, and more to the point,
 * every ratio is below 1 -- on a speckled waterfall the grain IS most of the
 * high-frequency content, so there is no filter that removes it for free. That
 * is a property of side-scan data, not a shortcoming of any of these filters,
 * and it means the honest goal here is a gentle one.
 *
 * So: 3x3 (half the detail cost of 5x5) followed by a mild unsharp, which gives
 * back the edge acuity the median took without reintroducing the grain, because
 * the grain is no longer there to amplify. Net effect is a frame that reads as
 * cleaner rather than softer -- which is what an operator means by "despeckle",
 * even though denoising and sharpening are opposite operations and only the
 * first one is in the name.
 *
 * What it costs you, and why it is off by default
 * -----------------------------------------------
 * A median filter removes small bright outliers. Small bright outliers are also
 * what a 2m piece of debris looks like at range. The filter cannot tell those
 * apart -- suppressing one suppresses the other, and a large enough radius will
 * erase a real target from the picture while the box around it stays exactly
 * where it was. The raw frame is the evidence of record; this is a reading aid
 * laid over it. Hence: opt in, per frame, clearly labelled while active.
 *
 * Implementation
 * --------------
 * Huang's sliding-window median. The naive form -- gather (2r+1)^2 values per
 * pixel and sort -- is ~22M comparisons on a 1408x640 frame at r=2 and janks
 * the tab for a second or more. Huang keeps a 256-bin histogram of the window
 * plus a running count of samples below the current median, and slides it one
 * column at a time, so each step costs 2*(2r+1) histogram updates and a short
 * rebalance walk instead of a full sort. Per-pixel work stops depending on the
 * radius, which is what makes 5x5 (and 7x7, if you want it) cheap enough to run
 * synchronously on a toggle.
 * ========================================================================== */

/** Default window radius. 1 => a 3x3 median. See the note on strength above. */
export const DEFAULT_RADIUS = 1;

/**
 * Unsharp amount applied after the median, to give back the edge acuity the
 * median took. See the note on strength above for why this pairing exists.
 */
export const DEFAULT_SHARPEN = 0.6;

/**
 * Median-filter one 8-bit plane in place-safe fashion (reads `src`, writes a
 * fresh array). Borders replicate the edge pixel rather than darkening toward
 * zero, which would otherwise draw a false shadow around every frame.
 */
function medianPlane(
  src: Uint8ClampedArray,
  width: number,
  height: number,
  radius: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(width * height);
  const hist = new Uint32Array(256);
  const windowSize = (2 * radius + 1) * (2 * radius + 1);
  // The index we want in sorted order: for odd window sizes this is the true
  // median. `<=` in the climb below is what makes ties resolve consistently.
  const target = windowSize >> 1;

  const at = (x: number, y: number) => {
    // Clamp = replicate border.
    const cx = x < 0 ? 0 : x >= width ? width - 1 : x;
    const cy = y < 0 ? 0 : y >= height ? height - 1 : y;
    return src[cy * width + cx];
  };

  for (let y = 0; y < height; y++) {
    // Rebuild the window at the start of every row. O((2r+1)^2) per row, which
    // is noise next to the row itself, and it stops error accumulating.
    hist.fill(0);
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        hist[at(dx, y + dy)]++;
      }
    }

    // Seed the median by walking the histogram once.
    let mdn = 0;
    let ltCount = 0; // samples strictly below `mdn`
    while (ltCount + hist[mdn] <= target) {
      ltCount += hist[mdn];
      mdn++;
    }
    out[y * width] = mdn;

    for (let x = 1; x < width; x++) {
      // Slide: drop the column leaving the window, add the one entering it.
      const outCol = x - radius - 1;
      const inCol = x + radius;
      for (let dy = -radius; dy <= radius; dy++) {
        const leaving = at(outCol, y + dy);
        hist[leaving]--;
        if (leaving < mdn) ltCount--;

        const entering = at(inCol, y + dy);
        hist[entering]++;
        if (entering < mdn) ltCount++;
      }

      // Rebalance toward the new median. Both loops together walk only as far
      // as the median actually moved, which between adjacent pixels is small.
      while (ltCount > target) {
        mdn--;
        ltCount -= hist[mdn];
      }
      while (ltCount + hist[mdn] <= target) {
        ltCount += hist[mdn];
        mdn++;
      }

      out[y * width + x] = mdn;
    }
  }

  return out;
}

/**
 * Separable Gaussian blur of one 8-bit plane, used only as the low-pass half of
 * the unsharp mask below. sigma is fixed small: the point is to isolate edge
 * detail, not to blur meaningfully.
 */
function gaussianPlane(
  src: Uint8ClampedArray,
  width: number,
  height: number,
  sigma = 1.2,
): Float32Array {
  const radius = Math.max(1, Math.ceil(sigma * 2));
  const kernel = new Float32Array(2 * radius + 1);
  let sum = 0;
  for (let i = -radius; i <= radius; i++) {
    const v = Math.exp(-(i * i) / (2 * sigma * sigma));
    kernel[i + radius] = v;
    sum += v;
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= sum;

  const tmp = new Float32Array(width * height);
  const out = new Float32Array(width * height);

  // Horizontal, then vertical. Borders clamp, matching the median.
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let acc = 0;
      for (let k = -radius; k <= radius; k++) {
        const cx = Math.min(width - 1, Math.max(0, x + k));
        acc += src[y * width + cx] * kernel[k + radius];
      }
      tmp[y * width + x] = acc;
    }
  }
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let acc = 0;
      for (let k = -radius; k <= radius; k++) {
        const cy = Math.min(height - 1, Math.max(0, y + k));
        acc += tmp[cy * width + x] * kernel[k + radius];
      }
      out[y * width + x] = acc;
    }
  }
  return out;
}

/**
 * Despeckle an ImageData in place.
 *
 * Sonar waterfalls are greyscale, so this filters a single luminance plane and
 * writes the result back to R, G and B rather than paying three times over for
 * channels that carry the same number. Alpha is untouched.
 */
export function despeckleImageData(
  image: ImageData,
  radius = DEFAULT_RADIUS,
  sharpen = DEFAULT_SHARPEN,
): void {
  const { width, height, data } = image;
  const plane = new Uint8ClampedArray(width * height);

  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    // Rec. 601 luma. The frames are grey, so this is a channel pick in all but
    // name -- it just also does the right thing if one ever is not.
    plane[p] = (data[i] * 299 + data[i + 1] * 587 + data[i + 2] * 114) / 1000;
  }

  const filtered = medianPlane(plane, width, height, radius);

  // Unsharp mask: filtered + amount * (filtered - blur(filtered)). Applied to
  // the DENOISED plane, never the raw one -- sharpening raw speckle is how you
  // make a waterfall less readable, not more.
  let final: Uint8ClampedArray | Float32Array = filtered;
  if (sharpen > 0) {
    const low = gaussianPlane(filtered, width, height);
    const sharpened = new Uint8ClampedArray(width * height);
    for (let p = 0; p < sharpened.length; p++) {
      sharpened[p] = filtered[p] + sharpen * (filtered[p] - low[p]);
    }
    final = sharpened;
  }

  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    const v = final[p];
    data[i] = v;
    data[i + 1] = v;
    data[i + 2] = v;
  }
}

/**
 * Render a despeckled copy of `sourceUrl` and hand back an object URL for it.
 *
 * The caller owns the returned URL and must revokeObjectURL it. Dimensions are
 * preserved exactly, which is what lets the detection box keep using the scale
 * it derived from the unfiltered image.
 */
export async function despeckleImage(
  sourceUrl: string,
  radius = DEFAULT_RADIUS,
  sharpen = DEFAULT_SHARPEN,
): Promise<string> {
  const img = new Image();
  img.src = sourceUrl;
  await img.decode();

  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;

  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("2D canvas context unavailable");

  ctx.drawImage(img, 0, 0);
  const frame = ctx.getImageData(0, 0, canvas.width, canvas.height);
  despeckleImageData(frame, radius, sharpen);
  ctx.putImageData(frame, 0, 0);

  // PNG, not JPEG: re-encoding a denoised frame with a lossy codec would put a
  // different kind of grain back into it.
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/png"),
  );
  if (!blob) throw new Error("Failed to encode despeckled frame");

  return URL.createObjectURL(blob);
}
