"""
app.py  –  Streamlit front-end for the CV Management System
============================================================
Run with:  streamlit run app.py
"""

import base64
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ── Configuration ──────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="CV Management System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.main-header  { font-size:2.4rem; color:#1f77b4; text-align:center; margin-bottom:1.5rem; }
.section-header { font-size:1.4rem; color:#2e86ab; margin:1.2rem 0 0.8rem 0; }
.badge-green  { background:#d4edda; color:#155724; padding:2px 8px; border-radius:12px; font-size:.85rem; }
.badge-yellow { background:#fff3cd; color:#856404; padding:2px 8px; border-radius:12px; font-size:.85rem; }
hr { margin: 0.6rem 0; }
</style>
""",
    unsafe_allow_html=True,
)


# ── API wrapper ────────────────────────────────────────────────────────────
class CVManagerAPI:
    base = API_BASE_URL

    # -- health --
    def health_check(self) -> bool:
        try:
            return requests.get(f"{self.base}/health", timeout=3).status_code == 200
        except Exception:
            return False

    # -- categories --
    def get_categories(self):
        try:
            r = requests.get(f"{self.base}/categories/", timeout=10)
            return r.json() if r.ok else []
        except Exception:
            return []

    def create_category(self, name: str) -> bool:
        try:
            r = requests.post(f"{self.base}/categories/", json={"name": name}, timeout=10)
            return r.ok
        except Exception:
            return False

    # -- CVs --
    def upload_cv(self, file, category: str):
        try:
            r = requests.post(
                f"{self.base}/cvs/upload",
                files={"file": (file.name, file.getvalue(), "application/pdf")},
                data={"category": category},
                timeout=120,
            )
            if r.ok:
                return r.json()
            st.error(f"Upload failed ({r.status_code}): {r.text}")
            return None
        except Exception as e:
            st.error(f"Upload exception: {e}")
            return None

    def get_cvs(self, category: str):
        try:
            r = requests.get(f"{self.base}/cvs/", params={"category": category}, timeout=30)
            return r.json() if r.ok else []
        except Exception:
            return []

    def get_cv_pdf(self, cv_id: str, category: str):
        try:
            r = requests.get(
                f"{self.base}/cvs/{cv_id}/preview",
                params={"category": category},
                timeout=30,
            )
            return r.content if r.ok else None
        except Exception:
            return None

    def delete_cv(self, cv_id: str, category: str) -> bool:
        try:
            r = requests.delete(
                f"{self.base}/cvs/{cv_id}", params={"category": category}, timeout=30
            )
            return r.ok
        except Exception:
            return False

    # -- search --
    def search(self, category: str, job_desc: str, top_n: int, rerank: bool):
        try:
            r = requests.post(
                f"{self.base}/search/",
                json={
                    "job_description": job_desc,
                    "category": category,
                    "top_n": top_n,
                    "rerank": rerank,
                },
                timeout=120,
            )
            if r.ok:
                return r.json()
            st.error(f"Search error {r.status_code}: {r.text}")
            return []
        except Exception as e:
            st.error(f"Search exception: {e}")
            return []

    # -- email --
    def generate_email(self, candidate_id: str, job_desc: str, company: str, sender: str):
        if not candidate_id:
            return None
        try:
            r = requests.post(
                f"{self.base}/emails/generate",
                json={
                    "candidate_id": candidate_id,
                    "job_description": job_desc,
                    "company_name": company,
                    "sender_role": sender,
                },
                timeout=60,
            )
            if r.ok:
                return r.json().get("email_content")
            st.error(f"Email generation failed ({r.status_code}): {r.text}")
            return None
        except Exception as e:
            st.error(f"Email generation exception: {e}")
            return None

    def send_email(self, candidate_id: str, job_desc: str, company: str, sender: str) -> bool:
        if not candidate_id:
            return False
        try:
            r = requests.post(
                f"{self.base}/emails/send",
                json={
                    "candidate_id": candidate_id,
                    "job_description": job_desc,
                    "company_name": company,
                    "sender_role": sender,
                },
                timeout=60,
            )
            return r.ok
        except Exception:
            return False


api = CVManagerAPI()


# ── Helpers ────────────────────────────────────────────────────────────────
def _fmt_dt(ts) -> str:
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return "—"


def display_pdf(pdf_bytes: bytes, filename: str):
    b64 = base64.b64encode(pdf_bytes).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" '
        f'height="620px" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )
    st.download_button("📥 Download PDF", pdf_bytes, filename, mime="application/pdf")


def validation_badge(status: str) -> str:
    if status == "complete":
        return '<span class="badge-green">✅ Complete</span>'
    return '<span class="badge-yellow">⚠️ Incomplete</span>'


# ── Pages ──────────────────────────────────────────────────────────────────

def page_dashboard():
    st.markdown('<div class="main-header">📊 Dashboard</div>', unsafe_allow_html=True)

    status_ok = api.health_check()
    categories = api.get_categories() if status_ok else []
    total_cvs = sum(c.get("cv_count", 0) for c in categories)

    c1, c2, c3 = st.columns(3)
    c1.metric("Categories", len(categories))
    c2.metric("Total CVs", total_cvs)
    c3.metric("API", "✅ Online" if status_ok else "❌ Offline")

    if not status_ok:
        st.error("FastAPI backend is not reachable at " + API_BASE_URL)
        return

    st.markdown('<div class="section-header">📁 Categories</div>', unsafe_allow_html=True)
    if not categories:
        st.info("No categories yet — create one in **Manage Categories**.")
        return

    for cat in categories:
        with st.expander(f"📂 {cat['name']}  ({cat.get('cv_count', 0)} CVs)"):
            st.write(f"**Description:** {cat.get('description', '—')}")
            st.write(f"**Created:** {_fmt_dt(cat.get('created_at'))}")


def page_upload():
    st.markdown('<div class="main-header">📤 Upload CV</div>', unsafe_allow_html=True)
    categories = api.get_categories()
    cat_names  = [c["name"] for c in categories]

    col_left, col_right = st.columns(2)

    with col_left:
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

        if cat_names:
            selected_cat = st.selectbox("Existing category", cat_names)
            create_new   = st.checkbox("Create new category instead")
            if create_new:
                new_cat  = st.text_input("New category name")
                category = new_cat.strip() if new_cat.strip() else selected_cat
            else:
                category = selected_cat
        else:
            st.info("No categories yet — enter a name to create one.")
            category   = st.text_input("New category name")
            create_new = True

        if st.button("⬆️ Upload", type="primary"):
            if not uploaded_file:
                st.warning("Please choose a PDF file first.")
            elif not category:
                st.warning("Please provide a category name.")
            else:
                if create_new and category not in cat_names:
                    if not api.create_category(category):
                        st.error("Failed to create category.")
                        st.stop()
                with st.spinner("Processing CV — this may take ~30 s…"):
                    result = api.upload_cv(uploaded_file, category)
                if result:
                    st.success("✅ CV uploaded and indexed!")
                    meta = result.get("metadata", {})
                    st.json(
                        {
                            "Name":       meta.get("name"),
                            "Email":      meta.get("email"),
                            "Experience": f"{meta.get('experience_years', 0)} years",
                            "Skills":     meta.get("skills", []),
                            "Status":     meta.get("validation_status"),
                            "ID":         result.get("id"),
                        }
                    )

    with col_right:
        st.markdown('<div class="section-header">Recently uploaded</div>', unsafe_allow_html=True)
        if cat_names:
            show_cat = st.selectbox("Show from", cat_names, key="recent_cat")
            cvs = api.get_cvs(show_cat)
            if cvs:
                for cv in cvs[:8]:
                    meta = cv.get("metadata", {})
                    st.write(f"**{cv['filename']}**  `{cv['id'][:8]}…`")
                    st.caption(
                        f"👤 {meta.get('name', '—')}  |  "
                        f"📧 {meta.get('email', '—')}  |  "
                        f"🕐 {_fmt_dt(cv.get('uploaded_at'))}"
                    )
                    st.markdown("---")
            else:
                st.info("No CVs in this category.")


def page_search():
    st.markdown('<div class="main-header">🔍 Search Candidates</div>', unsafe_allow_html=True)
    categories = api.get_categories()
    if not categories:
        st.warning("No categories available. Upload some CVs first.")
        return

    with st.form("search_form"):
        col_a, col_b = st.columns([1, 2])
        with col_a:
            category = st.selectbox("Category", [c["name"] for c in categories])
            top_n    = st.slider("Results to return", 1, 20, 5)
            rerank   = st.checkbox("LLM reranking (slower, smarter)", value=False)
        with col_b:
            job_desc = st.text_area(
                "Job Description",
                height=220,
                placeholder="e.g., Looking for a senior Python developer with FastAPI and ML experience…",
            )
        submitted = st.form_submit_button("🔍 Search", type="primary")

    if submitted:
        if not job_desc.strip():
            st.warning("Please enter a job description.")
        else:
            with st.spinner("Searching…"):
                results = api.search(category, job_desc, top_n, rerank)
            if results:
                st.session_state["search_results"] = results
                st.session_state["search_job_desc"] = job_desc
            else:
                st.warning("No candidates found — try broadening the job description.")
                st.session_state.pop("search_results", None)

    if "search_results" not in st.session_state:
        st.info("Enter a job description above and click **Search**.")
        return

    results  = st.session_state["search_results"]
    job_desc = st.session_state.get("search_job_desc", "")
    st.success(f"Found **{len(results)}** candidate(s)")

    # ── Summary table ────────────────────────────────────────────────────
    df = pd.DataFrame(results)[
        ["rank", "name", "email", "phone", "similarity_score", "validation_status", "candidate_id"]
    ]
    df.columns = ["Rank", "Name", "Email", "Phone", "Score", "Status", "ID"]
    df["Score"]  = df["Score"].map("{:.3f}".format)
    df["ID"]     = df["ID"].str[:12] + "…"
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Bulk email ───────────────────────────────────────────────────────
    with st.expander("📧 Bulk email (all candidates with valid e-mail)", expanded=False):
        bulk_company = st.text_input("Company name", "Our Company", key="bulk_co")
        bulk_sender  = st.text_input("Sender role",  "HR Manager",  key="bulk_sr")
        if st.button("Send bulk emails"):
            if not job_desc:
                st.error("Job description missing — please search again.")
            else:
                sent = failed = skipped = 0
                prog = st.progress(0)
                for idx_b, cand in enumerate(results):
                    prog.progress((idx_b + 1) / len(results))
                    cid = cand.get("candidate_id", "")
                    if not cid:
                        skipped += 1
                        continue
                    email = cand.get("email", "")
                    if not email or email == "Not provided":
                        skipped += 1
                        continue
                    if api.send_email(cid, job_desc, bulk_company, bulk_sender):
                        sent += 1
                    else:
                        failed += 1
                    time.sleep(0.3)
                st.success(f"Sent: {sent}  |  Failed: {failed}  |  Skipped (no e-mail): {skipped}")

    # ── Candidate cards ──────────────────────────────────────────────────
    st.markdown("### 👤 Candidate details")
    for i, cand in enumerate(results):
        cid = cand.get("candidate_id", "")
        with st.container():
            st.markdown(f"#### #{cand['rank']} — {cand['name']}")
            col_x, col_y, col_z = st.columns([1, 1, 2])
            with col_x:
                st.write(f"📧 {cand['email']}")
                st.write(f"📞 {cand.get('phone', '—')}")
            with col_y:
                st.write(f"🎯 Score: **{cand['similarity_score']:.3f}**")
                status = cand.get("validation_status", "incomplete")
                st.markdown(validation_badge(status), unsafe_allow_html=True)
            with col_z:
                st.write(cand["summary"][:300] + "…")

            with st.expander(f"✉️ Email {cand['name']}"):
                if not cid:
                    st.error(
                        "⚠️ candidate_id is missing for this result. "
                        "Re-upload the CV to regenerate the index entry."
                    )
                else:
                    cand_jd      = st.text_area("Job description", job_desc, key=f"jd_{i}")
                    cand_company = st.text_input("Company",   "Our Company", key=f"co_{i}")
                    cand_sender  = st.text_input("Sender",    "HR Manager",  key=f"sr_{i}")

                    col_gen, col_send = st.columns(2)
                    with col_gen:
                        if st.button("📝 Preview email", key=f"preview_{i}"):
                            with st.spinner("Generating…"):
                                html = api.generate_email(cid, cand_jd, cand_company, cand_sender)
                            if html:
                                st.session_state[f"email_html_{i}"] = html
                            else:
                                st.error("Generation failed — check API logs.")
                    with col_send:
                        if st.button("📨 Generate & Send", key=f"send_{i}"):
                            with st.spinner("Generating & sending…"):
                                html = api.generate_email(cid, cand_jd, cand_company, cand_sender)
                            if html:
                                if api.send_email(cid, cand_jd, cand_company, cand_sender):
                                    st.success("✅ Email sent!")
                                else:
                                    st.error("Generation succeeded but SMTP send failed.")
                            else:
                                st.error("Email generation failed.")

                    if f"email_html_{i}" in st.session_state:
                        st.markdown("**Preview:**")
                        st.components.v1.html(
                            st.session_state[f"email_html_{i}"], height=280, scrolling=True
                        )

            st.markdown("---")


def page_preview():
    st.markdown('<div class="main-header">👁️ Preview CVs</div>', unsafe_allow_html=True)
    categories = api.get_categories()
    if not categories:
        st.warning("No categories found.")
        return

    col_left, col_right = st.columns([1, 2])
    with col_left:
        category = st.selectbox("Category", [c["name"] for c in categories])
        cvs = api.get_cvs(category)
        if not cvs:
            st.info("No CVs in this category.")
            return

        cv_options = {f"{cv['filename']}  ({cv['id'][:8]}…)": cv for cv in cvs}
        selected   = st.selectbox("Select CV", list(cv_options.keys()))
        cv         = cv_options[selected]
        meta       = cv.get("metadata", {})

        st.write(f"**Uploaded:** {_fmt_dt(cv.get('uploaded_at'))}")
        st.write(f"**Name:** {meta.get('name', '—')}")
        st.write(f"**Email:** {meta.get('email', '—')}")
        st.write(f"**Experience:** {meta.get('experience_years', 0)} years")
        if meta.get("skills"):
            st.write("**Skills:** " + ", ".join(meta["skills"][:10]))
        st.write(f"**ID:** `{cv['id']}`")

        if st.button("🗑️ Delete CV", type="secondary"):
            if api.delete_cv(cv["id"], category):
                st.success("Deleted.")
                st.rerun()
            else:
                st.error("Delete failed.")

    with col_right:
        pdf_data = api.get_cv_pdf(cv["id"], category)
        if pdf_data:
            display_pdf(pdf_data, cv["filename"])
        else:
            st.error("Could not load PDF preview.")


def page_categories():
    st.markdown('<div class="main-header">📁 Manage Categories</div>', unsafe_allow_html=True)
    col_left, col_right = st.columns(2)

    with col_left:
        with st.form("new_cat_form"):
            new_name  = st.text_input("Category name")
            submitted = st.form_submit_button("➕ Create")
            if submitted:
                if not new_name.strip():
                    st.warning("Name cannot be empty.")
                elif api.create_category(new_name.strip()):
                    st.success(f"Category '{new_name.strip()}' created.")
                    st.rerun()
                else:
                    st.error("Could not create (it may already exist).")

    with col_right:
        st.subheader("Existing categories")
        cats = api.get_categories()
        if cats:
            for cat in cats:
                st.write(f"**{cat['name']}** — {cat.get('cv_count', 0)} CVs")
                st.caption(f"Created: {_fmt_dt(cat.get('created_at'))}")
                st.markdown("---")
        else:
            st.info("No categories yet.")


def page_email_tester():
    st.markdown('<div class="main-header">✉️ Email Tester</div>', unsafe_allow_html=True)
    categories = api.get_categories()
    if not categories:
        st.warning("No categories found.")
        return

    category = st.selectbox("Category", [c["name"] for c in categories])
    cvs = api.get_cvs(category)
    if not cvs:
        st.info("No CVs in this category.")
        return

    candidate_map = {}
    for cv in cvs:
        name  = cv.get("metadata", {}).get("name", "Unknown")
        cid   = cv["id"]
        label = f"{name}  ({cid[:8]}…)"
        candidate_map[label] = cid

    selected = st.selectbox("Candidate", list(candidate_map.keys()))
    cand_id  = candidate_map[selected]

    st.caption(f"Candidate ID: `{cand_id}`")

    job_desc = st.text_area("Job description", height=150)
    company  = st.text_input("Company name", "Our Company")
    sender   = st.text_input("Sender role",  "HR Manager")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📝 Generate preview"):
            if not job_desc.strip():
                st.warning("Enter a job description first.")
            else:
                with st.spinner("Generating…"):
                    html = api.generate_email(cand_id, job_desc, company, sender)
                if html:
                    st.session_state["tester_email_html"] = html
                else:
                    st.error("Generation failed.")

    with col_b:
        if st.button("📨 Send now"):
            if not job_desc.strip():
                st.warning("Enter a job description first.")
            elif api.send_email(cand_id, job_desc, company, sender):
                st.success("Email sent!")
            else:
                st.error("Send failed — check SMTP settings and API logs.")

    if "tester_email_html" in st.session_state:
        st.markdown("### Generated Email")
        st.components.v1.html(
            st.session_state["tester_email_html"], height=450, scrolling=True
        )


# ── Navigation ─────────────────────────────────────────────────────────────
def main():
    if not api.health_check():
        st.error(
            "⚠️ FastAPI backend is offline.  "
            "Start it with:  `uvicorn app.main:app --reload`"
        )
        return

    st.sidebar.title("📄 CV Manager")
    pages = {
        "📊 Dashboard":          page_dashboard,
        "📤 Upload CV":          page_upload,
        "🔍 Search Candidates":  page_search,
        "👁️ Preview CVs":        page_preview,
        "📁 Manage Categories":  page_categories,
        "✉️ Email Tester":       page_email_tester,
    }
    choice = st.sidebar.radio("Navigation", list(pages.keys()))
    pages[choice]()


if __name__ == "__main__":
    main()