import { useEffect } from "react";
import { MessageSquareText } from "lucide-react";
import { useResource } from "../api/hooks";

export const DEFAULT_BRAND_COLORS = {
  brand_dark: "#3b4b32",
  brand_primary: "#4a5d3f",
  brand_light: "#657b57",
  brand_accent: "#b88d4b",
  brand_gold: "#d4a860",
  brand_bg: "#f7f8f4",
  brand_card: "#ffffff",
  sidebar_item_bg: "#edf1e8",
} as const;

export type BrandColors = Record<keyof typeof DEFAULT_BRAND_COLORS, string>;

export type BrandingData = {
  colors: BrandColors;
  logo_url: string | null;
  logo_version: number;
  updated_at: string | null;
};

function rgb(color: string) {
  return [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16));
}

function luminance(color: string) {
  const channels = rgb(color).map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(first: string, second: string) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

export function readableForeground(background: string) {
  const whiteContrast = contrastRatio(background, "#ffffff");
  const ink = "#171717";
  return whiteContrast >= contrastRatio(background, ink) ? "#ffffff" : ink;
}

function accentInk(accent: string, surface: string) {
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

export function applyBranding(data: BrandingData) {
  const root = document.documentElement;
  const safeColors = {} as BrandColors;
  for (const [key, fallback] of Object.entries(DEFAULT_BRAND_COLORS)) {
    const value = data.colors[key as keyof BrandColors];
    const safeValue = typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value) ? value : fallback;
    safeColors[key as keyof BrandColors] = safeValue;
    root.style.setProperty(`--${key.replaceAll("_", "-")}`, safeValue);
  }
  root.style.setProperty(
    "--brand-accent-ink",
    accentInk(safeColors.brand_accent, safeColors.brand_card),
  );
  root.style.setProperty("--brand-accent-foreground", readableForeground(safeColors.brand_accent));
  root.style.setProperty("--brand-gold-foreground", readableForeground(safeColors.brand_gold));
  root.style.setProperty("--sidebar-item-ink", readableForeground(safeColors.sidebar_item_bg));
}

export function useBranding() {
  const branding = useResource<BrandingData>("/branding", "ar");
  useEffect(() => {
    if (branding.data) applyBranding(branding.data);
  }, [branding.data]);
  return branding.data;
}

export function BrandingRuntime() {
  useBranding();
  return null;
}

export function BrandMark({ size = 22 }: { size?: number }) {
  const branding = useBranding();
  return branding?.logo_url ? (
    <img className="brand-custom-logo" src={branding.logo_url} alt="" aria-hidden="true" />
  ) : (
    <MessageSquareText size={size} aria-hidden="true" />
  );
}
