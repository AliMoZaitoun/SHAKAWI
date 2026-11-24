const DEFAULT_BRAND_COLORS = {
  brand_dark: "#3b4b32",
  brand_primary: "#4a5d3f",
  brand_light: "#657b57",
  brand_accent: "#b88d4b",
  brand_gold: "#d4a860",
  brand_bg: "#f7f8f4",
  brand_card: "#ffffff",
};

function rgb(color) {
  return [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16));
}

function luminance(color) {
  const channels = rgb(color).map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first, second) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

function readableForeground(background) {
  const ink = "#171717";
  return contrastRatio(background, "#ffffff") >= contrastRatio(background, ink) ? "#ffffff" : ink;
}

function accentInk(accent, surface) {
  if (contrastRatio(accent, surface) >= 4.5) return accent;
  const source = rgb(accent);
  for (let amount = 0.04; amount <= 1; amount += 0.04) {
    const candidate = `#${source
      .map((channel) => Math.round(channel * (1 - amount)).toString(16).padStart(2, "0"))
      .join("")}`;
    if (contrastRatio(candidate, surface) >= 4.5) return candidate;
  }
  return "#283128";
}

function applyBranding(payload) {
  const colors = payload?.colors && typeof payload.colors === "object" ? payload.colors : {};
  const safeColors = {};
  for (const [key, fallback] of Object.entries(DEFAULT_BRAND_COLORS)) {
    const value = colors[key];
    safeColors[key] = typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value) ? value : fallback;
    document.documentElement.style.setProperty(`--${key.replaceAll("_", "-")}`, safeColors[key]);
  }
  document.documentElement.style.setProperty(
    "--brand-accent-ink",
    accentInk(safeColors.brand_accent, safeColors.brand_card),
  );
  document.documentElement.style.setProperty(
    "--brand-accent-foreground",
    readableForeground(safeColors.brand_accent),
  );
  document.documentElement.style.setProperty(
    "--brand-gold-foreground",
    readableForeground(safeColors.brand_gold),
  );

  const logo = document.getElementById("site-brand-logo");
  const fallback = document.getElementById("brand-logo-fallback");
  const logoVersion = Number.isSafeInteger(payload?.logo_version) ? payload.logo_version : 0;
  if (logo && fallback && payload?.logo_url) {
    logo.src = `/api/v1/branding/logo?v=${logoVersion}`;
    logo.hidden = false;
    fallback.hidden = true;
  } else if (logo && fallback) {
    logo.removeAttribute("src");
    logo.hidden = true;
    fallback.hidden = false;
  }
}

export async function loadLegacyBranding() {
  const response = await fetch("/api/v1/branding", { cache: "no-store" });
  if (!response.ok) throw new Error(`Brand settings request failed (${response.status})`);
  applyBranding(await response.json());
}
