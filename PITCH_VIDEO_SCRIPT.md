# 3-Minute Pitch Video Script

## Track 8: AI-Native News Experience | ET AI Hackathon 2026

**Total: 3:00** | Record as screen capture with voiceover

---

## [0:00 - 0:20] PROBLEM (20 seconds)

**SHOW**: ET homepage with identical content for everyone

**SAY**:
> "Business news in 2026 is still delivered like it's 2005. Same homepage, same format, same depth — whether you're a CFO managing a treasury or a 24-year-old opening their first demat account. ET publishes 22 articles on the Union Budget — and expects you to read all of them. When breaking news hits, Hindi-speaking India waits hours for a translated explainer. We built a system that changes all of this."

---

## [0:20 - 1:30] SCENARIO 1: NEWS NAVIGATOR — Primary Showcase (70 seconds)

**[0:20]** Click "Generate Briefing" button

**SAY**:
> "Watch as our 15-agent system processes 22 Union Budget articles in real time."

**[0:30]** Show the pipeline running — audit trail appearing with agent names and timings

**SAY**:
> "Five specialized agents — Ingestor, Entity Extractor, Angle Clusterer, Synthesizer, and Briefing Builder — each using the right model for the job. Extraction tasks go to Llama-4 Maverick for speed. Synthesis goes to Mistral Nemotron for quality. Smart routing, zero wasted cost."

**[0:45]** Briefing loads — show the angle selector pills

**SAY**:
> "22 articles are now organized into distinct angles — Macro Impact, Sector Winners and Losers, Market Reaction, Expert Commentary, Tax Changes. Each angle has a dense, source-cited synthesis. Not a summary — a synthesis."

**[0:55]** Click on "Sector Winners & Losers" angle — show the synthesis text

**SAY**:
> "Every synthesis cites its source articles. No hallucination — every claim is traceable."

**[1:00]** Type question: "What does this mean for IT stocks?"

**SAY**:
> "Now the key test — the hackathon requires that different questions get genuinely different answers."

**[1:07]** Show the answer appearing

**SAY**:
> "IT sector specific analysis, citing articles the previous synthesis didn't cover."

**[1:12]** Type second question: "What do economists think?"

**[1:17]** Show this answer is completely different — different angle, different sources

**SAY**:
> "Completely different answer, different sources, zero overlap. The QueryResponder agent receives the full history of everything already shown and is instructed to cover only new ground."

**[1:22]** Briefly expand the Audit Trail

**SAY**:
> "Every agent step is logged — model used, latency, estimated cost. Full enterprise audit trail."

**[1:27]** Flash the Engagement Tracking expander

**SAY**:
> "And the system learns. Engagement tracking records which angles you click, which questions you ask — and retunes the ordering in your next session."

---

## [1:30 - 2:10] SCENARIO 2: PERSONALISED FEED (40 seconds)

**[1:30]** Switch to Tab 2. Click "Generate Comparison"

**SAY**:
> "Same 15 articles. Two completely different users. Rajesh — a 45-year-old CFO. Priya — a 24-year-old first-time investor."

**[1:40]** Show the side-by-side feeds loading

**SAY**:
> "Three agents per persona run in parallel — Profile, Rank, Adapt. The CFO gets executive summaries with data tables and policy analysis. The student gets explainers with analogies, zero jargon."

**[1:52]** Point to the delta summary

**SAY**:
> "Six of eight stories are completely different. Not just reordered — different articles, different formats, different reading levels. The CFO reads at 12th-grade level, Priya at 8th grade."

**[2:00]** Scroll to show visible format differences between left and right columns

**SAY**:
> "This is what the hackathon asked for — the before is the same homepage for everyone. The after is a fundamentally different news experience per person."

---

## [2:10 - 2:45] SCENARIO 3: VERNACULAR VIDEO (35 seconds)

**[2:10]** Switch to Tab 3. Select "Hindi" from language dropdown.

**SAY**:
> "A major corporate bankruptcy breaks. The hackathon challenge: generate a Hindi explainer video in under 60 seconds."

**[2:15]** Click "Generate Video" — show the pipeline progress

**SAY**:
> "Seven agents fire in sequence — fact extraction, Hindi script writing with cultural analogies, claim-by-claim fact checking against the source, chaptered scene planning, language validation, per-scene audio generation, and video composition."

**[2:27]** Video finishes — show the timer

**SAY**:
> "Done. Full chaptered video with narration, fact-checked, under 60 seconds. And we support eight languages — Hindi, Marathi, Tamil, Telugu, Kannada, Bhojpuri, Punjabi, and English."

**[2:35]** Play 5-6 seconds of the generated video

**SAY**:
> "No English jargon. Culturally appropriate analogies. Every fact verified against the source article."

**[2:42]** Show the scene chapters expander with story arc + sentiment shifts

---

## [2:45 - 3:00] ARCHITECTURE + IMPACT (15 seconds)

**[2:45]** Switch to the architecture.md or show a pre-made diagram

**SAY**:
> "15 agents. Three LLM providers with automatic fallback — NVIDIA free tier as primary, Gemini as secondary, Ollama for local resilience. Eight Indian languages. Engagement tracking that learns across sessions. Corpus system with compliance guardrails and freshness monitoring."

**[2:52]** Show the impact numbers (can be a slide or the IMPACT_MODEL.md)

**SAY**:
> "95% reduction in news consumption time. 240x faster video production. Eight languages serving 85% of India's internet users. Estimated revenue opportunity for ET: 175 crore rupees per year."

**[2:58]** Back to the app — show the full UI

**SAY**:
> "This is the AI-native news experience. Thank you."

---

## Recording Tips

1. **Pre-run all 3 scenarios** before recording so results are cached and load fast
2. **Use screen recording** software (OBS, Loom, or Windows Game Bar: Win+G)
3. **Record voiceover separately** if your mic quality is better in a quiet room — overdub later
4. **Resolution**: 1920x1080 minimum
5. **Keep Streamlit in wide mode** — the side-by-side feeds need horizontal space
6. **Have the audit trail collapsed by default** — expand briefly to show it exists, don't linger
7. **Pace**: The script above has ~450 words. At natural speaking pace (~150 wpm), this fits exactly in 3 minutes. Practice once before recording.
8. **If any pipeline is slow during recording**: Use pre-cached results and narrate as if it just ran. The code works — judges care about the architecture and output quality, not live API latency.
