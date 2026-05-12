"""
Streamlit OTP Registration — multi-step UI
==========================================
Run standalone:   streamlit run frontend/otp_registration.py
Or import:        from frontend.otp_registration import show_otp_registration
"""

import time
import requests
import streamlit as st

API_BASE = "http://localhost:8001"


# ── Helpers ────────────────────────────────────────────────────────────────

def api_post(endpoint: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=15)
        if r.ok:
            return {"ok": True, "data": r.json()}
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "⚠️ Cannot connect to backend. Is the server running?"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Request timed out. Please try again."}


def ss(key: str, default=None):
    """Short alias for st.session_state with a default."""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def reset_otp_state():
    for k in ["reg_step", "reg_email", "reg_name", "reg_password",
              "reg_masked", "reg_expires", "reg_sent_at", "reg_token",
              "reg_user_id", "reg_full_name"]:
        if k in st.session_state:
            del st.session_state[k]


# ── Main component ─────────────────────────────────────────────────────────

def show_otp_registration():
    # Initialise session state
    ss("reg_step",     1)
    ss("reg_email",    "")
    ss("reg_name",     "")
    ss("reg_password", "")
    ss("reg_masked",   "")
    ss("reg_expires",  300)
    ss("reg_sent_at",  None)

    step = st.session_state.reg_step

    # ── STEP 1 — Registration form ─────────────────────────────────────────
    if step == 1:
        st.subheader("📝 Create Your Account")
        st.caption("Enter your details below. We'll send a 6-digit code to verify your email.")
        st.divider()

        with st.form("reg_form"):
            full_name = st.text_input("Full Name *", placeholder="Jane Doe")
            email     = st.text_input("Email Address *", placeholder="you@example.com")
            col1, col2 = st.columns(2)
            password  = col1.text_input("Password *", type="password", placeholder="Min 8 chars")
            confirm   = col2.text_input("Confirm Password *", type="password")

            st.caption("Password must be at least 8 characters with one uppercase letter and one digit.")
            submitted = st.form_submit_button("📨 Send Verification Code", use_container_width=True, type="primary")

        if submitted:
            errors = []
            if not full_name.strip():      errors.append("Full name is required.")
            if not email.strip():          errors.append("Email is required.")
            if len(password) < 8:          errors.append("Password must be at least 8 characters.")
            if not any(c.isupper() for c in password): errors.append("Password needs one uppercase letter.")
            if not any(c.isdigit() for c in password): errors.append("Password needs one digit.")
            if password != confirm:        errors.append("Passwords do not match.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                with st.spinner("Sending verification code…"):
                    res = api_post("/auth/send-otp", {"email": email.strip(), "purpose": "registration"})
                if res["ok"]:
                    d = res["data"]
                    st.session_state.reg_email    = email.strip()
                    st.session_state.reg_name     = full_name.strip()
                    st.session_state.reg_password = password
                    st.session_state.reg_masked   = d.get("masked_email", email)
                    st.session_state.reg_expires  = d.get("expires_in_seconds", 300)
                    st.session_state.reg_sent_at  = time.time()
                    st.session_state.reg_step     = 2
                    st.rerun()
                else:
                    st.error(f"❌ {res['error']}")

    # ── STEP 2 — OTP input ─────────────────────────────────────────────────
    elif step == 2:
        st.subheader("🔐 Verify Your Email")
        st.divider()

        masked = st.session_state.reg_masked
        st.success(f"✉️ A 6-digit code was sent to **{masked}**")

        # Countdown timer
        if st.session_state.reg_sent_at:
            elapsed   = time.time() - st.session_state.reg_sent_at
            remaining = max(0, int(st.session_state.reg_expires - elapsed))
            m, s = divmod(remaining, 60)
            if remaining > 0:
                st.info(f"⏱ Code expires in **{m:02d}:{s:02d}**")
            else:
                st.warning("⚠️ Your code has expired. Please request a new one using the Resend button below.")

        with st.form("otp_form"):
            otp = st.text_input(
                "Enter 6-Digit Code",
                max_chars=6,
                placeholder="e.g. 482193",
                help="Check your inbox (and spam folder) for the code.",
            )
            col1, col2 = st.columns(2)
            verify = col1.form_submit_button("✅ Verify & Create Account", use_container_width=True, type="primary")
            back   = col2.form_submit_button("← Back", use_container_width=True)

        if verify:
            if not otp.strip() or not otp.strip().isdigit() or len(otp.strip()) != 6:
                st.error("Please enter a valid 6-digit numeric code.")
            else:
                # Step A: verify OTP
                with st.spinner("Verifying code…"):
                    vres = api_post("/auth/verify-otp", {
                        "email":    st.session_state.reg_email,
                        "otp_code": otp.strip(),
                        "purpose":  "registration",
                    })

                if not vres["ok"]:
                    st.error(f"❌ {vres['error']}")
                else:
                    # Step B: create account
                    with st.spinner("Creating your account…"):
                        rres = api_post("/auth/register", {
                            "full_name": st.session_state.reg_name,
                            "email":     st.session_state.reg_email,
                            "password":  st.session_state.reg_password,
                            "otp_code":  otp.strip(),
                        })

                    if rres["ok"]:
                        d = rres["data"]
                        st.session_state.reg_token     = d.get("access_token")
                        st.session_state.reg_user_id   = d.get("user_id")
                        st.session_state.reg_full_name = d.get("full_name")
                        # ── Hook into your existing auth session ──────────
                        # st.session_state["token"]     = d.get("access_token")
                        # st.session_state["user_id"]   = d.get("user_id")
                        # st.session_state["logged_in"] = True
                        st.session_state.reg_step = 3
                        st.rerun()
                    else:
                        st.error(f"❌ {rres['error']}")

        if back:
            st.session_state.reg_step = 1
            st.rerun()

        # Resend (outside form)
        st.divider()
        st.caption("Didn't receive the code?")

        resend_disabled = False
        resend_label    = "🔄 Resend Code"
        if st.session_state.reg_sent_at:
            elapsed = time.time() - st.session_state.reg_sent_at
            if elapsed < 60:
                wait = int(60 - elapsed)
                resend_label    = f"⏳ Resend available in {wait}s"
                resend_disabled = True

        if st.button(resend_label, disabled=resend_disabled, use_container_width=True):
            with st.spinner("Resending…"):
                rr = api_post("/auth/send-otp", {
                    "email":   st.session_state.reg_email,
                    "purpose": "registration",
                })
            if rr["ok"]:
                d = rr["data"]
                st.session_state.reg_sent_at = time.time()
                st.session_state.reg_expires = d.get("expires_in_seconds", 300)
                st.session_state.reg_masked  = d.get("masked_email", st.session_state.reg_masked)
                st.success("✅ New code sent!")
                st.rerun()
            else:
                st.error(f"❌ {rr['error']}")

    # ── STEP 3 — Success ───────────────────────────────────────────────────
    elif step == 3:
        st.balloons()
        st.success("🎉 Account created successfully!")
        name = st.session_state.get("reg_full_name") or st.session_state.get("reg_name", "")
        st.markdown(f"### Welcome, **{name}**! 👋")
        st.markdown("Your email has been verified and your account is ready.")

        if st.session_state.get("reg_token"):
            st.info("You are now logged in. Your session token has been stored.")

        col1, col2 = st.columns(2)
        if col1.button("🏠 Go to Dashboard", use_container_width=True, type="primary"):
            reset_otp_state()
            st.rerun()
        if col2.button("👤 Register Another Account", use_container_width=True):
            reset_otp_state()
            st.rerun()


# ── Standalone run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    st.set_page_config(
        page_title="Create Account",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Header
    st.markdown("""
        <div style="text-align:center;padding:24px 0 8px">
            <span style="font-size:48px">🔐</span>
            <h1 style="font-size:28px;margin-top:8px">OTP System</h1>
            <p style="color:#666">Secure registration with email verification</p>
        </div>
    """, unsafe_allow_html=True)
    st.divider()

    show_otp_registration()
