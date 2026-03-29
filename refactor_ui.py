#!/usr/bin/env python
"""Refactor ui/app.py to move Settings from expander to dedicated page."""

import re

with open("ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the Settings expander in the header
old_header_section = '''with col2:
    st.markdown("**Multi-Agent Architecture**")
    st.caption("12 agents | 3 models | Smart routing")

    with st.expander("Settings", expanded=False):
        st.caption("Operations and compliance controls (separate from main product tabs)")'''

new_header_section = '''with col2:
    st.markdown("**Multi-Agent Architecture**")
    st.caption("12 agents | 3 models | Smart routing")
    if st.button("⊙ Settings", key="header_settings_btn", use_container_width=True):
        st.session_state["show_settings_page"] = True
        st.rerun()

if st.session_state.get("show_settings_page", False):
    # ============================================================
    # SETTINGS PAGE
    # ============================================================
    st.markdown("---")
    
    col_back, col_title = st.columns([1, 3])
    with col_back:
        if st.button("← Back", key="settings_back_btn"):
            st.session_state["show_settings_page"] = False
            st.rerun()
    with col_title:
        st.title("⊙ Settings")
    
    st.divider()

    # --- SYSTEM STATUS HEADER ---
    st.markdown("**System Configuration**")
    flag_col1, flag_col2 = st.columns(2)
    with flag_col1:
        flag_status_1 = "[ENABLED]" if is_retrieval_contracts_enabled() else "[DISABLED]"
        st.metric("Contracts", flag_status_1, delta=None)
    with flag_col2:
        flag_status_2 = "[LOCKED]" if is_corpus_kill_switch_enabled() else "[ACTIVE]"
        st.metric("Corpus Kill-Switch", flag_status_2, delta=None)

    st.divider()

    # ===== SECTION 1: OPS =====
    with st.expander("▶ Operations", expanded=True):
        st.caption("Crawl and refresh corpus subsets")

        # Inputs
        ops_col1, ops_col2, ops_col3 = st.columns(3)
        with ops_col1:
            ops_topic = st.text_input("Topic", value="Union Budget 2026", key="settings_ops_topic", label_visibility="collapsed")
        with ops_col2:
            ops_max_pages = st.number_input("Pages", min_value=1, max_value=120, value=60, key="settings_ops_max_pages", label_visibility="collapsed")
        with ops_col3:
            ops_max_depth = st.number_input("Depth", min_value=1, max_value=4, value=2, key="settings_ops_max_depth", label_visibility="collapsed")

        # Action buttons
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("Crawl & Refresh", key="settings_run_crawl_refresh", use_container_width=True):
                with st.spinner("Running crawl refresh..."):
                    try:
                        summary = run_crawl_refresh(
                            topic=ops_topic,
                            max_pages=int(ops_max_pages),
                            max_depth=int(ops_max_depth),
                        )
                        st.session_state["settings_last_crawl_summary"] = summary
                        st.session_state["settings_show_ops_table"] = True
                        st.success(f"[PASS] Crawl completed | Status: {summary.get('status', 'unknown')}")
                    except Exception as e:
                        st.error(f"[FAIL] {e}")

        with btn_col2:
            if st.button("Subset Refresh", key="settings_run_subset_refresh", use_container_width=True):
                with st.spinner("Running subset refresh..."):
                    try:
                        summary = run_subset_refresh(topics=[ops_topic])
                        st.session_state["settings_last_subset_summary"] = summary
                        st.session_state["settings_show_ops_table"] = True
                        st.success(f"[PASS] Subset refresh completed | Status: {summary.get('status', 'unknown')}")
                    except Exception as e:
                        st.error(f"[FAIL] {e}")

        with btn_col3:
            if st.button("Load Summaries", key="settings_load_run_summaries", use_container_width=True):
                try:
                    st.session_state["settings_run_summaries"] = load_recent_run_summaries(limit=20)
                    st.session_state["settings_show_ops_table"] = True
                except Exception as e:
                    st.error(f"[FAIL] {e}")

        # Display ops summary table
        summaries = st.session_state.get("settings_run_summaries", [])
        if st.session_state.get("settings_show_ops_table") and summaries:
            st.markdown("**Recent Runs**")
            ops_data = []
            for summary in summaries[-10:]:
                ops_data.append({
                    "Type": summary.get("operation_type", "unknown"),
                    "Topic": summary.get("topic", "—"),
                    "Status": "[PASS]" if summary.get("status") == "success" else "[WARN]",
                    "Articles": summary.get("articles_processed", 0),
                    "Time": f"{summary.get('execution_time_seconds', 0):.1f}s",
                })
            st.dataframe(ops_data, use_container_width=True, hide_index=True)

    # ===== SECTION 2: METRICS =====
    with st.expander("▶ Metrics", expanded=False):
        st.caption("Corpus freshness and quality indicators")

        if st.button("Refresh Metrics", key="settings_refresh_metrics", use_container_width=True):
            with st.spinner("Computing metrics..."):
                try:
                    st.session_state["settings_freshness_metrics"] = compute_freshness_metrics()
                    st.session_state["settings_show_metrics"] = True
                except Exception as e:
                    st.error(f"[FAIL] {e}")

        metrics = st.session_state.get("settings_freshness_metrics")
        if st.session_state.get("settings_show_metrics") and metrics:
            corpus = metrics.get("corpus", {})
            topic_subsets = metrics.get("topic_subsets", {})
            persona_subsets = metrics.get("persona_subsets", {})

            # Metric cards
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("Corpus Articles", corpus.get("article_count", 0))
            with metric_col2:
                stale_rate = topic_subsets.get("stale_rate", 0.0)
                st.metric("Topic Stale Rate", f"{stale_rate:.0%}", delta=f"{stale_rate:.1%}" if stale_rate > 0.2 else None)
            with metric_col3:
                pstale_rate = persona_subsets.get("stale_rate", 0.0)
                st.metric("Persona Stale Rate", f"{pstale_rate:.0%}", delta=f"{pstale_rate:.1%}" if pstale_rate > 0.2 else None)

            # Freshness breakdown table
            st.markdown("**Subset Freshness**")
            freshness_data = []
            for subset_name, subset_metrics in topic_subsets.get("subsets", {}).items():
                freshness_data.append({
                    "Subset": subset_name,
                    "Articles": subset_metrics.get("article_count", 0),
                    "Fresh %": f"{(1 - subset_metrics.get('stale_rate', 0)):.0%}",
                    "Avg Age": f"{subset_metrics.get('avg_age_hours', 0):.1f}h",
                })
            if freshness_data:
                st.dataframe(freshness_data, use_container_width=True, hide_index=True)

    # ===== SECTION 3: COMPLIANCE =====
    with st.expander("▶ Compliance", expanded=False):
        st.caption("Safety validators and audit logs")

        comp_btn_col1, comp_btn_col2 = st.columns(2)
        with comp_btn_col1:
            if st.button("Load Snapshots", key="settings_load_compliance_snapshots", use_container_width=True):
                try:
                    st.session_state["settings_compliance_snapshots"] = load_compliance_snapshots(limit=100)
                    st.session_state["settings_show_compliance"] = True
                except Exception as e:
                    st.error(f"[FAIL] {e}")

        with comp_btn_col2:
            if st.button("Generate Report", key="settings_generate_compliance_report", use_container_width=True):
                with st.spinner("Generating report..."):
                    try:
                        st.session_state["settings_compliance_report"] = generate_compliance_report(limit=500, persist=False)
                        st.session_state["settings_show_compliance"] = True
                    except Exception as e:
                        st.error(f"[FAIL] {e}")

        # Display compliance snapshots
        if st.session_state.get("settings_show_compliance"):
            snapshots = st.session_state.get("settings_compliance_snapshots")
            if snapshots:
                st.markdown("**Recent Validators** (last 15)")
                snap_data = []
                for snapshot in snapshots[-15:]:
                    snap_data.append({
                        "Event": snapshot.get("event_type", "unknown"),
                        "Result": "[ALLOW]" if snapshot.get("decision") == "allow" else "[DENY]",
                        "Reason": snapshot.get("denial_reason", "—")[:50],
                        "Time": snapshot.get("timestamp", "—"),
                    })
                st.dataframe(snap_data, use_container_width=True, hide_index=True)

            # Display compliance report
            compliance_report = st.session_state.get("settings_compliance_report")
            if compliance_report:
                st.markdown("**Compliance Summary**")
                comp_summary = compliance_report.get("summary", {})
                comp_col1, comp_col2, comp_col3 = st.columns(3)
                with comp_col1:
                    st.metric("Total Events", comp_summary.get("total_snapshots", 0))
                with comp_col2:
                    allow_rate = comp_summary.get("allow_rate", 0)
                    st.metric("Allow Rate", f"{allow_rate:.0%}")
                with comp_col3:
                    denial_count = comp_summary.get("denial_count", 0)
                    st.metric("Denials", denial_count, delta_color="inverse")

                # Denial reasons breakdown
                denial_reasons = comp_summary.get("denial_reasons_breakdown", {})
                if denial_reasons:
                    st.markdown("**Denial Reasons**")
                    denial_data = [
                        {"Reason": reason, "Count": count}
                        for reason, count in denial_reasons.items()
                    ]
                    st.dataframe(denial_data, use_container_width=True, hide_index=True)

else:
    # ============================================================
    # MAIN APP (TABS)
    # ============================================================'''

# Find and replace the section in the content
if old_header_section in content:
    content = content.replace(old_header_section, new_header_section)
    print("✅ Successfully refactored Settings expander to standalone page")
else:
    print("❌ Could not find the Settings section to replace")
    exit(1)

# Now add proper indentation to all the tab content (indent by 4 spaces)
# Split into lines and find the tab section
lines = content.split('\n')
output_lines = []
in_tabs_section = False
start_indent = False

for i, line in enumerate(lines):
    if '# --- Tabs ---' in line:
        start_indent = True
        in_tabs_section = True
    
    if start_indent and i > lines.index([l for l in lines if '# --- Tabs ---' in l][0]):
        # Add 4 spaces to the beginning of each line (unless it's empty)
        if line.strip():  # non-empty line
            line = "    " + line
    
    output_lines.append(line)

# Write back the refactored content
with open("ui/app.py", "w", encoding="utf-8") as f:
    f.write('\n'.join(output_lines))

print("✅ File refactored successfully")
