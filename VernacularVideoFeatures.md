# Vernacular Video Features

Last updated: 2026-03-28

## 1) Goal and Scope
The Vernacular Video pipeline converts a breaking business news article into a short-form explainer video with:
- Story-arc driven chapters
- Multi-language script and narration
- Fact-aware scene planning
- Visual composition with timeline/impact storytelling
- Audio-video synchronization
- API and UI support for language selection and outputs

## 2) What Was Added and Improved (Chronological)

### Phase 1: Core Reliability and Duration Improvements
- End-to-end language parameter wiring from API/UI to script, TTS, and composer.
- Language profile system in config for voice/font/language hints.
- Composer updates to avoid overly short output in sparse-content cases.
- Better fallback scene generation when extraction is thin.

### Phase 2: Chaptered Storytelling
- Added scene-plan models and scene planner agent.
- Introduced chapter-based composition flow.
- Added timeline/chapter visuals and chapter metadata exposure.
- API/UI now return/display scene plan and chapter information.

### Phase 2.5: A/V Sync and Visual Richness
- Added scene-level TTS generation and merged narration track.
- Composer uses per-scene audio durations for stricter sync.
- Added article visual fetcher (image scraping from source URL with fallback).
- Improved extraction enrichment to prevent empty/sparse outputs.

### Phase 3: Story Arc Depth
- Expanded story-arc metadata in outputs:
  - Story arc summary
  - Key players
  - Sentiment shifts
  - Contrarian perspective
  - Watch-next signals
- Added richer fallback chapter set (including contrarian + watch-next).
- Added per-scene narration text fields for better voiceover quality.

### Multilingual Expansion + Validation
- Added Indian language support requested in alphabetical order:
  - Bhojpuri, Hindi, Kannada, Marathi, Punjabi, Tamil, Telugu
- Added language validator stage to detect and correct language leakage.
- Hardened validator against quota/error text contamination.
- Added deterministic cleanup fallback when model validation fails.

### Performance and Rendering Optimization
- Reduced expensive validator loops and added fast gating.
- Added concurrent scene-level TTS generation.
- Tuned TTS speed and guardrails to improve generation latency.
- Wired language-aware font resolution and fallback.
- Verified generation runtime improvements (representative benchmark around sub-60s in optimized path).

### Latest Fix: Short Videos in Non-Hindi Languages
Root cause identified:
- In strict scene-sync mode, short fallback narration text + aggressive TTS speed produced very short per-scene clips.
- Final video duration was clipped to short merged narration.

Fix implemented:
- Added target-duration-aware scene-audio generation.
- Enriched very short scene narration before TTS.
- Reduced aggressive TTS speedup.
- Added minimum merged-audio duration enforcement (padding when needed).

Result:
- Non-Hindi outputs no longer collapse to ~30-40s in fallback-heavy runs.
- Typical multilingual outputs now stay near intended runtime floor.

## 3) Current Pipeline Structure

### High-level Flow
1. BreakingIngestor
   - Extracts structured facts (5W1H, key numbers, impact points).
2. ScriptWriter
   - Generates language-aware explainer script with target duration guidance.
3. FactChecker
   - Verifies claims against source article context.
4. ScenePlanner
   - Builds chaptered scene plan with story-arc metadata.
5. LanguageValidator (conditional)
   - Runs only when needed; corrects mixed-language leakage.
6. AudioGenerator
   - Primary: scene-level audio generation + merge + duration map.
   - Fallback: full-script narration generation.
7. VideoComposer
   - Renders frames, chapter scenes, timeline scene, and final video using ffmpeg.
   - Supports strict scene sync and language-aware fonts.

### Main Orchestration Entry
- run_video_pipeline in src/agents/video/pipeline.py

## 4) Current Feature Set (Present State)

### Storytelling Features
- Chaptered narrative scenes (typically 6-10 scenes).
- Timeline/progression scene support.
- Contrarian lens and watch-next chapter support.
- Sentiment progression capture across scenes.

### Language and Localization
- Language-aware prompting for script/planner.
- Multi-language fallback templates for scripts and scenes.
- Conditional post-generation language validation/correction.
- Localized emergency replacement paths to avoid Hindi leakage in other languages.

### Audio Features
- Scene-level TTS for tighter sync and chapter pacing.
- Voice candidate fallback list per language.
- Merged narration with ffmpeg concat/re-encode fallback.
- Duration probing and scene duration mapping.
- Runtime floor protection to prevent very short final output.

### Video and Visual Features
- Title, chapter, timeline, recap/facts/impact, and closing frame generation.
- Article image extraction from source page for background visuals.
- Gradient/overlay visual fallback when source media is unavailable.
- Language-aware font resolution with fallback.

### API and UI Features
- Language selector exposed in UI.
- API accepts target_language and returns scene_plan metadata.
- UI surfaces chapter/story-arc related outputs.

### Reliability and Safety
- Audit trail logging for each pipeline step.
- Graceful degradation paths:
  - Scene audio failure -> full-script narration fallback.
  - Validator/model failures -> deterministic fallback cleanup.
  - Visual fetch failure -> generated visual backgrounds.

## 5) Key Modules and Responsibilities
- src/agents/video/pipeline.py
  - End-to-end orchestration and fallback control.
- src/agents/video/breaking_ingestor.py
  - Breaking news extraction + heuristic enrichment.
- src/agents/video/script_writer.py
  - Language-aware script generation and localized fallbacks.
- src/agents/video/scene_planner.py
  - Chapter/scene plan generation and story-arc metadata.
- src/agents/video/language_validator.py
  - Language consistency validation/correction.
- src/agents/video/audio_gen.py
  - TTS generation, per-scene merge, duration handling.
- src/agents/video/video_composer.py
  - Frame rendering and final video composition.
- src/agents/video/article_visuals.py
  - Source-page image discovery/download.
- src/config.py
  - Language profiles, voice/font candidates, defaults.
- src/models.py
  - Extended data models for scene plans and story-arc fields.
- src/api/main.py
  - API contract and language pass-through.
- ui/app.py
  - Streamlit controls and metadata display.

## 6) Supported Languages (Current)
- English
- Hindi
- Bhojpuri
- Kannada
- Marathi
- Punjabi
- Tamil
- Telugu

Note:
- Text generation/localization works for these languages.
- Punjabi voice support may be unavailable depending on local edge-tts voice availability, resulting in text/video fallback behavior without generated Punjabi narration audio.

## 7) Performance Notes
- Major bottlenecks reduced through validator gating and concurrency in scene TTS generation.
- Duration safety logic now prevents short multilingual outputs in strict scene-sync mode.
- Generation time depends on model latency, TTS voice availability, and ffmpeg work on host machine.

## 8) Known Limitations
- Voice availability is provider/environment dependent (not all locales have guaranteed voices).
- Output quality in low-resource language paths still depends on LLM response quality and available fallback templates.
- Visual richness depends on whether source article pages expose usable images.

## 9) Suggested Next Enhancements
1. Add explicit voice support flags in API/UI (audio_supported_for_language, selected_voice).
2. Integrate alternative TTS provider for Punjabi and any missing locales.
3. Add automated regression tests for:
   - Minimum runtime by language
   - Language leakage checks
   - Scene-plan quality thresholds
4. Add quality metrics dashboard from audit logs (duration, fallback rate, validator usage, failure modes).
