import math
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Inngest Capacity Planner", page_icon="📬", layout="wide")

st.title("📬 Inngest & Vercel Capacity Planner")

with st.sidebar:
    st.header("Assumptions")
    steps_per_session = st.number_input(
        "Think&Act steps per session",
        min_value=1,
        value=10,
        step=1,
        help="Number of Inngest function steps per email/session."
    )
    seconds_per_step = st.number_input(
        "Seconds per think-and-act",
        min_value=1,
        value=30,
        step=1,
        help="Average execution time per Inngest function step."
    )
    tokens_per_step = st.number_input(
        "Tokens per step",
        min_value=1,
        value=3000,
        step=100,
        help="Average tokens consumed per Inngest function LLM call."
    )
    safety_buffer = st.slider(
        "Safety buffer (%)",
        min_value=0,
        max_value=100,
        value=20,
        step=5,
        help="Headroom added on top of computed requirements."
    )
    spike_scaler = st.slider(
        "Traffic spike scaler",
        min_value=1.0,
        max_value=10.0,
        value=2.0,
        step=0.1,
        help="Multiplier for handling traffic bursts and spikes."
    )
    st.caption("Tip: Safety buffer accounts for variance and retries. Spike scaler handles traffic bursts.")

st.subheader("Capacity")
c1, c2 = st.columns(2)
with c1:
    parallelism_input = st.number_input("Available parallelism", min_value=1, value=100, step=1, help="Number of concurrent Inngest functions you can run on Vercel")
with c2:
    emails_per_hour_input = st.number_input("Target emails per hour", min_value=1, value=10000, step=100, help="Desired throughput in emails per hour")

# --- Core math ---
S = steps_per_session
T = seconds_per_step

# Sessions per hour per Inngest function (a function processes steps serially for one session at a time)
sessions_per_hour_per_function = 3600 / (S * T)

# Compute achievable emails per hour from available parallelism
emails_per_hour_from_parallelism = parallelism_input * sessions_per_hour_per_function
emails_per_hour_with_buffer = emails_per_hour_from_parallelism / (1 + safety_buffer / 100)

# Compute required parallelism for target emails per hour
required_parallelism_raw = emails_per_hour_input / sessions_per_hour_per_function
required_parallelism_with_buffer = math.ceil(required_parallelism_raw * (1 + safety_buffer / 100))

# Steps per minute and token rate (use target emails per hour)
sessions_per_min = emails_per_hour_input / 60
steps_per_min = sessions_per_min * S
tpm_raw = steps_per_min * tokens_per_step

# Apply safety buffer and spike scaler, ensuring minimum tokens per step
tpm_with_buffer = tpm_raw * (1 + safety_buffer / 100)
tpm_with_spikes = tpm_with_buffer * spike_scaler
tpm_needed = max(math.ceil(tpm_with_spikes), tokens_per_step)

# Also show RPM if one LLM request per step
rpm_raw = steps_per_min
rpm_needed = math.ceil(rpm_raw)

# Total latency per session
total_latency_per_session = S * T

# Generate traffic distribution for TPM calculations
minutes = np.arange(0, 60, 1)
base_traffic = emails_per_hour_input / 60  # emails per minute

# Create spike patterns based on spike scaler
if spike_scaler <= 1.5:
    # Low spike: mostly steady with small variations
    spike_factor = 1 + 0.2 * np.sin(2 * np.pi * minutes / 30) + 0.1 * np.random.normal(0, 0.1, len(minutes))
elif spike_scaler <= 3.0:
    # Medium spike: periodic bursts
    spike_factor = 1 + 0.5 * np.sin(2 * np.pi * minutes / 20) + 0.2 * np.random.normal(0, 0.2, len(minutes))
else:
    # High spike: irregular bursts
    spike_factor = 1 + 0.8 * np.sin(2 * np.pi * minutes / 15) + 0.3 * np.random.normal(0, 0.3, len(minutes))

# Apply spike scaler but normalize to ensure total doesn't exceed hourly limit
traffic_per_minute = base_traffic * spike_factor * spike_scaler
traffic_per_minute = np.maximum(traffic_per_minute, base_traffic * 0.1)  # Minimum 10% of base

# Normalize to ensure total emails per hour doesn't exceed target
total_traffic = np.sum(traffic_per_minute)
if total_traffic > emails_per_hour_input:
    traffic_per_minute = traffic_per_minute * (emails_per_hour_input / total_traffic)

# Calculate TPM based on traffic pattern
steps_per_minute_traffic = traffic_per_minute * S
tpm_per_minute = steps_per_minute_traffic * tokens_per_step

# Calculate average and peak TPM
avg_tpm_traffic = np.mean(tpm_per_minute)
peak_tpm_traffic = np.max(tpm_per_minute)

# --- Display ---
st.markdown("### Results")

# Show comparison between what you can achieve vs what you want
c1, c2 = st.columns(2)
with c1:
    st.metric("📧 Achievable emails/hour", f"{emails_per_hour_with_buffer:,.0f}", help="Throughput with your available parallelism")
with c2:
    st.metric("🎯 Target emails/hour", f"{emails_per_hour_input:,}", help="Your desired throughput")

# Show whether you have enough parallelism
if emails_per_hour_with_buffer >= emails_per_hour_input:
    st.success(f"✅ You have sufficient parallelism to meet your target!")
else:
    st.warning(f"⚠️ You need {required_parallelism_with_buffer:,} concurrent Inngest functions to meet your target (you have {parallelism_input:,})")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Required parallelism", f"{required_parallelism_with_buffer:,}", help="Parallelism needed for target throughput")
with c2:
    st.metric("Average TPM needed", f"{avg_tpm_traffic:,.0f} TPM", help="Average tokens per minute based on traffic pattern")
with c3:
    st.metric("Peak TPM needed", f"{peak_tpm_traffic:,.0f} TPM", help="Peak tokens per minute during traffic spikes")
with c4:
    st.metric("Total latency per session", f"{total_latency_per_session:.1f}s", help="Total time to process one email session")

st.markdown("---")
st.markdown("### Traffic Distribution Visualization")

# Create DataFrame for plotting
df = pd.DataFrame({
    'Minute': minutes,
    'Emails per minute': traffic_per_minute,
    'Base rate': base_traffic
})

# Create the chart
fig = px.line(df, x='Minute', y=['Emails per minute', 'Base rate'], 
              title=f'Hourly Traffic Distribution (Spike Scaler: {spike_scaler}x)',
              labels={'value': 'Emails per minute', 'variable': 'Traffic Type'})

fig.update_layout(
    xaxis_title='Minute of Hour',
    yaxis_title='Emails per Minute',
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True)

# Show traffic summary
total_emails_shown = np.sum(traffic_per_minute)
max_traffic_per_minute = np.max(traffic_per_minute)
min_traffic_per_minute = np.min(traffic_per_minute)

st.write(f"""
**Traffic Summary:**
- **Total emails in chart**: {total_emails_shown:,.0f} (target: {emails_per_hour_input:,})
- **Peak traffic per minute**: {max_traffic_per_minute:,.0f} emails
- **Minimum traffic per minute**: {min_traffic_per_minute:,.0f} emails
- **Peak-to-average ratio**: {max_traffic_per_minute / base_traffic:.1f}x

**TPM Requirements Based on Traffic Pattern:**
- **Average TPM needed**: {avg_tpm_traffic:,.0f} TPM
- **Peak TPM needed**: {peak_tpm_traffic:,.0f} TPM
- **Peak-to-average TPM ratio**: {peak_tpm_traffic / avg_tpm_traffic:.1f}x
""")

st.markdown("---")
st.markdown("### API Rate Planning")
st.write(
    f"""
- **Steps per minute**: **{steps_per_min:,.2f}**  
- **Requests per minute (1 request/step)**: **{rpm_needed:,} RPM**  
- **Tokens per minute (raw)**: **{tpm_raw:,.0f} TPM**  
- **Tokens per minute (with buffer)**: **{tpm_with_buffer:,.0f} TPM**  
- **Tokens per minute (with spikes)**: **{tpm_with_spikes:,.0f} TPM**  
- **Tokens per minute (final)**: **{tpm_needed:,} TPM**
"""
)

st.markdown("### What these numbers mean")
st.write(
    """
- **Parallelism** is the number of concurrent Inngest functions you can run on Vercel.  
- **Emails/hour** shows the throughput you can achieve with your available parallelism.  
- **Total latency per session** is the wall-clock time to process one complete email session.  
- **RPM** assumes one LLM call per Inngest function step. If your function makes multiple calls, multiply accordingly.  
- **TPM (raw)** is the base token throughput needed for steady-state traffic.  
- **TPM (with buffer)** adds headroom for variance and retries.  
- **TPM (with spikes)** accounts for traffic bursts and sudden load increases.  
- **TPM (final)** ensures at least the minimum tokens needed for one step.  
- **Safety buffer** accounts for variance and retries. **Spike scaler** handles traffic bursts.
"""
)

st.markdown("---")
st.markdown("### Additional Analysis")
st.write(
    f"""
**Sessions per hour per Inngest function**: {sessions_per_hour_per_function:,.2f}  
**Available parallelism**: {parallelism_input:,} concurrent Inngest functions  
**Target throughput**: {emails_per_hour_input:,} emails/hour  
**Safety buffer**: {safety_buffer}%  
**Spike scaler**: {spike_scaler}x  
**Minimum tokens per step**: {tokens_per_step:,}
"""
)

st.markdown("---")
st.caption("How to run: `pip install streamlit` then `streamlit run throughput_planner.py`")
