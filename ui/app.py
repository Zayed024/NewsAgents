"""Streamlit frontend for ET AI News Navigator — 3-tab interface."""

import sys
import os
import asyncio
import time
import math
from datetime import datetime

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


def infer_text_sentiment(text: str) -> str:
    """Infer coarse sentiment from text for contrarian framing."""
    lowered = (text or "").lower()
    bullish_tokens = ["rally", "surge", "growth", "upside", "beat", "profit", "optimistic"]
    bearish_tokens = ["decline", "risk", "fall", "loss", "downside", "weak", "concern"]
    bullish_hits = sum(1 for token in bullish_tokens if token in lowered)
    bearish_hits = sum(1 for token in bearish_tokens if token in lowered)

    if bullish_hits > bearish_hits:
        return "bullish"
    if bearish_hits > bullish_hits:
        return "bearish"
    return "neutral"


def _parse_dt_for_sort(raw_value: str) -> datetime:
    """Parse timestamps for recent-first sorting; invalid values map to oldest."""
    if not raw_value:
        return datetime.min
    try:
        normalized = str(raw_value).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return datetime.min


def get_recent_items_for_pulse(section_articles: list[dict], window_size: int = 5) -> list[dict]:
    """Extract recent article dicts from wrapped section items for sentiment pulse."""
    items = [wrapped.get("item", {}) for wrapped in (section_articles or []) if wrapped.get("item")]
    sorted_items = sorted(
        items,
        key=lambda item: _parse_dt_for_sort(item.get("published_at", "")),
        reverse=True,
    )
    return sorted_items[:max(1, window_size)]


def compute_story_arc_pulse(scene_plan):
    """Compute pulse for story arc using the latest scene sentiments as proxy signals."""
    if not scene_plan or not getattr(scene_plan, "scenes", None):
        return None

    from src.agents.sentiment_pulse import compute_sentiment_pulse

    class _Meta:
        def __init__(self, sentiment: str, credibility_score: float):
            self.sentiment = sentiment
            self.credibility_score = credibility_score

    sentiment_map = {
        "positive": "bullish",
        "negative": "bearish",
        "neutral": "neutral",
        "bullish": "bullish",
        "bearish": "bearish",
        "cautious": "neutral",
    }

    recent_scenes = list(scene_plan.scenes or [])[-5:]
    synthetic_items = []
    synthetic_metadata = {}

    for idx, scene in enumerate(recent_scenes):
        scene_id = f"scene-{idx}"
        synthetic_items.append({"id": scene_id, "published_at": f"2026-01-01T00:00:0{idx}"})
        mapped_sentiment = sentiment_map.get((scene.sentiment or "neutral").lower(), "neutral")
        synthetic_metadata[scene_id] = _Meta(mapped_sentiment, 0.8)

    return compute_sentiment_pulse(
        topic="story arc",
        recent_items=synthetic_items,
        metadata_map=synthetic_metadata,
        window_size=5,
    )


def build_entity_graph_dot(entity_navigation: dict) -> str:
    """Build a compact Graphviz graph from entity-to-angle navigation data."""
    lines = [
        "digraph EntityGraph {",
        "rankdir=LR;",
        'graph [fontsize=10 fontname="Arial"];',
        'node [shape=box style=rounded fontsize=10 fontname="Arial"];',
        'edge [fontsize=9 fontname="Arial"];',
    ]

    for entity_type, entries in (entity_navigation or {}).items():
        for entry in entries or []:
            entity_name = str(entry.get("entity", "")).strip()
            if not entity_name:
                continue

            entity_node = f'{entity_type}:{entity_name}'
            lines.append(f'"{entity_node}" [label="{entity_name}\\n({entity_type})" color="#2563eb"];')

            for angle_name in entry.get("angles", []) or []:
                angle_node = f'angle:{angle_name}'
                lines.append(f'"{angle_node}" [label="{angle_name}" color="#ea580c"];')
                lines.append(f'"{entity_node}" -> "{angle_node}";')

    lines.append("}")
    return "\n".join(lines)


def build_entity_graph_interactive(entity_navigation: dict):
    """Build an interactive Plotly entity graph; return None if Plotly is unavailable."""
    try:
        import plotly.graph_objects as go
    except Exception:
        return None

    entity_nodes: dict[str, dict] = {}
    angle_nodes: set[str] = set()
    edges: list[tuple[str, str, int, int]] = []

    for entity_type, entries in (entity_navigation or {}).items():
        for entry in entries or []:
            entity_name = str(entry.get("entity", "")).strip()
            if not entity_name:
                continue

            node_id = f"{entity_type}:{entity_name}"
            entity_nodes[node_id] = {
                "name": entity_name,
                "type": entity_type,
                "article_count": int(entry.get("article_count", 0)),
                "angle_count": int(entry.get("angle_count", 0)),
            }

            for angle_name in entry.get("angles", []) or []:
                angle = str(angle_name).strip()
                if not angle:
                    continue
                angle_nodes.add(angle)
                edges.append((node_id, angle, int(entry.get("article_count", 0)), int(entry.get("angle_count", 0))))

    if not entity_nodes or not angle_nodes:
        return None

    entity_ids = list(entity_nodes.keys())
    angle_ids = sorted(angle_nodes)

    positions: dict[str, tuple[float, float]] = {}

    # Place entity nodes on the left in a circular arc.
    n_entities = len(entity_ids)
    for i, node_id in enumerate(entity_ids):
        theta = (2 * math.pi * i / max(1, n_entities)) - (math.pi / 2)
        x = -1.4 + 0.35 * math.cos(theta)
        y = 0.9 * math.sin(theta)
        positions[node_id] = (x, y)

    # Place angle nodes on the right in a vertical lane.
    n_angles = len(angle_ids)
    for i, angle_id in enumerate(angle_ids):
        y = 0 if n_angles == 1 else 1.0 - (2.0 * i / (n_angles - 1))
        positions[f"angle:{angle_id}"] = (1.4, y)

    edge_x: list[float] = []
    edge_y: list[float] = []
    hover_x: list[float] = []
    hover_y: list[float] = []
    hover_text: list[str] = []

    for src, angle, article_count, angle_count in edges:
        sx, sy = positions[src]
        tx, ty = positions[f"angle:{angle}"]
        edge_x.extend([sx, tx, None])
        edge_y.extend([sy, ty, None])

        hover_x.append((sx + tx) / 2)
        hover_y.append((sy + ty) / 2)
        hover_text.append(
            f"Entity: {entity_nodes[src]['name']}<br>"
            f"Angle: {angle}<br>"
            f"Entity article count: {article_count}<br>"
            f"Entity angle count: {angle_count}"
        )

    node_x: list[float] = []
    node_y: list[float] = []
    node_text: list[str] = []
    node_labels: list[str] = []
    node_color: list[str] = []

    for node_id in entity_ids:
        x, y = positions[node_id]
        meta = entity_nodes[node_id]
        node_x.append(x)
        node_y.append(y)
        node_labels.append(meta["name"])
        node_color.append("#2563eb")
        node_text.append(
            f"Entity: {meta['name']}<br>"
            f"Type: {meta['type']}<br>"
            f"Articles: {meta['article_count']}<br>"
            f"Related angles: {meta['angle_count']}"
        )

    for angle in angle_ids:
        x, y = positions[f"angle:{angle}"]
        node_x.append(x)
        node_y.append(y)
        node_labels.append(angle)
        node_color.append("#ea580c")
        node_text.append(f"Angle: {angle}")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(color="#94a3b8", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            marker=dict(size=8, color="rgba(0,0,0,0)"),
            hoverinfo="text",
            hovertext=hover_text,
            name="Connections",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            marker=dict(size=18, color=node_color, line=dict(color="#0f172a", width=1)),
            text=node_labels,
            textposition="top center",
            hoverinfo="text",
            hovertext=node_text,
            name="Nodes",
            showlegend=False,
        )
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        height=460,
    )

    return fig


# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("ET AI News Navigator")
    st.caption("AI-Native News Experience | Track 8 | ET AI Hackathon 2026")
with col2:
    st.markdown("**Multi-Agent Architecture**")
    st.caption("12 agents | 3 models | Smart routing")
    if st.button("Settings", key="open_settings_page", use_container_width=True):
        st.session_state["show_settings_page"] = True
        st.rerun()

if st.session_state.get("show_settings_page", False):
    back_col, title_col = st.columns([1, 4])
    with back_col:
        if st.button("Back", key="close_settings_page"):
            st.session_state["show_settings_page"] = False
            st.rerun()
    with title_col:
        st.subheader("Settings")

    st.caption("Dedicated settings page for runtime flags, ops actions, and compliance controls.")
    st.markdown("**Runtime Flags**")

    from src.config import is_retrieval_contracts_enabled
    from src.tools.corpus.compliance import (
        generate_compliance_report,
        is_corpus_kill_switch_enabled,
        load_compliance_snapshots,
    )

    flag_col1, flag_col2 = st.columns(2)
    with flag_col1:
        st.metric("Retrieval Contracts", "Enabled" if is_retrieval_contracts_enabled() else "Disabled")
    with flag_col2:
        st.metric("Corpus Kill Switch", "On" if is_corpus_kill_switch_enabled() else "Off")

    st.divider()
    st.markdown("**Ops**")

    from src.tools.corpus.operations import (
        compute_freshness_metrics,
        load_recent_run_summaries,
        run_crawl_refresh,
        run_subset_refresh,
    )

    ops_topic = st.text_input("Ops topic", value="Union Budget 2026", key="settings_ops_topic")
    ops_max_pages = st.number_input("Max pages", min_value=1, max_value=120, value=60, key="settings_ops_max_pages")
    ops_max_depth = st.number_input("Max depth", min_value=1, max_value=4, value=2, key="settings_ops_max_depth")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run Crawl Refresh", key="settings_run_crawl_refresh"):
            with st.spinner("Running crawl refresh..."):
                try:
                    summary = run_crawl_refresh(
                        topic=ops_topic,
                        max_pages=int(ops_max_pages),
                        max_depth=int(ops_max_depth),
                    )
                    st.session_state["settings_last_crawl_summary"] = summary
                    st.success(f"Crawl refresh completed with status: {summary.get('status', 'unknown')}")
                except Exception as e:
                    st.error(f"Crawl refresh failed: {e}")
    with c2:
        if st.button("Run Subset Refresh", key="settings_run_subset_refresh"):
            with st.spinner("Running subset refresh..."):
                try:
                    summary = run_subset_refresh(topics=[ops_topic])
                    st.session_state["settings_last_subset_summary"] = summary
                    st.success(f"Subset refresh completed with status: {summary.get('status', 'unknown')}")
                except Exception as e:
                    st.error(f"Subset refresh failed: {e}")

    if st.button("Refresh Freshness Metrics", key="settings_refresh_metrics"):
        try:
            st.session_state["settings_freshness_metrics"] = compute_freshness_metrics()
        except Exception as e:
            st.error(f"Failed to load freshness metrics: {e}")

    metrics = st.session_state.get("settings_freshness_metrics")
    if metrics:
        with st.expander("Freshness Metrics", expanded=False):
            st.json(metrics)

    if st.button("Load Recent Run Summaries", key="settings_load_run_summaries"):
        try:
            st.session_state["settings_run_summaries"] = load_recent_run_summaries(limit=20)
        except Exception as e:
            st.error(f"Failed to load run summaries: {e}")

    summaries = st.session_state.get("settings_run_summaries")
    if summaries:
        with st.expander("Recent Run Summaries", expanded=False):
            st.json(summaries)

    st.divider()
    st.markdown("**Compliance**")

    if st.button("Load Compliance Snapshots", key="settings_load_compliance_snapshots"):
        try:
            st.session_state["settings_compliance_snapshots"] = load_compliance_snapshots(limit=100)
        except Exception as e:
            st.error(f"Failed to load compliance snapshots: {e}")

    if st.button("Generate Compliance Report", key="settings_generate_compliance_report"):
        try:
            st.session_state["settings_compliance_report"] = generate_compliance_report(limit=500, persist=False)
        except Exception as e:
            st.error(f"Failed to generate compliance report: {e}")

    snapshots = st.session_state.get("settings_compliance_snapshots")
    if snapshots:
        with st.expander("Compliance Snapshots", expanded=False):
            st.json(snapshots[-20:])

    compliance_report = st.session_state.get("settings_compliance_report")
    if compliance_report:
        with st.expander("Compliance Report", expanded=False):
            st.json(compliance_report)

    st.divider()
    st.markdown("**Measurement + A/B**")
    ab_days = st.slider("Summary window (days)", min_value=7, max_value=180, value=30, key="settings_ab_days")

    if st.button("Load A/B Summary", key="settings_load_ab_summary"):
        try:
            from src.agents.ab_measurement import get_ab_test_summary

            st.session_state["settings_ab_summary"] = get_ab_test_summary(days=int(ab_days))
        except Exception as e:
            st.error(f"Failed to load A/B summary: {e}")

    if st.button("Load Recent A/B Runs", key="settings_load_ab_runs"):
        try:
            from src.agents.ab_measurement import list_ab_test_runs

            st.session_state["settings_ab_runs"] = list_ab_test_runs(limit=25)
        except Exception as e:
            st.error(f"Failed to load A/B runs: {e}")

    ab_summary = st.session_state.get("settings_ab_summary")
    if ab_summary:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total A/B Runs", ab_summary.get("total_runs", 0))
        m2.metric("Personalized Win Rate", f"{ab_summary.get('personalized_win_rate', 0) * 100:.1f}%")
        m3.metric("Avg Relevance Lift", f"{ab_summary.get('avg_relevance_lift', 0):.3f}")
        m4.metric("Avg Cost / Run", f"${ab_summary.get('avg_cost_per_run', 0):.4f}")

        with st.expander("A/B Daily Trend", expanded=False):
            st.json(ab_summary.get("daily_trend", []))

    ab_runs = st.session_state.get("settings_ab_runs")
    if ab_runs:
        with st.expander("Recent A/B Runs", expanded=False):
            st.json(ab_runs)

    st.stop()

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "News Navigator",
    "My ET — Create Your Profile",
    "Personalised Feed",
    "Vernacular Video",
])

# ============================================================
# TAB 1: NEWS NAVIGATOR (Primary Showcase)
# ============================================================
with tab1:
    st.header("Union Budget 2026 — Interactive Intelligence Briefing")
    st.markdown("*22 articles synthesised into navigable angles with interactive Q&A*")

    navigator_source_options = {
        "Budget demo corpus (22 curated budget articles)": "budget",
        "Homepage corpus (latest mixed-category stories)": "homepage",
    }
    navigator_source_label = st.selectbox(
        "Navigator article source",
        options=list(navigator_source_options.keys()),
        key="navigator_source_label",
    )
    navigator_source = navigator_source_options[navigator_source_label]

    topic = st.text_input(
        "Briefing topic",
        value="Union Budget 2026",
        key="navigator_topic",
    )
    navigator_max_items = st.slider(
        "Articles to include",
        min_value=5,
        max_value=50,
        value=22,
        key="navigator_max_items",
    )
    enforce_topic_coverage = st.checkbox(
        "Enforce topic coverage scan across available corpus articles",
        value=True,
        key="navigator_enforce_topic_coverage",
    )

    # Generate briefing button
    if st.button("Generate Briefing", key="gen_briefing", type="primary"):
        with st.spinner("Running 5-agent pipeline: Ingest → Extract → Cluster → Synthesise..."):
            try:
                from src.tools.article_loader import load_budget_articles, load_homepage_articles
                from src.agents.navigator.pipeline import run_navigator_pipeline

                if navigator_source == "homepage":
                    articles = load_homepage_articles(max_items=navigator_max_items)
                else:
                    articles = load_budget_articles(topic=topic, max_items=navigator_max_items)
                start = time.time()
                result = run_async(
                    run_navigator_pipeline(
                        articles,
                        "navigator",
                        topic=topic,
                        enforce_topic_coverage=enforce_topic_coverage,
                    )
                )
                elapsed = time.time() - start

                st.session_state["briefing"] = result
                st.session_state["briefing_time"] = elapsed
                st.session_state["navigator_article_count"] = len(articles)
                st.success(f"Briefing generated in {elapsed:.1f}s — {len(result.angles)} angles, {len(result.syntheses)} syntheses")
            except Exception as e:
                st.error(f"Pipeline error: {e}")

    # Display briefing if available
    if "briefing" in st.session_state:
        result = st.session_state["briefing"]

        # Metrics row
        # Cost summary
        from src.audit import get_session_cost_summary
        cost = get_session_cost_summary("navigator")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Articles Processed", st.session_state.get("navigator_article_count", "-"))
        m2.metric("Angles Identified", len(result.angles))
        m3.metric("Pipeline Time", f"{st.session_state.get('briefing_time', 0):.1f}s")
        m4.metric("Agents Used", "7")
        m5.metric("Est. Cost", f"${cost['total_cost_usd']:.4f}")

        st.divider()

        # Entity graph and explorer (always visible section)
        st.subheader("Entity Graph")
        st.caption("Explore how extracted entities connect to briefing angles.")

        entity_navigation = getattr(result, "entity_navigation", {}) or {}
        entity_types = [etype for etype, items in entity_navigation.items() if items]

        if entity_types:
            graph_fig = build_entity_graph_interactive(entity_navigation)
            if graph_fig is not None:
                st.plotly_chart(graph_fig, use_container_width=True, key="entity_graph_interactive")
            else:
                graph_dot = build_entity_graph_dot(entity_navigation)
                st.graphviz_chart(graph_dot)

            st.markdown("**Entity Explorer**")
            selected_type = st.selectbox(
                "Entity type",
                options=entity_types,
                key="entity_type_selector",
            )

            entries = entity_navigation.get(selected_type, [])
            entity_labels = [
                f"{entry.get('entity', 'Unknown')} ({entry.get('article_count', 0)} articles, {entry.get('angle_count', 0)} angles)"
                for entry in entries
            ]

            if entity_labels:
                selected_label = st.selectbox(
                    "Entity",
                    options=entity_labels,
                    key="entity_name_selector",
                )
                selected_index = entity_labels.index(selected_label)
                selected_entry = entries[selected_index]

                related_angles = selected_entry.get("angles", [])
                if related_angles:
                    st.caption("Related angles")
                    for idx, angle_name in enumerate(related_angles):
                        if st.button(f"Open angle: {angle_name}", key=f"entity_angle_btn_{idx}_{angle_name}"):
                            st.session_state["angle_selector"] = angle_name
                            st.rerun()
        else:
            st.info("No entity graph data available for this run yet. Generate a new briefing to populate entity links.")

        st.divider()

        # Angle selector
        angle_names = [a.angle_name for a in result.angles]
        selected_angle = st.radio(
            "Select an angle to explore:",
            angle_names,
            horizontal=True,
            key="angle_selector",
        )

        # Log engagement signal
        from src.agents.engagement_tracker import log_angle_click
        if selected_angle:
            log_angle_click("demo_user", selected_angle, "navigator")

        nav_contrarian_cache = st.session_state.setdefault("phase8_nav_contrarian_cache", {})

        # Show synthesis for selected angle
        selected_synthesis = None
        for synthesis in result.syntheses:
            if synthesis.angle_name == selected_angle:
                selected_synthesis = synthesis
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

        if selected_synthesis:
            nav_contrarian_key = f"navigator:{selected_synthesis.angle_name}"
            nav_show_key = f"show_nav_contrarian_{selected_synthesis.angle_name}"

            if st.button("⚖️ Hear the other side", key=f"nav_contrarian_btn_{selected_synthesis.angle_name}"):
                st.session_state[nav_show_key] = True
                if nav_contrarian_key not in nav_contrarian_cache:
                    with st.spinner("Generating a contrarian take for this angle..."):
                        try:
                            from src.agents.contrarian_view import generate_contrarian_view

                            synthesis_text = selected_synthesis.synthesis or ""
                            key_takeaways_text = " ".join(selected_synthesis.key_takeaways or [])
                            combined_text = f"{synthesis_text}\n{key_takeaways_text}".strip()

                            contrarian_summary = run_async(
                                generate_contrarian_view(
                                    item_title=selected_synthesis.angle_name,
                                    item_text=combined_text,
                                    current_sentiment=infer_text_sentiment(combined_text),
                                    session_id="navigator",
                                )
                            )
                            nav_contrarian_cache[nav_contrarian_key] = contrarian_summary.model_dump()
                        except Exception as e:
                            st.error(f"Could not generate contrarian view: {e}")

            if st.session_state.get(nav_show_key, False):
                nav_contrarian = nav_contrarian_cache.get(nav_contrarian_key)
                if nav_contrarian:
                    with st.container():
                        st.markdown("**Contrarian View**")
                        st.caption(f"Main read: {nav_contrarian.get('primary_take', '')}")
                        st.markdown(f"- **Other side:** {nav_contrarian.get('other_side_take', '')}")
                        st.markdown(
                            f"- **Strongest supporting evidence:** {nav_contrarian.get('strongest_evidence_for_other_side', '')}"
                        )
                        st.markdown(
                            f"- **What would change the view:** {nav_contrarian.get('what_would_change_my_mind', '')}"
                        )

        st.divider()

        # Interactive Q&A
        st.subheader("Ask a Follow-up Question")
        st.caption("Each answer is non-overlapping — asking different questions yields genuinely different insights.")

        suggested_questions = [q for q in (getattr(result, "suggested_questions", []) or []) if q]
        suggested_question_to_run = ""
        if suggested_questions:
            st.markdown("**Suggested follow-up questions**")
            for idx, suggested_q in enumerate(suggested_questions[:6], start=1):
                if st.button(suggested_q, key=f"nav_suggested_q_{idx}", use_container_width=True):
                    st.session_state["nav_question"] = suggested_q
                    suggested_question_to_run = suggested_q

        question = st.text_input(
            "Your question:",
            placeholder="e.g., What does this mean for IT stocks?",
            key="nav_question",
        )

        run_manual_question = st.button("Ask", key="ask_btn")
        question_to_run = suggested_question_to_run or (question if run_manual_question else "")

        if question_to_run:
            with st.spinner("QueryResponder agent processing..."):
                try:
                    from src.agents.navigator.pipeline import handle_query
                    qr = run_async(handle_query(question_to_run, "navigator"))
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

        # Engagement summary
        from src.agents.engagement_tracker import get_engagement_summary, get_user_interest_vector
        eng = get_engagement_summary()
        interest = get_user_interest_vector("demo_user")
        if eng["total_sessions"] > 0:
            with st.expander("Engagement Tracking (Cross-session Learning)"):
                e1, e2, e3 = st.columns(3)
                e1.metric("Sessions", eng["total_sessions"])
                e2.metric("Queries Logged", eng["total_queries"])
                e3.metric("Engagement Depth", interest["engagement_depth"].title())
                if interest["preferred_angles"]:
                    st.caption(f"Preferred angles: {', '.join(interest['preferred_angles'])}")
                if eng["top_angles"]:
                    st.caption(f"Most clicked angles: {', '.join(f'{a} ({c})' for a, c in eng['top_angles'])}")

        # --- NEW: Reading Path, Contradictions, Blind Spots ---
        from src.agents.navigator.pipeline import _briefing_cache
        _cache = _briefing_cache.get("navigator", {})

        reading_path = _cache.get("reading_path", {})
        if reading_path and reading_path.get("path"):
            with st.expander("If You Only Have 2 Minutes — Optimal Reading Path", expanded=False):
                st.caption(reading_path.get("path_rationale", ""))
                for step in reading_path["path"]:
                    st.markdown(
                        f"**{step.get('position', '?')}.** [{step.get('article_id', '')}] "
                        f"**{step.get('title', '')}** ({step.get('read_time_minutes', '?')} min)"
                    )
                    st.caption(f"Why: {step.get('why_read_this', '')}")
                total = reading_path.get("total_estimated_minutes", 0)
                st.markdown(f"**Total: {total} minutes**")
                skip = reading_path.get("skip_if_short_on_time", "")
                if skip:
                    st.caption(f"Short on time? Skip: {skip}")

        contradictions = _cache.get("contradictions", [])
        if contradictions:
            with st.expander(f"Cross-Article Contradictions ({len(contradictions)} found)", expanded=False):
                for c in contradictions:
                    severity = c.get("severity", "medium")
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "🟡")
                    st.markdown(f"{icon} **{c.get('topic', 'Disagreement')}** ({severity})")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**View A** ({', '.join(c.get('source_a', []))}):")
                        st.caption(c.get("claim_a", ""))
                    with col_b:
                        st.markdown(f"**View B** ({', '.join(c.get('source_b', []))}):")
                        st.caption(c.get("claim_b", ""))
                    st.caption(f"Why it matters: {c.get('why_it_matters', '')}")
                    st.divider()

        blind_spots = _cache.get("blind_spots", [])
        if blind_spots:
            with st.expander(f"Coverage Blind Spots ({len(blind_spots)} gaps)", expanded=False):
                st.caption("Important topics not covered by any article in this set:")
                for bs in blind_spots:
                    imp = bs.get("importance", "medium")
                    icon = "🔴" if imp == "high" else "🟡"
                    st.markdown(f"{icon} **{bs.get('topic', '')}**")
                    st.caption(f"{bs.get('why_it_matters', '')}")
                    st.caption(f"Expected: {bs.get('expected_coverage', '')}")

        # Audit trail with cost
        if result.audit_trail:
            with st.expander("Audit Trail (Enterprise Readiness)"):
                cost_info = get_session_cost_summary("navigator")
                st.caption(
                    f"Total: {cost_info['steps']} steps | "
                    f"~{cost_info['total_input_tokens']} input tokens | "
                    f"${cost_info['total_cost_usd']:.4f} estimated cost"
                )
                for entry in result.audit_trail:
                    status_icon = {"success": "✅", "fallback": "⚠️", "error": "❌"}.get(entry.status, "ℹ️")
                    cost_str = f" | ~${entry.estimated_cost_usd:.5f}" if entry.estimated_cost_usd > 0 else ""
                    st.markdown(
                        f"{status_icon} **{entry.agent_name}** | {entry.action} | "
                        f"Model: `{entry.model_used}` | {entry.latency_ms}ms{cost_str}"
                    )

# ============================================================
# TAB 2: MY ET — USER CREATION & ONBOARDING (Phase 1)
# ============================================================
with tab2:
    st.header("🎯 My ET — Create Your Personalized Newsroom")
    st.markdown("*Answer a few quick questions and get news tailored to you*")
    
    # Session state for form tracking
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = "mode_select"
    if "quick_answers" not in st.session_state:
        st.session_state.quick_answers = {}
    if "deep_answers" not in st.session_state:
        st.session_state.deep_answers = {}
    
    # Step 1: Choose quick or deep setup
    if st.session_state.onboarding_step == "mode_select":
        st.subheader("Step 1: Choose Your Setup")
        st.markdown("Quick setup takes 2 minutes. Deep setup gives us more context (5 minutes).")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚡ Quick Start (4 questions)", key="quick_mode", use_container_width=True):
                st.session_state.is_deep_setup = False
                st.session_state.onboarding_step = "questions"
                st.rerun()
        
        with col2:
            if st.button("🔍 Deep Setup (10 questions)", key="deep_mode", use_container_width=True):
                st.session_state.is_deep_setup = True
                st.session_state.onboarding_step = "questions"
                st.rerun()
    
    # Step 2: Collect answers
    elif st.session_state.onboarding_step == "questions":
        from src.agents.onboarding import QUICK_START_QUESTIONS, DEEP_SETUP_QUESTIONS
        
        st.subheader("Step 2: Tell Us About Yourself")
        
        # Basic info
        name = st.text_input(
            "What's your name?",
            value=st.session_state.get("user_name", ""),
            key="user_name_input",
        )
        st.session_state.user_name = name
        
        st.divider()
        
        # Quick start questions
        quick_questions = QUICK_START_QUESTIONS
        for q in quick_questions:
            if q["type"] == "single_choice":
                st.session_state.quick_answers[q["id"]] = st.radio(
                    q["question"],
                    q["options"],
                    key=f"q_{q['id']}",
                    index=0,
                )
            elif q["type"] == "multi_choice":
                st.session_state.quick_answers[q["id"]] = st.multiselect(
                    q["question"],
                    q["options"],
                    key=f"q_{q['id']}",
                    max_selections=3 if "pick up to" in q["question"].lower() else None,
                )
            st.markdown("")
        
        # Deep setup questions if selected
        if st.session_state.is_deep_setup:
            st.divider()
            st.markdown("### Additional Details")
            
            deep_questions = DEEP_SETUP_QUESTIONS
            for q in deep_questions:
                if q["type"] == "single_choice":
                    st.session_state.deep_answers[q["id"]] = st.radio(
                        q["question"],
                        q["options"],
                        key=f"deep_{q['id']}",
                    )
                elif q["type"] == "multi_choice":
                    st.session_state.deep_answers[q["id"]] = st.multiselect(
                        q["question"],
                        q["options"],
                        key=f"deep_{q['id']}",
                    )
                st.markdown("")
        
        # Submit button
        if st.button("Create My Profile", key="create_profile_btn", type="primary", use_container_width=True):
            if not st.session_state.user_name.strip():
                st.error("Please enter your name")
            else:
                # Call API to create user
                try:
                    import requests
                    
                    payload = {
                        "name": st.session_state.user_name,
                        "quick_start_answers": st.session_state.quick_answers,
                        "is_deep_setup": st.session_state.is_deep_setup,
                        "deep_setup_answers": st.session_state.deep_answers,
                    }
                    
                    response = requests.post(
                        "http://localhost:8000/api/v1/users/create",
                        json=payload,
                        timeout=30,
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.created_user = result
                        st.session_state.onboarding_step = "success"
                        st.rerun()
                    else:
                        st.error(f"Error creating profile: {response.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")
    
    # Step 3: Success
    elif st.session_state.onboarding_step == "success":
        user = st.session_state.created_user
        st.success("✅ Profile Created Successfully!")
        
        st.markdown(f"""
        ### Welcome, **{user['name']}**!
        
        **Your Profile:**
        - **Role:** {user['role']}
        - **Reading Level:** {user['reading_level'].title()}
        - **Preferred Format:** {user['preferred_format'].replace('_', ' ').title()}
        - **Interests:** {', '.join(user['priority_topics'])}
        
        Your personalized feed will start appearing in the **Personalized Feed** tab!
        """)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("View Your Profile", use_container_width=True):
                st.session_state.new_user_id = user["user_id"]
                st.session_state.view_profile = True
        
        with col2:
            if st.button("Create Another Profile", use_container_width=True):
                st.session_state.onboarding_step = "mode_select"
                st.session_state.quick_answers = {}
                st.session_state.deep_answers = {}
                st.rerun()
        
        with col3:
            if st.button("Go to Feed", use_container_width=True):
                st.info("Switch to the 'Personalised Feed' tab to view your news feed")

# ============================================================
# TAB 3: PERSONALISED FEED
# ============================================================
with tab3:
    st.header("📰 Your Personalized Feed")
    st.markdown("*News curated just for you based on your profile and interests*")
    
    # Step 1: User selector
    st.subheader("Select Your Profile")
    
    # Load available users
    from src.agents.onboarding import list_all_user_profiles
    
    available_users = list_all_user_profiles()
    if not available_users:
        st.warning("⚠️ No user profiles found. Please create one in 'My ET — Create Your Profile' tab first.")
        st.stop()
    
    user_options = {u['user_id']: f"{u['name']} ({u['role']})" for u in available_users}
    selected_user_id = st.selectbox(
        "Choose your profile:",
        options=list(user_options.keys()),
        format_func=lambda x: user_options[x],
        key="personalized_feed_user_selector",
    )
    
    # Load selected user profile
    from src.agents.onboarding import load_user_by_id
    selected_profile = load_user_by_id(selected_user_id)
    
    if selected_profile is None:
        st.error(f"❌ Could not load profile '{selected_user_id}'. Profile file may be corrupted or missing.")
        st.stop()
    
    # Display profile summary
    profile_col1, profile_col2, profile_col3 = st.columns(3)
    with profile_col1:
        st.metric("Role", selected_profile.role)
    with profile_col2:
        st.metric("Reading Level", selected_profile.reading_level.title())
    with profile_col3:
        st.metric("Top Interest", selected_profile.interests[0] if selected_profile.interests else "N/A")
    
    st.divider()
    
    # Step 2: Generate personalized feed
    st.subheader("Your Personalized News")
    
    gen_col1, gen_col2 = st.columns([2, 1])
    
    with gen_col1:
        st.markdown(f"Showing articles tailored for **{selected_profile.name}**")
    
    with gen_col2:
        if st.button("🔄 Refresh Feed", key="refresh_personalized_feed", use_container_width=True):
            st.session_state["personalized_feed"] = None
            st.rerun()
    
    # Load articles for personalization
    if st.button("Generate My Feed", key="gen_personalized_feed", type="primary", use_container_width=True):
        with st.spinner(f"Personalizing feed for {selected_profile.name}..."):
            try:
                from src.tools.article_loader import load_homepage_articles
                from src.agents.personalized_feed_pipeline import generate_personalized_user_feed
                
                articles = load_homepage_articles()
                
                # Convert dict articles to Article objects
                from src.models import Article
                article_objs = [
                    Article(**a) if isinstance(a, dict) else a 
                    for a in articles
                ]

                article_map = {}
                for a in articles:
                    if isinstance(a, dict):
                        article_id = a.get("id")
                        if article_id:
                            article_map[article_id] = a
                    else:
                        article_map[a.id] = a.model_dump()
                
                start = time.time()
                feed_result = run_async(
                    generate_personalized_user_feed(
                        user_id=selected_profile.user_id,
                        profile=selected_profile,
                        all_articles=article_objs,
                        session_id=f"feed_{selected_profile.user_id}",
                        use_personalized_subset=True,
                        top_n=5,
                    )
                )
                elapsed = time.time() - start
                
                st.session_state["personalized_feed"] = feed_result
                st.session_state["feed_source_article_map"] = article_map
                st.session_state["feed_generation_time"] = elapsed
                st.success(f"✅ Feed generated in {elapsed:.1f}s")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Feed generation error: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
    
    # Display personalized feed if available
    if "personalized_feed" in st.session_state:
        feed_result = st.session_state["personalized_feed"]
        feed = feed_result["feed"]
        explanations = feed_result["explanations"]
        generation_time = st.session_state.get("feed_generation_time", 0)

        from src.agents.feed_organizer import (
            organize_feed_into_sections,
            get_section_summary_stats,
            filter_section_by_search,
        )
        from src.agents.metadata_enricher import (
            enrich_feed_with_metadata,
            get_urgency_badge,
            get_sentiment_emoji,
            get_credibility_stars,
            format_freshness,
            get_metadata_summary_stats,
        )

        source_article_map = st.session_state.get("feed_source_article_map", {})
        section_input_items = []
        for item in feed.feed_items:
            source = source_article_map.get(item.article_id, {})
            section_input_items.append({
                "id": item.article_id,
                "title": item.adapted_title or item.original_title,
                "content": item.adapted_content,
                "author": source.get("author", ""),
                "published_at": source.get("published_at", ""),
                "category": source.get("category", ""),
                "tags": source.get("tags", []),
                "original_title": item.original_title,
                "format_type": item.format_type,
            })

        organized = organize_feed_into_sections(
            user_id=selected_profile.user_id,
            user_profile=selected_profile,
            feed_items=section_input_items,
            explanations=explanations,
        )
        metadata_map = enrich_feed_with_metadata(section_input_items, selected_profile.model_dump())
        metadata_stats = get_metadata_summary_stats(metadata_map)

        # Feed metrics
        st.subheader("Feed Insights")
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

        with metric_col1:
            st.metric("Articles in Feed", len(feed.feed_items))
        with metric_col2:
            avg_relevance = sum(e["relevance_score"] for e in explanations) / len(explanations) if explanations else 0
            st.metric("Avg. Relevance", f"{avg_relevance:.2f} / 1.0")
        with metric_col3:
            st.metric("Sections", len(organized.sections))
        with metric_col4:
            st.metric("Generation Time", f"{generation_time:.1f}s")

        sent_dist = metadata_stats.get("sentiment_distribution", {})
        urgency_dist = metadata_stats.get("urgency_distribution", {})
        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.caption(
                f"Sentiment: 📈 {sent_dist.get('bullish', 0)} | ➡️ {sent_dist.get('neutral', 0)} | 📉 {sent_dist.get('bearish', 0)}"
            )
        with stat_col2:
            st.caption(
                f"Urgency: 🔴 {urgency_dist.get('breaking', 0)} | 🟡 {urgency_dist.get('important', 0)}"
            )
        with stat_col3:
            st.caption(f"Avg credibility: {metadata_stats.get('avg_credibility', 0):.2f} / 1.0")

        st.divider()

        st.subheader("🔥 Headline Picks")
        if organized.headline_articles:
            for h in organized.headline_articles:
                h_item = h.get("item", {})
                h_expl = h.get("explanation", {})
                h_meta = metadata_map.get(h_item.get("id"))
                title = h_item.get("title", "Untitled")
                section_name = h.get("section", "")
                st.markdown(f"**{title}**")
                st.caption(f"{section_name} | Relevance: {h_expl.get('relevance_score', 0):.2f}")
                if h_meta:
                    badge = get_urgency_badge(h_meta)
                    st.caption(
                        f"{badge if badge else 'Routine'} | {get_sentiment_emoji(h_meta)} | {get_credibility_stars(h_meta)} | {format_freshness(h_meta)}"
                    )

        st.divider()

        st.subheader("📚 Sectioned Feed")
        section_search = st.text_input(
            "Search within your feed",
            value="",
            key="phase6_feed_search",
            placeholder="Try: market, tax, policy...",
        )

        so_what_cache = st.session_state.setdefault("phase8_so_what_cache", {})
        contrarian_cache = st.session_state.setdefault("phase8_contrarian_cache", {})

        for sec_idx, section in enumerate(organized.sections):
            visible_section = filter_section_by_search(section, section_search) if section_search else section
            section_stats = get_section_summary_stats(visible_section)

            from src.agents.sentiment_pulse import compute_sentiment_pulse

            recent_section_items = get_recent_items_for_pulse(visible_section.articles, window_size=5)
            section_pulse = compute_sentiment_pulse(
                topic=visible_section.topic or visible_section.section_name,
                recent_items=recent_section_items,
                metadata_map=metadata_map,
                window_size=5,
            )

            pulse_icon_map = {
                "Bullish": "📈",
                "Cautious": "⚖️",
                "Bearish": "📉",
            }
            pulse_icon = pulse_icon_map.get(section_pulse.label, "⚖️")
            header = (
                f"{visible_section.section_name} ({visible_section.article_count})"
                f" · Avg relevance {section_stats.get('avg_relevance', 0):.2f}"
            )

            with st.expander(header, expanded=sec_idx == 0):
                if not visible_section.articles:
                    st.caption("No articles match this search in this section.")
                    continue

                st.caption(
                    f"{pulse_icon} Live Sentiment Pulse: {section_pulse.label}"
                    f" (n={section_pulse.sample_size}) — {section_pulse.reason_line}"
                )

                for item_idx, wrapped in enumerate(visible_section.articles):
                    article = wrapped.get("item", {})
                    explanation = wrapped.get("explanation", {})
                    article_id = article.get("id", f"sec{sec_idx}_item{item_idx}")
                    metadata = metadata_map.get(article_id)
                    key_base = f"{sec_idx}_{item_idx}_{article_id}"

                    with st.container():
                        feed_card_col1, feed_card_col2 = st.columns([3, 1])

                        with feed_card_col1:
                            st.markdown(f"### {article.get('title', 'Untitled')}")
                            content_preview = (article.get("content", "") or "")[:220]
                            if content_preview:
                                st.markdown(f"{content_preview}...")

                            if metadata:
                                urgency_badge = get_urgency_badge(metadata)
                                urgency_text = urgency_badge if urgency_badge else "Routine"
                                st.caption(
                                    f"{urgency_text} | {get_sentiment_emoji(metadata)} {metadata.sentiment.title()}"
                                    f" | {get_credibility_stars(metadata)} | {format_freshness(metadata)}"
                                )

                            exp_col1, exp_col2, exp_col3 = st.columns(3)
                            with exp_col1:
                                relevance = explanation.get("relevance_score", 0)
                                relevance_color = "🟢" if relevance > 0.7 else "🟡" if relevance > 0.4 else "🔴"
                                st.caption(f"{relevance_color} Relevance: {relevance:.2f}")
                            with exp_col2:
                                confidence = explanation.get("confidence", "low")
                                confidence_icon = "✓" if confidence == "high" else "~"
                                st.caption(f"{confidence_icon} Confidence: {confidence.title()}")
                            with exp_col3:
                                st.caption(f"📏 Format: {explanation.get('format_applied', 'standard').title()}")

                            boost_badge = " 🚀 **BOOSTED**" if explanation.get("boosted", False) else ""
                            st.caption(f"💡 **Why shown:** {explanation.get('why_shown', 'Relevant to your profile')}{boost_badge}")

                            matched_tags = explanation.get("matched_tags", [])
                            if matched_tags:
                                st.caption(f"#️⃣ Tags: {' | '.join(matched_tags[:3])}")

                            action_col1, action_col2 = st.columns(2)
                            so_what_cache_key = f"{selected_profile.user_id}:{article_id}"
                            contrarian_cache_key = f"{selected_profile.user_id}:{article_id}"

                            with action_col1:
                                if st.button("✨ So what for me?", key=f"so_what_{key_base}", use_container_width=True):
                                    st.session_state[f"show_so_what_{key_base}"] = True
                                    if so_what_cache_key not in so_what_cache:
                                        with st.spinner("Building a personal impact summary..."):
                                            try:
                                                from src.agents.personal_impact import generate_personal_impact

                                                so_what_summary = run_async(
                                                    generate_personal_impact(
                                                        profile=selected_profile,
                                                        item_title=article.get("title", "Untitled"),
                                                        item_text=article.get("content", ""),
                                                        session_id=f"feed_{selected_profile.user_id}",
                                                    )
                                                )
                                                so_what_cache[so_what_cache_key] = so_what_summary.model_dump()
                                            except Exception as e:
                                                st.error(f"Could not generate personal impact: {e}")

                            with action_col2:
                                if st.button("⚖️ Hear the other side", key=f"contrarian_{key_base}", use_container_width=True):
                                    st.session_state[f"show_contrarian_{key_base}"] = True
                                    if contrarian_cache_key not in contrarian_cache:
                                        with st.spinner("Generating a contrarian perspective..."):
                                            try:
                                                from src.agents.contrarian_view import generate_contrarian_view

                                                contrarian_summary = run_async(
                                                    generate_contrarian_view(
                                                        item_title=article.get("title", "Untitled"),
                                                        item_text=article.get("content", ""),
                                                        current_sentiment=getattr(metadata, "sentiment", "neutral"),
                                                        session_id=f"feed_{selected_profile.user_id}",
                                                    )
                                                )
                                                contrarian_cache[contrarian_cache_key] = contrarian_summary.model_dump()
                                            except Exception as e:
                                                st.error(f"Could not generate contrarian view: {e}")

                            if st.session_state.get(f"show_so_what_{key_base}", False):
                                so_what = so_what_cache.get(so_what_cache_key)
                                if so_what:
                                    with st.container():
                                        st.markdown("**So what this means for you**")
                                        st.caption(so_what.get("headline_impact", ""))
                                        for point in so_what.get("bullet_points", [])[:3]:
                                            st.markdown(f"- {point}")
                                        st.caption(
                                            f"Confidence: {(so_what.get('confidence', 'medium') or 'medium').title()}"
                                            f" | Caveat: {so_what.get('caveat', 'Validate with fresh disclosures.')}"
                                        )

                            if st.session_state.get(f"show_contrarian_{key_base}", False):
                                contrarian = contrarian_cache.get(contrarian_cache_key)
                                if contrarian:
                                    with st.container():
                                        st.markdown("**Contrarian View**")
                                        st.caption(f"Main read: {contrarian.get('primary_take', '')}")
                                        st.markdown(f"- **Other side:** {contrarian.get('other_side_take', '')}")
                                        st.markdown(
                                            f"- **Strongest supporting evidence:** {contrarian.get('strongest_evidence_for_other_side', '')}"
                                        )
                                        st.markdown(
                                            f"- **What would change the view:** {contrarian.get('what_would_change_my_mind', '')}"
                                        )

                        with feed_card_col2:
                            st.markdown("")
                            st.markdown("")
                            fb_col1, fb_col2 = st.columns(2)
                            with fb_col1:
                                if st.button("👍", key=f"interested_{key_base}", use_container_width=True):
                                    from src.agents.engagement_tracker import log_article_feedback

                                    log_article_feedback(
                                        user_id=selected_profile.user_id,
                                        article_id=article_id,
                                        feedback_type="interested",
                                        reason=None,
                                        session_id=f"feed_{selected_profile.user_id}",
                                    )
                                    st.toast("👍 Great! We'll show you more like this.", icon="✅")

                            with fb_col2:
                                if st.button("👎", key=f"not_interested_{key_base}", use_container_width=True):
                                    st.session_state[f"show_reason_picker_{key_base}"] = True

                            if st.session_state.get(f"show_reason_picker_{key_base}", False):
                                from src.agents.engagement_tracker import log_article_feedback, FEEDBACK_REASONS

                                with st.popover("👎 Why not interested?", use_container_width=True):
                                    st.markdown("**Help us improve your feed:**")
                                    selected_reason = st.radio(
                                        "What's the reason?",
                                        options=FEEDBACK_REASONS["not_interested"],
                                        key=f"reason_picker_{key_base}",
                                    )

                                    if st.button("Confirm", key=f"confirm_reason_{key_base}", use_container_width=True):
                                        log_article_feedback(
                                            user_id=selected_profile.user_id,
                                            article_id=article_id,
                                            feedback_type="not_interested",
                                            reason=selected_reason,
                                            session_id=f"feed_{selected_profile.user_id}",
                                        )
                                        st.session_state[f"show_reason_picker_{key_base}"] = False
                                        st.toast(f"👎 Got it! {selected_reason}. We'll improve your feed.", icon="📝")
                                        st.rerun()

                    st.divider()
        
        # A/B Comparison option
        st.subheader("📊 Compare with Baseline")
        st.markdown("*See how the personalized feed differs from generic ordering*")
        
        if st.button("Show A/B Comparison", key="show_ab_comparison", use_container_width=True):
            with st.spinner("Generating baseline feed for comparison..."):
                try:
                    from src.agents.personalized_feed_pipeline import compare_personalized_vs_baseline
                    from src.tools.article_loader import load_homepage_articles
                    from src.models import Article
                    
                    articles = load_homepage_articles()
                    article_objs = [
                        Article(**a) if isinstance(a, dict) else a 
                        for a in articles
                    ]
                    
                    comparison = run_async(
                        compare_personalized_vs_baseline(
                            user_id=selected_profile.user_id,
                            profile=selected_profile,
                            all_articles=article_objs,
                            session_id=f"comparison_{selected_profile.user_id}",
                        )
                    )

                    total_cost_usd = 0.0
                    for entry in comparison.get("audit_trail", []):
                        if isinstance(entry, dict):
                            total_cost_usd += float(entry.get("estimated_cost_usd", 0.0) or 0.0)
                        else:
                            total_cost_usd += float(getattr(entry, "estimated_cost_usd", 0.0) or 0.0)

                    from src.agents.ab_measurement import log_feed_ab_test_run

                    log_feed_ab_test_run(
                        user_id=selected_profile.user_id,
                        session_id=f"comparison_{selected_profile.user_id}",
                        delta_metrics=comparison.get("delta_metrics", {}),
                        total_cost_usd=total_cost_usd,
                    )
                    
                    st.session_state["feed_comparison"] = comparison
                    st.rerun()
                except Exception as e:
                    st.error(f"Comparison error: {str(e)}")
        
        # Display comparison if available
        if "feed_comparison" in st.session_state:
            comp = st.session_state["feed_comparison"]
            delta = comp["delta_metrics"]
            
            st.markdown("**Comparison Results**")
            
            comp_col1, comp_col2, comp_col3, comp_col4 = st.columns(4)
            with comp_col1:
                st.metric("Articles in Common", delta['articles_in_common'])
            with comp_col2:
                st.metric("Unique to Personalized", delta['unique_to_personalized'])
            with comp_col3:
                st.metric("Personalized Avg Relevance", f"{delta['personalized_avg_relevance']:.2f}")
            with comp_col4:
                st.metric("Baseline Avg Relevance", f"{delta['baseline_avg_relevance']:.2f}")
            
            st.info(f"📌 {delta['personalization_delta']}")
        
        # Feedback summary
        from src.agents.engagement_tracker import get_user_feedback_summary
        
        feedback_summary = get_user_feedback_summary(selected_profile.user_id)
        
        if feedback_summary["interested_count"] > 0 or feedback_summary["not_interested_count"] > 0:
            st.divider()
            st.subheader("📊 Your Feedback This Session")
            
            feedback_col1, feedback_col2 = st.columns(2)
            
            with feedback_col1:
                st.metric("👍 Articles You Liked", feedback_summary["interested_count"])
                if feedback_summary["interested_reasons"]:
                    with st.expander("Why you liked them"):
                        for reason, count in feedback_summary["interested_reasons"].items():
                            st.caption(f"{reason}: {count}")
            
            with feedback_col2:
                st.metric("👎 Articles Not Helpful", feedback_summary["not_interested_count"])
                if feedback_summary["not_interested_reasons"]:
                    with st.expander("Why not helpful"):
                        for reason, count in feedback_summary["not_interested_reasons"].items():
                            st.caption(f"{reason}: {count}")
            
            st.caption("💡 Your feedback helps us improve your personalized feed for next time!")



# ============================================================
# TAB 4: VERNACULAR VIDEO
# ============================================================
with tab4:
    st.header("Breaking News → Vernacular Video")
    st.markdown("*5-agent pipeline: Ingest → Script → Fact-check → Audio → Video (language selectable)*")

    # Requested Indian languages in alphabetical order.
    language_options = {
        "English": "en",
        "Bhojpuri": "bho",
        "Hindi": "hi",
        "Kannada": "kn",
        "Marathi": "mr",
        "Punjabi": "pa",
        "Tamil": "ta",
        "Telugu": "te",
    }
    selected_language_label = st.selectbox(
        "Video language",
        options=list(language_options.keys()),
        index=0,
        key="video_language",
    )
    selected_language = language_options[selected_language_label]

    selected_breaking_article_id = None
    selected_breaking_article = None

    try:
        from src.tools.article_loader import load_breaking_news_articles

        breaking_articles = load_breaking_news_articles(max_items=20)
        if breaking_articles:
            article_options = {
                f"{a.title[:90]}{'...' if len(a.title) > 90 else ''} ({a.published_at[:10]})": a.id
                for a in breaking_articles
            }
            selected_label = st.selectbox(
                "Breaking news source",
                options=list(article_options.keys()),
                key="video_breaking_article",
            )
            selected_breaking_article_id = article_options[selected_label]
            selected_breaking_article = next(
                (a for a in breaking_articles if a.id == selected_breaking_article_id),
                breaking_articles[0],
            )

        # Show source article
        with st.expander("Source Article (Breaking News)", expanded=False):
            if selected_breaking_article:
                st.markdown(f"**{selected_breaking_article.title}**")
                st.markdown(selected_breaking_article.content)
                st.caption(
                    f"Source: {selected_breaking_article.author} | {selected_breaking_article.published_at}"
                )
            else:
                st.warning("No breaking news articles found.")
    except Exception as e:
        with st.expander("Source Article (Breaking News)", expanded=False):
            st.warning(f"Could not load article: {e}")

    if st.button("Generate Video", key="gen_video", type="primary"):
        progress = st.progress(0, text="Starting pipeline...")

        try:
            from src.tools.article_loader import load_breaking_news
            from src.agents.video.pipeline import run_video_pipeline

            article = load_breaking_news(article_id=selected_breaking_article_id)
            video_session_id = f"video-{article.id}-{selected_language}-{int(time.time() * 1000)}"
            start = time.time()

            # Run pipeline with progress updates
            progress.progress(10, text="Extracting key facts...")
            result = run_async(
                run_video_pipeline(
                    article,
                    target_language=selected_language,
                    session_id=video_session_id,
                )
            )
            elapsed = time.time() - start

            progress.progress(100, text=f"Complete! {elapsed:.1f} seconds")

            st.session_state["video_result"] = result
            st.session_state["video_time"] = elapsed
            st.session_state["video_session_id"] = video_session_id
            st.session_state["video_source_title"] = article.title
            st.session_state["video_source_id"] = article.id

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
        if st.session_state.get("video_source_title"):
            st.caption(
                f"Source used: {st.session_state.get('video_source_title')} "
                f"({st.session_state.get('video_source_id')})"
            )

        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Generation Time", f"{result.generation_time_seconds:.1f}s")
        m2.metric("Target", "<60s")
        m3.metric("Status", result.status.upper())

        # Two columns: Script + Fact Check
        col_script, col_facts = st.columns(2)

        with col_script:
            st.subheader("Generated Script")
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

        if result.scene_plan and result.scene_plan.scenes:
            with st.expander(f"Story Chapters ({len(result.scene_plan.scenes)})", expanded=True):
                story_pulse = compute_story_arc_pulse(result.scene_plan)
                if story_pulse:
                    pulse_icon_map = {
                        "Bullish": "📈",
                        "Cautious": "⚖️",
                        "Bearish": "📉",
                    }
                    pulse_icon = pulse_icon_map.get(story_pulse.label, "⚖️")
                    st.caption(
                        f"{pulse_icon} Live Sentiment Pulse: {story_pulse.label}"
                        f" (n={story_pulse.sample_size}) — {story_pulse.reason_line}"
                    )

                if result.scene_plan.story_arc_summary:
                    st.info(f"Story arc: {result.scene_plan.story_arc_summary}")
                if result.scene_plan.key_players:
                    st.caption("Key players: " + ", ".join(result.scene_plan.key_players))
                if result.scene_plan.sentiment_shifts:
                    st.caption("Sentiment shifts: " + " -> ".join(result.scene_plan.sentiment_shifts))
                if result.scene_plan.contrarian_perspective:
                    st.caption("Contrarian perspective: " + result.scene_plan.contrarian_perspective)
                if result.scene_plan.watch_next:
                    st.caption("What to watch next: " + ", ".join(result.scene_plan.watch_next))

                for idx, scene in enumerate(result.scene_plan.scenes, start=1):
                    st.markdown(
                        f"**{idx}. {scene.chapter} - {scene.heading}** "
                        f"({scene.duration_seconds}s, {scene.scene_type})"
                    )
                    st.caption(scene.text)

        # Video player
        if result.video_path and os.path.exists(result.video_path):
            st.subheader("Generated Video")
            st.video(result.video_path)
        elif result.audio_path and os.path.exists(result.audio_path):
            st.subheader("Generated Audio (video composition unavailable)")
            st.audio(result.audio_path)

        # Audit trail
        from src.audit import get_audit_trail
        trail = get_audit_trail(st.session_state.get("video_session_id", "video"))
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
