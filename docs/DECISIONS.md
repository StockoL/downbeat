# Decisions

Choices the spec docs don't settle, made during the build. Newest at the bottom of each phase.

## Phase 1

**27 Oct 2026. Python 3.12, Django 5.2 LTS.** The project conventions name Python 3.12; the laptop also has 3.14, so the venv is pinned with `py -3.12`. Django 5.2 is the current 5.x LTS.

**27 Oct 2026. No login and no Django admin in Phase 1.** The app binds to localhost on the laptop and has one user, so `contrib.auth` and `contrib.admin` are left out. A login arrives in Phase 2, when Tailscale exposes the app to the iPad. All CRUD is on Downbeat's own pages, as the kickoff asks.

**27 Oct 2026. Theme generated from LooseLeaf's token compiler.** `tools/build-theme.mjs` sets the neutral ramp to zero chroma (greyscale chrome) and the action and accent hues to the same indigo (hue 270), so the interface has exactly one accent. One contrast pair falls short: link text on the dark surface is 4.18:1 against a 4.5 target, the same shortfall LooseLeaf's defaults have. Links are rare in the room view; revisit at the surface pass. A configurator export can replace the bundle at any time.

**27 Oct 2026. Navigation shows only areas that exist.** The desk navbar lists Today and Settings in Phase 1 (Plan once the seating editor exists). Sweep and Pupils appear when their phases build them, so no link leads to an empty page.

**27 Oct 2026. Checklist items and flag types are not in the Phase 1 first-run setup.** BUILD_ORDER's Phase 1 paragraph says the setup creates "the timetable, note types, checklist items and flag types", but ChecklistItem and FlagType are Phase 3 tables, the project conventions say not to scaffold later phases' models, and the kickoff says no flags. The setup wizard gains those steps in Phase 3.
