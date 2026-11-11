/**
 * Sprites pixel art des huit agents.
 * Chaque personnage partage la même base, avec une silhouette et des
 * accessoires distincts (lunettes, casque, casquette, barbe, cravate…).
 */

const OUTLINE = "#0a1220";

function rect(x, y, width, height, fill, extra = "") {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="${fill}" ${extra}/>`;
}

function hairBack(kind, color) {
  if (kind === "long") {
    return [
      rect(-15, -73, 30, 30, color, `rx="6" stroke="${OUTLINE}" stroke-width="2"`),
      rect(-16, -64, 6, 23, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.5"`),
      rect(10, -64, 6, 23, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.5"`),
    ].join("");
  }
  if (kind === "ponytail") {
    return [
      rect(12, -70, 8, 22, color, `rx="3" stroke="${OUTLINE}" stroke-width="1.5"`),
      rect(16, -56, 7, 12, color, `rx="3" stroke="${OUTLINE}" stroke-width="1.5"`),
    ].join("");
  }
  return "";
}

function hairFront(kind, color) {
  if (kind === "long" || kind === "ponytail") {
    return [
      rect(-13, -76, 26, 9, color, `rx="3" stroke="${OUTLINE}" stroke-width="1.5"`),
      rect(-12, -70, 5, 7, color),
      rect(7, -70, 5, 7, color),
    ].join("");
  }
  if (kind === "curly") {
    return [
      rect(-13, -76, 26, 9, color, `rx="3" stroke="${OUTLINE}" stroke-width="1.5"`),
      rect(-15, -72, 7, 7, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.2"`),
      rect(8, -72, 7, 7, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.2"`),
      rect(-10, -79, 8, 6, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.2"`),
      rect(2, -80, 8, 6, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.2"`),
    ].join("");
  }
  if (kind === "cap") {
    return [
      rect(-12, -77, 24, 7, color, `rx="2" stroke="${OUTLINE}" stroke-width="1.5"`),
      rect(-16, -72, 13, 4, color, `rx="1" stroke="${OUTLINE}" stroke-width="1.2"`),
      rect(-12, -71, 24, 4, color),
    ].join("");
  }
  // short
  return [
    rect(-12, -76, 24, 8, color, `rx="3" stroke="${OUTLINE}" stroke-width="1.5"`),
    rect(-12, -70, 4, 6, color),
    rect(8, -70, 4, 6, color),
  ].join("");
}

function glasses() {
  return `
    <g fill="none" stroke="${OUTLINE}" stroke-width="1.3">
      <rect x="-8" y="-66" width="7" height="7" rx="1"/>
      <rect x="1" y="-66" width="7" height="7" rx="1"/>
      <path d="M-1 -63h2"/>
    </g>`;
}

function headset() {
  return `
    <path d="M-13 -70 Q0 -83 13 -70" fill="none" stroke="${OUTLINE}" stroke-width="3"/>
    <rect x="-18" y="-68" width="5" height="10" rx="2" fill="#1f2937" stroke="${OUTLINE}" stroke-width="1.5"/>
    <rect x="13" y="-68" width="5" height="10" rx="2" fill="#1f2937" stroke="${OUTLINE}" stroke-width="1.5"/>
    <rect x="-8" y="-47" width="5" height="3" rx="1" fill="#1f2937"/>
    <rect x="-9" y="-44" width="3" height="6" rx="1" fill="#1f2937"/>
  `;
}

function beard(color) {
  return `
    <rect x="-10" y="-56" width="20" height="7" rx="2" fill="${color}" opacity=".92"/>
    <rect x="-2" y="-55" width="5" height="2" fill="#8a4b3a"/>
  `;
}

function tie() {
  return `
    <path d="M0 -49 L5 -42 L2 -28 L-2 -28 L-5 -42 Z" fill="#0f172a" stroke="${OUTLINE}" stroke-width="1"/>
    <path d="M0 -47 L3 -42 L0 -35 L-3 -42 Z" fill="#ef4444"/>
  `;
}

export function spriteMarkup(sprite) {
  const skin = sprite.skin || "#e8b48c";
  const hair = sprite.hair_color || "#1f2937";
  const shirt = sprite.shirt || "#3b82f6";
  const pants = sprite.pants || "#24324f";
  const kind = sprite.hair || "short";
  const accessory = sprite.accessory || "none";

  return `
    <ellipse cx="0" cy="2" rx="21" ry="6" fill="#03070f" opacity=".45"/>
    ${hairBack(kind, hair)}

    <!-- jambes et chaussures -->
    ${rect(-10, -22, 8, 19, pants, `stroke="${OUTLINE}" stroke-width="1.5"`)}
    ${rect(2, -22, 8, 19, pants, `stroke="${OUTLINE}" stroke-width="1.5"`)}
    ${rect(-12, -6, 11, 6, "#101827", `rx="1" stroke="${OUTLINE}" stroke-width="1.5"`)}
    ${rect(1, -6, 11, 6, "#101827", `rx="1" stroke="${OUTLINE}" stroke-width="1.5"`)}

    <!-- corps -->
    <rect class="sprite-body" x="-13" y="-48" width="26" height="29" rx="3" fill="${shirt}" stroke="${OUTLINE}" stroke-width="2"/>
    <rect x="-13" y="-25" width="26" height="5" fill="${pants}" opacity=".95"/>
    <rect x="-2" y="-46" width="4" height="19" fill="#ffffff" opacity=".13"/>

    <!-- bras -->
    <rect class="sprite-arm" x="-19" y="-46" width="6" height="21" rx="2" fill="${shirt}" stroke="${OUTLINE}" stroke-width="1.5"/>
    ${rect(-19, -27, 6, 6, skin, `rx="1" stroke="${OUTLINE}" stroke-width="1.2"`)}
    <rect x="13" y="-46" width="6" height="21" rx="2" fill="${shirt}" stroke="${OUTLINE}" stroke-width="1.5"/>
    ${rect(13, -27, 6, 6, skin, `rx="1" stroke="${OUTLINE}" stroke-width="1.2"`)}

    <!-- tête -->
    <rect x="-11" y="-70" width="22" height="20" rx="4" fill="${skin}" stroke="${OUTLINE}" stroke-width="2"/>
    ${rect(-14, -62, 4, 7, skin, `rx="1" stroke="${OUTLINE}" stroke-width="1.2"`)}
    ${rect(10, -62, 4, 7, skin, `rx="1" stroke="${OUTLINE}" stroke-width="1.2"`)}
    ${rect(-6, -63, 3, 4, "#0a1220")}
    ${rect(3, -63, 3, 4, "#0a1220")}
    ${rect(-2, -55, 5, 2, "#8a4b3a")}
    ${rect(-9, -57, 3, 2, "#e58f8f", 'opacity=".5"')}

    ${hairFront(kind, hair)}

    ${accessory === "glasses" ? glasses() : ""}
    ${accessory === "headset" ? headset() : ""}
    ${accessory === "beard" ? beard(hair) : ""}
    ${accessory === "tie" ? tie() : ""}
  `;
}
