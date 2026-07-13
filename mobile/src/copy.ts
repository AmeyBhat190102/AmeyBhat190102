/** The studio's voice, shared across screens. Same language the website
 * speaks — nothing here should read like an app wrote it. */

export interface ArtifactType {
  key: string;
  name: string;
  reason: string;
}

export const ARTIFACTS: ArtifactType[] = [
  { key: "visiting-card", name: "Visiting cards", reason: "the handshake that stays behind" },
  { key: "wedding-suite", name: "Wedding suites", reason: "lineage, held in the hand" },
  { key: "book-cover", name: "Book covers", reason: "the argument before page one" },
  { key: "letterhead", name: "Letterheads", reason: "authority at document scale" },
  { key: "product-film", name: "Product films", reason: "8 seconds of presence, from one photo" },
  { key: "brand-mark", name: "Brand marks", reason: "a silhouette that survives being small" },
];

export const ROLE_LABELS: Record<string, string> = {
  layout_designer: "Layout typographer",
  cover_artist: "Cover artist",
  cinematographer: "Cinematographer",
  copywriter: "Copywriter",
  calligraphy_specialist: "Type specialist",
  motif_illustrator: "Motif illustrator",
  sound_brief_writer: "Sound director",
  logo_designer: "Logo designer",
  critic: "The critic",
};

/** How the gallery introduces each risk level — the web's exact words. */
export const RISK_LABELS: Record<string, string> = {
  safe: "The banker",
  balanced: "The considered choice",
  bold: "The statement",
};

/** Task status, in the studio's voice — small caps beside each crew member. */
export const STATUS_LABELS: Record<string, string> = {
  pending: "waiting",
  running: "at work",
  succeeded: "delivered",
  failed: "failed",
  skipped: "stood down",
  budget_denied: "held",
};
