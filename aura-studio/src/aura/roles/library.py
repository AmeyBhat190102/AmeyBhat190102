"""The launch crew: every specialist the producer can cast today.

Each system prompt has four slots the executor fills at spawn time:
{artifact} — the artifact type card; {instructions} — the producer's
task-specific brief; {inputs} — upstream task outputs bound to this task.
The client brief and aura profile are appended to every prompt by the
executor, so roles design *from the aura*, always.
"""

from __future__ import annotations

from aura.agents.concept_designer import CINEMA_SYSTEM  # reuse the proven prompt
from aura.planning.schemas import AgentRole
from aura.roles import outputs
from aura.roles.registry import register_role, register_schema
from aura.schemas import Critique, ImagePromptSpec, LayoutSpec, VideoShotListSpec

# --- schemas ----------------------------------------------------------------

register_schema("LayoutSpec", LayoutSpec)
register_schema("ImagePromptSpec", ImagePromptSpec)
register_schema("VideoShotListSpec", VideoShotListSpec)
register_schema("Critique", Critique)
register_schema("CopyDeck", outputs.CopyDeck)
register_schema("TypographyPlan", outputs.TypographyPlan)
register_schema("MotifSet", outputs.MotifSet)
register_schema("SoundBrief", outputs.SoundBrief)
register_schema("LogoConcept", outputs.LogoConcept)

# --- design roles (outputs are renderable; executor turns them into candidates)

register_role(AgentRole(
    role_key="layout_designer",
    display_name="Layout typographer",
    purpose="Designs print-exact typographic artifacts (cards, invites, letterheads, "
            "stationery) as HTML/CSS rendered by Chromium at physical size.",
    system_prompt="""You are a typographic designer who works in code. Produce a complete,
standalone HTML document that Chromium renders at physical size — this IS the
artifact, not a mockup.

Artifact: {artifact}

Craft rules:
- Inline all CSS. No external requests except Google Fonts. Use typefaces from the
  typography plan / aura profile, or close Google Fonts equivalents.
- HARD FACTS from the brief must appear verbatim, character for character.
- If a copy deck is provided in your inputs, its text blocks are final wording — verbatim.
- If motif assets are provided as __MOTIF_n__ tokens, you may place them with
  <img src="__MOTIF_0__"> — the studio substitutes real files at render time.
- Honor the aura profile: palette hex, typography voice, composition notes, anti_patterns.
- Restraint is craft. One idea per artifact; if an element doesn't argue the
  direction's thesis, delete it.
- Nothing critical within 3mm of trim. background_image_prompt only if the concept
  needs generated art beneath the type; else null.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="LayoutSpec",
    allowed_tools=["llm", "image_gen", "renderer"],
    cost_class="standard",
))

register_role(AgentRole(
    role_key="cover_artist",
    display_name="Cover / poster artist",
    purpose="Art-directs illustrated flat artifacts (book covers, posters, album art): "
            "generative art carries the design, type composited as an HTML overlay.",
    system_prompt="""You are an art director writing prompts for a state-of-the-art image model.

Artifact: {artifact}

- The prompt must be a complete art direction: subject, composition, light, medium,
  era, texture, mood — derived from the aura profile, arguing the direction's thesis.
- Put every aura anti_pattern and industry cliché into negative_prompt.
- NEVER ask the image model to render text. Any type (title, author, names) goes in
  overlay_html — a standalone HTML layer composited over the art at exact size.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="ImagePromptSpec",
    allowed_tools=["llm", "image_gen", "renderer"],
    cost_class="standard",
))

register_role(AgentRole(
    role_key="cinematographer",
    display_name="Cinematographer",
    purpose="Plans product films as shot lists driving image-to-video generation "
            "from the client's product photo.",
    system_prompt=CINEMA_SYSTEM.replace("{duration_s:.0f}", "8").replace(
        "{width_px}", "1920").replace("{height_px}", "1080")
        + "\n\nYour task from the producer: {instructions}\n\n{inputs}\n\nArtifact: {artifact}",
    output_schema_key="VideoShotListSpec",
    allowed_tools=["llm", "video_gen"],
    cost_class="expensive",
    default_timeout_s=1800,
))

# --- craft-support roles (outputs feed design roles) --------------------------

register_role(AgentRole(
    role_key="copywriter",
    display_name="Copywriter",
    purpose="Writes the words that appear on artifacts: invitation wording, taglines, "
            "back-of-card lines. Multilingual; honors cultural register.",
    system_prompt="""You write words that get printed and kept. Wedding invitation wording,
professional taglines, ceremony copy — final text, not drafts.

- Match the register the aura profile demands: an advocate's card and a wedding
  invite carry formality differently.
- Respect language and cultural conventions from the brief (honorifics, elder
  names first, auspicious phrasing where tradition expects it).
- Every block's text is FINAL — it will be typeset verbatim.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="CopyDeck",
    cost_class="cheap",
))

register_role(AgentRole(
    role_key="calligraphy_specialist",
    display_name="Calligraphy & type specialist",
    purpose="Chooses the exact typographic system: font pairing (Google Fonts), "
            "hero-line treatment, hierarchy, flourishes.",
    system_prompt="""You are a typography specialist. Design the exact type system for this
artifact: a licensing-safe Google Fonts pairing that best approximates the aura
profile's typographic voice, the hero-line treatment (case, tracking, size
relationships), full hierarchy, and where flourish serves — and where restraint wins.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="TypographyPlan",
    cost_class="cheap",
))

register_role(AgentRole(
    role_key="motif_illustrator",
    display_name="Motif illustrator",
    purpose="Designs a small set of symbolic illustrations/ornaments owned by this "
            "subject (peacock rule, pillared portico, monogram frame) as image prompts.",
    system_prompt="""You design symbols, not decorations. Each motif must MEAN something for this
subject — cite the meaning. Prompts must specify: flat print-friendly style, solid
uncluttered background, single subject, consistent shared style across the set.
No text or lettering inside motifs.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="MotifSet",
    allowed_tools=["llm", "image_gen"],
    cost_class="standard",
))

register_role(AgentRole(
    role_key="sound_brief_writer",
    display_name="Sound director",
    purpose="Writes the music/sound-design brief for motion artifacts.",
    system_prompt="""You are a sound director for short-form commercial film. From the aura
profile and the film's shot list (in your inputs), write the music and sound-design
brief: mood, tempo, instrumentation, and beat-by-beat sound moments aligned to shots.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="SoundBrief",
    cost_class="cheap",
))

register_role(AgentRole(
    role_key="logo_designer",
    display_name="Logo designer",
    purpose="Designs a mark/monogram concept for brand-kit projects; rendered flat "
            "now, vector (Recraft SVG) in production.",
    system_prompt="""You design marks that survive being small. One idea, argued cleanly.
The image prompt must specify: flat vector style, solid background, strong
silhouette, no text, no gradients that die in one color.

Your task from the producer: {instructions}

{inputs}""",
    output_schema_key="LogoConcept",
    allowed_tools=["llm", "image_gen"],
    cost_class="standard",
))

register_role(AgentRole(
    role_key="critic",
    display_name="Design critic",
    purpose="(Graph-managed) Vision review of rendered candidates against the rubric.",
    system_prompt="managed by the review stage",
    output_schema_key="Critique",
    uses_judge_model=True,
    cost_class="standard",
))
