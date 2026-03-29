"""Streamlit frontend for ET AI News Navigator — 3-tab interface."""

import sys
import os
import asyncio
import time
import math

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

    st.stop()

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

    topic = st.text_input(
        "Briefing topic",
        value="Union Budget 2026",
        key="navigator_topic",
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
                from src.tools.article_loader import load_budget_articles
                from src.agents.navigator.pipeline import run_navigator_pipeline

                articles = load_budget_articles(topic=topic)
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
        m1.metric("Articles Processed", "22")
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

    if st.button("Generate Video", key="gen_video", type="primary"):
        progress = st.progress(0, text="Starting pipeline...")

        try:
            from src.tools.article_loader import load_breaking_news
            from src.agents.video.pipeline import run_video_pipeline

            article = load_breaking_news()
            start = time.time()

            # Run pipeline with progress updates
            progress.progress(10, text="Extracting key facts...")
            result = run_async(
                run_video_pipeline(
                    article,
                    target_language=selected_language,
                    session_id="video",
                )
            )
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
