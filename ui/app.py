"""Streamlit frontend for ET AI News Navigator — 3-tab interface."""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="ET AI News Navigator",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
    }
    .angle-pill {
        display: inline-block;
        padding: 8px 16px;
        margin: 4px;
        border-radius: 20px;
        background-color: #1e3a8a;
        color: white;
        cursor: pointer;
        font-size: 14px;
    }
    .angle-pill-active {
        background-color: #ea580c;
    }
    .audit-entry {
        font-size: 12px;
        padding: 4px 8px;
        border-left: 3px solid #ea580c;
        margin: 4px 0;
        background-color: #f8fafc;
    }
    .metric-card {
        background: linear-gradient(135deg, #0f172a, #1e3a8a);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .feed-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


def run_async(coro):
    """Run an async coroutine in Streamlit."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("ET AI News Navigator")
    st.caption("AI-Native News Experience | Track 8 | ET AI Hackathon 2026")
with col2:
    st.markdown("**Multi-Agent Architecture**")
    st.caption("12 agents | 3 models | Smart routing")

# --- Tabs ---
tab1, tab2, tab3 = st.tabs([
    "News Navigator",
    "Personalised Feed",
    "Vernacular Video",
])

# ============================================================
# TAB 1: NEWS NAVIGATOR (Primary Showcase)
# ============================================================
with tab1:
    st.header("Union Budget 2026 — Interactive Intelligence Briefing")
    st.markdown("*22 articles synthesised into navigable angles with interactive Q&A*")

    # Generate briefing button
    if st.button("Generate Briefing", key="gen_briefing", type="primary"):
        with st.spinner("Running 5-agent pipeline: Ingest → Extract → Cluster → Synthesise..."):
            try:
                from src.tools.article_loader import load_budget_articles
                from src.agents.navigator.pipeline import run_navigator_pipeline

                articles = load_budget_articles()
                start = time.time()
                result = run_async(run_navigator_pipeline(articles, "navigator"))
                elapsed = time.time() - start

                st.session_state["briefing"] = result
                st.session_state["briefing_time"] = elapsed
                st.success(f"Briefing generated in {elapsed:.1f}s — {len(result.angles)} angles, {len(result.syntheses)} syntheses")
            except Exception as e:
                st.error(f"Pipeline error: {e}")

    # Display briefing if available
    if "briefing" in st.session_state:
        result = st.session_state["briefing"]

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Articles Processed", "22")
        m2.metric("Angles Identified", len(result.angles))
        m3.metric("Pipeline Time", f"{st.session_state.get('briefing_time', 0):.1f}s")
        m4.metric("Agents Used", "5")

        st.divider()

        # Angle selector
        angle_names = [a.angle_name for a in result.angles]
        selected_angle = st.radio(
            "Select an angle to explore:",
            angle_names,
            horizontal=True,
            key="angle_selector",
        )

        # Show synthesis for selected angle
        for synthesis in result.syntheses:
            if synthesis.angle_name == selected_angle:
                st.subheader(synthesis.angle_name)
                st.markdown(synthesis.synthesis)

                # Source citations
                if synthesis.source_articles:
                    st.caption(f"Sources: {', '.join(synthesis.source_articles)}")

                # Key takeaways
                if synthesis.key_takeaways:
                    with st.expander("Key Takeaways"):
                        for t in synthesis.key_takeaways:
                            st.markdown(f"- {t}")
                break

        st.divider()

        # Interactive Q&A
        st.subheader("Ask a Follow-up Question")
        st.caption("Each answer is non-overlapping — asking different questions yields genuinely different insights.")

        question = st.text_input(
            "Your question:",
            placeholder="e.g., What does this mean for IT stocks?",
            key="nav_question",
        )

        if st.button("Ask", key="ask_btn") and question:
            with st.spinner("QueryResponder agent processing..."):
                try:
                    from src.agents.navigator.pipeline import handle_query
                    qr = run_async(handle_query(question, "navigator"))
                    st.markdown(f"**Answer** (Angle: {qr.angle})")
                    st.markdown(qr.answer)
                    if qr.sources:
                        st.caption(f"Sources: {', '.join(qr.sources)}")
                except Exception as e:
                    st.error(f"Query error: {e}")

        # Query history
        from src.agents.navigator.query_responder import get_query_history
        history = get_query_history("navigator")
        if history:
            with st.expander(f"Previous Questions ({len(history)})"):
                for h in reversed(history):
                    st.markdown(f"**Q:** {h['question']}")
                    st.markdown(f"A: {h['answer'][:200]}...")
                    st.divider()

        # Audit trail
        if result.audit_trail:
            with st.expander("Audit Trail (Enterprise Readiness)"):
                for entry in result.audit_trail:
                    status_icon = {"success": "✅", "fallback": "⚠️", "error": "❌"}.get(entry.status, "ℹ️")
                    st.markdown(
                        f"{status_icon} **{entry.agent_name}** | {entry.action} | "
                        f"Model: `{entry.model_used}` | {entry.latency_ms}ms | {entry.status}"
                    )

# ============================================================
# TAB 2: PERSONALISED FEED
# ============================================================
with tab2:
    st.header("Personalised Feed — Same News, Different Experience")
    st.markdown("*How the same homepage transforms for different user personas*")

    col_before, col_after = st.columns([1, 2])

    with col_before:
        st.subheader("BEFORE: Same Homepage")
        st.markdown("""
        <div style="background:#f1f5f9; padding:20px; border-radius:8px; text-align:center;">
            <p style="color:#64748b;">Identical content for all users</p>
            <p style="color:#64748b;">Same order, same format, same depth</p>
            <p style="color:#94a3b8; font-size:48px;">📰</p>
        </div>
        """, unsafe_allow_html=True)

    with col_after:
        st.subheader("AFTER: Persona-Differentiated")

    if st.button("Generate Comparison", key="gen_feed", type="primary"):
        with st.spinner("Profiling → Ranking → Adapting content for both personas..."):
            try:
                from src.tools.article_loader import load_homepage_articles, load_user_profile
                from src.agents.persona_feed.pipeline import run_feed_comparison

                articles = load_homepage_articles()
                profile_a = load_user_profile("cfo_profile")
                profile_b = load_user_profile("young_investor_profile")

                start = time.time()
                comparison = run_async(run_feed_comparison(articles, profile_a, profile_b))
                elapsed = time.time() - start

                st.session_state["feed_comparison"] = comparison
                st.session_state["feed_time"] = elapsed
                st.success(f"Feeds generated in {elapsed:.1f}s")
            except Exception as e:
                st.error(f"Feed error: {e}")

    if "feed_comparison" in st.session_state:
        comp = st.session_state["feed_comparison"]

        # Delta summary
        st.info(comp.delta_summary)

        # Side-by-side feeds
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader(f"👔 {comp.feed_a.user_profile.name}")
            st.caption(f"{comp.feed_a.user_profile.role} | {comp.feed_a.reading_level_applied} depth | {comp.feed_a.format_applied} format")
            for item in comp.feed_a.feed_items:
                with st.container():
                    st.markdown(f"**{item.adapted_title}**")
                    st.markdown(item.adapted_content[:300] + "..." if len(item.adapted_content) > 300 else item.adapted_content)
                    st.caption(f"Format: {item.format_type} | Relevance: {item.relevance_score:.0%}")
                    st.divider()

        with col_b:
            st.subheader(f"🎓 {comp.feed_b.user_profile.name}")
            st.caption(f"{comp.feed_b.user_profile.role} | {comp.feed_b.reading_level_applied} depth | {comp.feed_b.format_applied} format")
            for item in comp.feed_b.feed_items:
                with st.container():
                    st.markdown(f"**{item.adapted_title}**")
                    st.markdown(item.adapted_content[:300] + "..." if len(item.adapted_content) > 300 else item.adapted_content)
                    st.caption(f"Format: {item.format_type} | Relevance: {item.relevance_score:.0%}")
                    st.divider()

        # Audit trail
        if comp.audit_trail:
            with st.expander("Audit Trail"):
                for entry in comp.audit_trail:
                    status_icon = {"success": "✅", "fallback": "⚠️", "error": "❌"}.get(entry.status, "ℹ️")
                    st.markdown(
                        f"{status_icon} **{entry.agent_name}** | {entry.action} | "
                        f"Model: `{entry.model_used}` | {entry.latency_ms}ms"
                    )

# ============================================================
# TAB 3: VERNACULAR VIDEO
# ============================================================
with tab3:
    st.header("Breaking News → Hindi Video in <60 Seconds")
    st.markdown("*5-agent pipeline: Ingest → Script → Fact-check → Audio → Video*")

    # Show source article
    with st.expander("Source Article (Breaking News)", expanded=False):
        try:
            from src.tools.article_loader import load_breaking_news
            article = load_breaking_news()
            st.markdown(f"**{article.title}**")
            st.markdown(article.content)
            st.caption(f"Source: {article.author} | {article.published_at}")
        except Exception as e:
            st.warning(f"Could not load article: {e}")

    if st.button("Generate Hindi Video", key="gen_video", type="primary"):
        progress = st.progress(0, text="Starting pipeline...")

        try:
            from src.tools.article_loader import load_breaking_news
            from src.agents.video.pipeline import run_video_pipeline

            article = load_breaking_news()
            start = time.time()

            # Run pipeline with progress updates
            progress.progress(10, text="Extracting key facts...")
            result = run_async(run_video_pipeline(article, "video"))
            elapsed = time.time() - start

            progress.progress(100, text=f"Complete! {elapsed:.1f} seconds")

            st.session_state["video_result"] = result
            st.session_state["video_time"] = elapsed

            if result.status == "success":
                st.success(f"Video generated in {elapsed:.1f} seconds (target: <60s)")
            elif result.status == "degraded":
                st.warning(f"Partial output in {elapsed:.1f}s — some components unavailable")
            else:
                st.error(f"Pipeline failed after {elapsed:.1f}s")

        except Exception as e:
            progress.progress(100, text="Error")
            st.error(f"Video pipeline error: {e}")

    if "video_result" in st.session_state:
        result = st.session_state["video_result"]

        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Generation Time", f"{result.generation_time_seconds:.1f}s")
        m2.metric("Target", "<60s")
        m3.metric("Status", result.status.upper())

        # Two columns: Script + Fact Check
        col_script, col_facts = st.columns(2)

        with col_script:
            st.subheader("Hindi Script")
            if result.script:
                st.markdown(result.script.script_hindi)
                st.divider()
                st.caption(f"Estimated duration: {result.script.estimated_duration_seconds}s")
                if result.script.analogies_used:
                    st.caption(f"Analogies: {', '.join(result.script.analogies_used)}")

        with col_facts:
            st.subheader("Fact Check Report")
            if result.fact_check:
                st.metric("Accuracy Score", f"{result.fact_check.accuracy_score:.0%}")
                for claim in result.fact_check.claims:
                    icon = "✅" if claim.source_match else "❌"
                    st.markdown(f"{icon} {claim.claim}")
                    if claim.source_text:
                        st.caption(f"Source: {claim.source_text[:100]}...")

                if result.fact_check.flagged_claims:
                    st.warning("Flagged claims: " + ", ".join(result.fact_check.flagged_claims))

        # Video player
        if result.video_path and os.path.exists(result.video_path):
            st.subheader("Generated Video")
            st.video(result.video_path)
        elif result.audio_path and os.path.exists(result.audio_path):
            st.subheader("Generated Audio (video composition unavailable)")
            st.audio(result.audio_path)

        # Audit trail
        from src.audit import get_audit_trail
        trail = get_audit_trail("video")
        if trail:
            with st.expander("Pipeline Audit Trail"):
                for entry in trail:
                    status_icon = {"success": "✅", "fallback": "⚠️", "error": "❌"}.get(entry.status, "ℹ️")
                    st.markdown(
                        f"{status_icon} **{entry.agent_name}** | {entry.action} | "
                        f"Model: `{entry.model_used}` | {entry.latency_ms}ms | {entry.status}"
                    )

# --- Footer ---
st.divider()
st.caption(
    "Built for ET AI Hackathon 2026 | Track 8: AI-Native News Experience | "
    "Architecture: 12 agents, 3 models (Gemini Pro + Flash + Ollama), smart routing | "
    "Powered by Google ADK + FastAPI + Streamlit"
)
