import math
import streamlit as st

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
    st.caption("Tip: Safety buffer accounts for variance, retries, and spikes.")

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
tpm_needed = math.ceil(tpm_raw)

# Also show RPM if one LLM request per step
rpm_raw = steps_per_min
rpm_needed = math.ceil(rpm_raw)

# Total latency per session
total_latency_per_session = S * T

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

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Required parallelism", f"{required_parallelism_with_buffer:,}", help="Parallelism needed for target throughput")
with c2:
    st.metric("Tokens per minute needed", f"{tpm_needed:,} TPM")
with c3:
    st.metric("Total latency per session", f"{total_latency_per_session:.1f}s", help="Total time to process one email session")

st.markdown("---")
st.markdown("### API Rate Planning")
st.write(
    f"""
- **Steps per minute**: **{steps_per_min:,.2f}**  
- **Requests per minute (1 request/step)**: **{rpm_needed:,} RPM**  
- **Tokens per minute**: **{tpm_needed:,} TPM**
"""
)

st.markdown("### What these numbers mean")
st.write(
    """
- **Parallelism** is the number of concurrent Inngest functions you can run on Vercel.  
- **Emails/hour** shows the throughput you can achieve with your available parallelism.  
- **Total latency per session** is the wall-clock time to process one complete email session.  
- **RPM** assumes one LLM call per Inngest function step. If your function makes multiple calls, multiply accordingly.  
- **TPM** is aggregate token throughput needed across the API tenant/project.  
- **Safety buffer** accounts for variance, retries, and short spikes.
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
"""
)

st.markdown("---")
st.caption("How to run: `pip install streamlit` then `streamlit run throughput_planner.py`")
