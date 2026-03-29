# End-to-End Testing Guide: My ET Personalized Feed + Experience Intelligence Layer

**Overview**: This guide covers testing for the My ET personalized newsroom feature and the new Experience Intelligence Layer (So What, Contrarian View, Live Sentiment Pulse) across UI tabs.

---

## 🎯 Quick Start: Automated Test Suite

Run all phase tests at once:

```bash
# Run all phase tests sequentially
for test in tests/test_phase*.py; do
    echo "=== Running $test ==="; 
    python "$test" || exit 1
done

# Or run individually
python tests/test_phase1_onboarding.py           # 5/5 tests
python tests/test_phase2_corpus_personalization.py  # 8/8 tests
python tests/test_phase3_personalized_feed.py   # 6/6 tests
python tests/test_phase4_feedback_loop.py       # 8/8 tests
python tests/test_phase5_adaptive_learning.py   # 8/8 tests
```

**Expected**: All 35 tests passing ✅

---

## Experience Intelligence Layer: Full UI Test Procedure

This is the complete manual runbook for the 5-step rollout that was just implemented.

### Prerequisites

1. Start backend API.
2. Start Streamlit UI.
3. Ensure at least one user profile exists (Tab 2) and feed generation works.

Use these commands on Windows:

```bash
uvicorn src.api.main:app --reload --port 8000
streamlit run ui/app.py
```

Optional focused regression check before manual run:

```bash
c:/Users/ayush/Documents/NewsAgents/.venv/Scripts/python.exe -m pytest -q tests/test_phase8_signal_layers.py
```

### Step-by-Step Manual Validation

### Step 1: Validate Personalised Feed "So what for me?"

1. Open Tab 3: Personalised Feed.
2. Select any existing profile from the dropdown.
3. Click Generate My Feed.
4. In any article card, click ✨ So what for me?.
5. Confirm output panel appears below the card with:
   - one headline impact line,
   - exactly 3 bullets,
   - confidence and caveat line.
6. Click the same button again and verify result returns quickly (cached behavior, no visible regeneration delay).

Expected result:
- Personal impact summary is specific to the selected profile context.
- No page crashes even if model call fails.

### Step 2: Validate Personalised Feed "Hear the other side"

1. Stay in Tab 3 with generated feed.
2. Click ⚖️ Hear the other side on any article card.
3. Confirm panel includes:
   - Main read,
   - Other side,
   - Strongest supporting evidence,
   - What would change the view.
4. Repeat on another card to verify per-article behavior.

Expected result:
- Contrarian response is coherent and opposite-side aware.
- Previously opened card response reopens quickly due to session cache.

### Step 3: Validate News Navigator Contrarian Toggle

1. Open Tab 1: News Navigator.
2. Generate Briefing if not already generated.
3. Select any angle from the radio selector.
4. Click ⚖️ Hear the other side under the selected angle synthesis.
5. Confirm the same 4-part contrarian structure renders.
6. Switch to another angle and repeat.

Expected result:
- Contrarian output is angle-aware.
- Reopening same angle contrarian panel is fast (cached per angle).

### Step 4: Validate Section-Level Live Sentiment Pulse in Feed

1. Return to Tab 3.
2. Generate My Feed.
3. Open each section in Sectioned Feed.
4. For each section, verify presence of line:
   - icon (📈/⚖️/📉),
   - label (Bullish/Cautious/Bearish),
   - sample size n,
   - one-line reason.
5. Use Search within your feed and verify pulse still appears for visible sections.

Expected result:
- Pulse reflects up to last 5 recent items in that section.
- With smaller sections, sample size decreases gracefully.

### Step 5: Validate Story Arc Live Sentiment Pulse

1. Open Tab 4: Vernacular Video.
2. Click Generate Video.
3. Open Story Chapters expander once output appears.
4. Verify a Live Sentiment Pulse line appears above story arc details.
5. Check it includes icon, label, sample size, and reason.

Expected result:
- Story arc pulse renders whenever scene plan exists.
- No impact on video/audio rendering behavior.

### End-to-End Acceptance Checklist

- So What panel works in Personalised Feed cards.
- Contrarian panel works in Personalised Feed cards.
- Contrarian panel works in News Navigator angles.
- Live Sentiment Pulse appears in each Personalised Feed section.
- Live Sentiment Pulse appears in Story Chapters under Vernacular Video.
- Existing feedback loop and A/B comparison controls still function.

---

## 📋 Manual End-to-End Testing (UI Flow)

### Setup: Start the Services

```bash
# Terminal 1: Start FastAPI backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start Streamlit frontend  
streamlit run ui/app.py
```

The Streamlit app opens at `http://localhost:8501`

---

### **Test Scenario 1: Fresh User Setup (Phase 1)**

**Goal**: Create a user profile from scratch and verify it persists.

**Steps:**

1. **Navigate to Tab 2**: "My ET — Create Your Profile"
2. **Click "⚡ Quick Start"** (4 questions)
3. **Enter name**: `Test User 1`
4. **Answer all 4 questions** (any options):
   - What's your primary interest? → Pick one (e.g., "Markets & Investing")
   - Reading depth? → Any option (e.g., "Intermediate")
   - Preferred format? → Any option (e.g., "Comprehensive")
   - Investment experience? → Any option
5. **Click "Create My Profile"** → Should see ✅ success with profile summary

**Verification:**
- Profile appears in `data/user_profiles/` (filename format: `user-test-001/json`)
- User ID is deterministic (derived from name)
- Profile summary shown: role, reading level, interests

**Data Check:**
```bash
# Verify file exists and contains correct data
cat data/user_profiles/user-test-001.json
# Should show: user_id, name, age, role, interests, reading_level, preferred_format
```

---

### **Test Scenario 2: Multi-User Profile Creation (Phase 1)**

**Goal**: Ensure system handles multiple users without conflicts.

**Steps:**

1. Still in Tab 2, click "Create Another Profile"
2. **Enter name**: `Test User 2`
3. **Answer 4 questions** (different from Test User 1 where possible)
4. Click "Create My Profile" → Success

**Verification:**
- Both profiles exist: `test-user-1.json` and `test-user-2.json`
- User IDs are different and unique
- Can load both profiles independently

**Data Check:**
```bash
ls -la data/user_profiles/user-test-* | wc -l
# Should show: 2 (or more if you ran earlier tests)
```

---

### **Test Scenario 3: Personalized Feed Generation (Phase 2-3)**

**Goal**: Verify that Phase 2 corpus personalization + Phase 3 ranking + Phase 5 adaptive ranking work together.

**Steps:**

1. **Navigate to Tab 3**: "Personalised Feed"
2. **Select profile**: Choose "Test User 1" from dropdown
3. **Review profile summary**: Check role, reading level, top interest displayed
4. **Click "Generate My Feed"** → Wait for generation to complete
5. **Observe feed**:
   - 🟢 Relevance scores shown (color-coded)
   - Confidence levels displayed
   - Matched tags visible
   - Why shown explanation includes Phase 5 feedback boost info
   - Boost badge (🚀 **BOOSTED**) appears if article was boosted by feedback

**Verification:**
- Feed generated in < 5 seconds
- All 5 articles have relevance scores in [0, 1] range
- Explanations are non-empty
- Tags match user interests

**Expected Boost Behavior (Phase 5):**
- First feed generation: All articles show "Ranked by your interests" (no feedback yet)
- After providing feedback: Some articles will show "Boosted because you liked related articles"

---

### **Test Scenario 4: Feedback Loop Integration (Phase 4 + Phase 5)**

**Goal**: Verify feedback logging, summary aggregation, and adaptive ranking.

**Steps (with same feed as Scenario 3):**

1. **Test Positive Feedback** (👍 button):
   - Click 👍 on any article
   - Toast confirms: "Great! We'll show you more like this."
   - Scroll down to "Your Feedback This Session"
   - Count increases: "👍 Articles You Liked: 1"

2. **Test Negative Feedback** (👎 button):
   - Click 👎 on a different article
   - Popover appears: "Why not interested?"
   - Select reason (e.g., "Too basic/simple")
   - Click "Confirm"
   - Toast confirms: "Got it! Too basic/simple. We'll improve your feed."
   - Feedback summary updates: "👎 Articles Not Helpful: 1"
   - Expander shows reason breakdown

3. **Test Multiple Feedback**:
   - Provide 👍 and 👎 on several more articles
   - Verify counts and reason breakdowns accumulate
   - Scroll through feedback summary sections

**Verification:**
- Feedback events logged to `output/engagement_store.json`
- Summary counts match actual feedback given (this session)
- Reasons appear in correct section (interested vs not_interested)
- No duplicate entries

**Data Check:**
```bash
# Verify feedback was persisted
cat output/engagement_store.json | grep -A 10 "test-user-1"
# Should show: article_feedback array with your entries
```

---

### **Test Scenario 5: Adaptive Ranking in Action (Phase 5)**

**Goal**: Show that Phase 5 boost changes rankings within same session.

**Steps:**

1. **Generate initial feed**:
   - Tab 3, select "Test User 2"
   - Click "Generate My Feed"
   - Note the order and relevance scores of articles

2. **Provide feedback** on articles with similar themes:
   - If you see "Markets Rally" as article 2, click 👍
   - If you see "Budget Talk" as article 4, click 👍
   - If you see "Tech Boom" as article 3, click 👎 with reason "Not relevant"

3. **Refresh feed** (click 🔄 Refresh Feed):
   - Articles with similar themes to liked ones should rank higher
   - "Market-related" articles boost score +0.2-0.3
   - "Tech article" (disliked) shows lower or higher depending on profile

4. **Check explanations**:
   - Scroll to "Why shown" section
   - Articles with boost should show: "Boosted because you liked related articles (↑ 0.XX)"
   - 🚀 **BOOSTED** badge appears for boosted articles

**Expected Behavior:**
- First feed: Random/preference-based order
- After feedback + refresh: Liked themes move up, disliked themes move down
- Explanations clearly show boost source

---

### **Test Scenario 6: Cold-Start Path (Phase 5)**

**Goal**: Verify new users without feedback history get appropriate defaults.

**Steps:**

1. **Create new user** in Tab 2:
   - Name: `Test User 3`
   - Select "Young Investor" role during onboarding
   - Complete profile

2. **Generate feed immediately** (no feedback yet):
   - Tab 3, select "Test User 3"
   - Click "Generate My Feed"
   - Note explanations: All show "Ranked by your interests" (no boost)
   - No 🚀 badges (no feedback yet)

3. **Verify cold-start rules applied**:
   - Check audit trail in `output/adaptive_signals.json`:
     - Should show `apply_cold_start_boost` action
     - No feedback weight applied (weight = 0.0 for cold-start)

**Verification:**
```bash
# Check adaptive signals
tail -50 output/adaptive_signals.json | grep -A 5 "cold_start"
# Should show role-based defaults, no feedback applied
```

---

### **Test Scenario 7: A/B Comparison (Phase 3)**

**Goal**: Compare personalized feed vs. baseline (generic ranking).

**Steps:**

1. **With a feed already generated** (Tab 3):
2. **Click "Show A/B Comparison"** at bottom
3. **Review metrics**:
   - "Articles in Common": Number matching both feeds
   - "Unique to Personalized": Count of articles only in personalized feed
   - "Personalized Avg Relevance": Should be higher than baseline
   - "Baseline Avg Relevance": Lower (generic ranking)
   - Summary message explaining personalization delta

**Expected:**
- Personalized avg relevance > Baseline avg relevance (by 0.1-0.2)
- 2-3 unique articles between feeds

---

## 🧪 Automated Integration Tests

Create a full integration test script to run through entire user journey:

```bash
# tests/test_integration_full_journey.py
# (Already structured, just run):
python -m pytest tests/ -v  # Runs all test_*.py files

# Or create custom script:
#!/bin/bash
set -e

echo "=== FULL INTEGRATION TEST ==="

# 1. Create 3 test users
export TEST_USER1="integration-user-1"
export TEST_USER2="integration-user-2"
export TEST_USER3="integration-user-3"

# 2. Call API to create users
curl -X POST http://localhost:8000/api/v1/users/create \
  -H "Content-Type: application/json" \
  -d '{"name":"Integration Test User 1","quick_start_answers":{...}}'

# 3. Generate feeds
curl -X POST http://localhost:8000/api/v1/feed/personalized-full \
  -H "Content-Type: application/json" \
  -d '{"user_id":"integration-user-1"}'

# 4. Log feedback
curl -X POST http://localhost:8000/api/v1/engagement/log-feedback \
  -H "Content-Type: application/json" \
  -d '{"user_id":"integration-user-1","article_id":"art-001","feedback_type":"interested"}'

# 5. Regenerate feed with adaptive ranking
curl -X POST http://localhost:8000/api/v1/feed/personalized-full \
  -H "Content-Type: application/json" \
  -d '{"user_id":"integration-user-1"}'

echo "✅ Integration test passed!"
```

---

## 📊 Performance Benchmarks

**Target metrics:**

| Phase | Operation | Target Time | Notes |
|-------|-----------|-------------|-------|
| 1 | Create user profile | < 100ms | DB write |
| 2 | Get personalized subset (first call) | < 500ms | Corpus scan + filtering |
| 2 | Get personalized subset (cached) | < 50ms | Redis/file cache hit |
| 3 | Rank articles | < 200ms | Agent call |
| 3 | Adapt articles | < 300ms | Agent call |
| 3 | Full feed generation | < 2s | All steps combined |
| 4 | Log feedback | < 50ms | JSON write |
| 5 | Apply adaptive boost | < 100ms | In-memory computation |
| 5 | Full adaptive feed | < 2.5s | Phase 3 + Phase 5 |

**Run performance test:**

```bash
# Generate feed 10 times and measure
python -c "
import time
import asyncio
from src.agents.personalized_feed_pipeline import generate_personalized_user_feed

async def benchmark():
    times = []
    for i in range(10):
        start = time.time()
        # Generate feed
        elapsed = time.time() - start
        times.append(elapsed)
    print(f'Avg: {sum(times)/len(times):.2f}s | Min: {min(times):.2f}s | Max: {max(times):.2f}s')

asyncio.run(benchmark())
"
```

---

## ✔️ Data Integrity Checks

**Verify data consistency across phases:**

```bash
# 1. Check all users exist
wc -l data/user_profiles/*.json

# 2. Verify user profiles are valid JSON
for f in data/user_profiles/*.json; do
    python -m json.tool "$f" > /dev/null || echo "Invalid: $f"
done

# 3. Check engagement store
python -c "
import json
with open('output/engagement_store.json') as f:
    store = json.load(f)
    print(f'Users: {len(store.get(\"users\", {}))}')
    for user_id in list(store['users'].keys())[:3]:
        fb = store['users'][user_id].get('article_feedback', [])
        print(f'  {user_id}: {len(fb)} feedback entries')
"

# 4. Verify no data loss on restart
# Stop and restart backend:
#   kill $(lsof -t -i:8000)
#   uvicorn src.api.main:app --reload --port 8000
# Then regenerate feed for same user — should see same feedback
```

---

## 🐛 Common Issues & Debugging

### Issue: "Profile file not found" error in Tab 3

**Solution:**
1. Check `data/user_profiles/` directory exists
2. Verify filename format: `user-{user_id}.json` (lowercase)
3. Ensure profile file is valid JSON:
   ```bash
   python -m json.tool data/user_profiles/user-test-001.json
   ```
4. Recreate profile if corrupted

### Issue: Feed takes > 5 seconds to generate

**Solution:**
1. Check if corpus subset caching is working:
   ```bash
   ls -lah data/user_profiles/cache/
   # Should show cache files from Phase 2
   ```
2. Verify LLM API responses are fast:
   - Check `output/audit_trail.json` for agent latencies
   - Agent calls should be < 1s each

### Issue: Feedback not showing in feedback summary

**Solution:**
1. Verify feedback was logged:
   ```bash
   cat output/engagement_store.json | grep article_feedback
   ```
2. Check user_id matches selected profile
3. Try clicking button again or refresh page (Streamlit rerun)

### Issue: Adaptive boost not showing in explanations

**Solution:**
1. Verify Phase 4 feedback was logged (see above)
2. Check `adaptive_signals.json` exists and has entries:
   ```bash
   cat output/adaptive_signals.json | head -20
   ```
3. Regenerate feed after feedback logged
4. Look for `"boosted": true` in explanations dict

---

## 🎓 Summary: What Each Phase Tests

| Phase | What to Test | How | Expected Result |
|-------|--------------|-----|-----------------|
| **1** | User creation + persistence | Create user in UI → check file | Profile saves with correct fields |
| **2** | Corpus personalization + caching | Generate feed → check cached files | Subset cached, retrieved quickly |
| **3** | Feed generation + rankings | Generate feed → check scores | All articles ranked 0-1, explanations present |
| **4** | Feedback logging + summary | Click 👍/👎 → check engagement_store.json | Feedback persisted, summary accurate |
| **5** | Adaptive ranking + cold-start | Generate feed before/after feedback | Explanations show boost source, scores change |

---

## ✅ Final Validation Checklist

Before considering the feature "production-ready":

- [ ] All unit tests passing (35/35)
- [ ] Manual end-to-end flow complete (all 7 scenarios)
- [ ] Feedback properly logged and aggregated
- [ ] Adaptive boost explanations visible in UI
- [ ] Performance benchmarks met (< 2.5s full feed)
- [ ] Data persists across backend restarts
- [ ] No memory leaks (check `output/` folder growth)
- [ ] Streamlit app doesn't crash with edge cases
- [ ] Cold-start path works for new users
- [ ] A/B comparison delta makes sense

---

## 🚀 Phase 7 Status: Implemented

Phase 6 is complete with:
- Feed sections (Markets, Tech, Policy, etc.)
- Richer metadata (urgency, sentiment, freshness, credibility)
- Section-level search and headline picks in Tab 3

Phase 7 is now also implemented with:
- A/B run persistence (`output/ab_test_runs.json`)
- Summary metrics (win rate, relevance lift, cost/run)
- Settings dashboard controls for loading summary and recent runs
