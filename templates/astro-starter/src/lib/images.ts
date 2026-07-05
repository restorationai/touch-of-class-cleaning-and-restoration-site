// Responsive image helper — pairs with scripts/resize_images.py, which
// generates {stem}-480w.webp / -768w.webp / -1200w.webp variants and writes
// src/data/image-meta.json with the original dimensions + available widths.
import rawMeta from "../data/image-meta.json";

type ImageMeta = { width: number; height: number; variants?: number[] };
const meta = rawMeta as Record<string, ImageMeta>;

export interface ResponsiveImgAttrs {
  srcset?: string;
  width?: number;
  height?: number;
}

/**
 * Look up `src` (local path or full URL, exactly as rendered) in the generated
 * manifest. Returns a srcset built only from verified -{w}w.webp variants plus
 * the original's intrinsic width/height. Unknown srcs return {} so the <img>
 * renders exactly as it did before this pass — we never emit a srcset for an
 * unverified variant.
 */
export function srcsetFor(src: string): ResponsiveImgAttrs {
  const m = meta[src];
  if (!m) return {};
  const attrs: ResponsiveImgAttrs = { width: m.width, height: m.height };
  const widths = (m.variants ?? []).filter((w) => w < m.width);
  if (widths.length === 0) return attrs;
  const stem = src.replace(/\.(webp|png|jpe?g)$/i, "");
  const parts = widths.map((w) => `${stem}-${w}w.webp ${w}w`);
  // Include the original as the largest candidate only when it is already
  // WebP — oversized PNG originals are deliberately left out of the srcset.
  if (/\.webp$/i.test(src)) parts.push(`${src} ${m.width}w`);
  attrs.srcset = parts.join(", ");
  return attrs;
}
