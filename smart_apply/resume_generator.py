"""
Phase 4 — JD-tailored, ATS-aligned resume generation.

Takes the user's real "reference resume" data (resume_data.yaml) plus the
scraped job description, asks Groq to reword/reorder the summary, skills,
and experience bullets to match the JD — without inventing new employers,
titles, dates, or skills. Renders the result to a real, text-selectable PDF
via a Jinja2 HTML template + WeasyPrint.

Every failure mode here degrades to returning None; callers must fall back
to the existing static resume flow (see smart_apply/resume_uploader.py).

Requires: pip install Jinja2 WeasyPrint
Set GROQ_API_KEY in environment or .env file (shared with groq_tailorer.py).
"""

import json
import os
from typing import Dict, List, Optional

import yaml

import config

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from jinja2 import Environment, FileSystemLoader
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

_warned_unavailable = False

RESUME_DATA_FILE = "resume_data.yaml"
PROFILE_DATA_FILE = "profile_data.yaml"
TEMPLATE_DIR = "resume_templates"
TEMPLATE_NAME = "default.html.jinja"

TAILOR_MODEL = "llama3-70b-8192"


def _get_client() -> Optional[object]:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or not GROQ_AVAILABLE:
        return None
    return Groq(api_key=api_key)


def _load_yaml(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _first_present(profile: Dict, keys: List[str]) -> str:
    for key in keys:
        val = profile.get(key)
        if val:
            return str(val)
    return ""


def _tailor_resume_content(resume_data: Dict, master_skills: List[str], jd_text: str) -> Optional[Dict]:
    """
    Asks Groq to reword/reorder the summary, skills, and experience bullets to
    match the JD. Returns None on any failure — caller falls back to resume_data as-is.
    """
    client = _get_client()
    if not client:
        return None

    summary = resume_data.get("summary", "")
    experience = resume_data.get("experience", [])
    if not summary or not experience:
        return None

    experience_for_prompt = [
        {"company": job.get("company", ""), "bullets": job.get("bullets", [])}
        for job in experience
        if job.get("company")
    ]

    prompt = (
        "You are tailoring a real resume to a job description. Do NOT invent facts.\n"
        "Rules:\n"
        f"- skills: choose ONLY from this exact list, reorder/filter for JD relevance, "
        f"do not add new items: {json.dumps(master_skills)}\n"
        "- summary: rewrite the reference summary below in 2-4 sentences, same factual "
        "claims, aligned to the job description's language.\n"
        "- experience: for each company, reword/reorder the given bullets for JD relevance. "
        "Do not add companies, titles, dates, or claims not present in the input bullets.\n"
        "Reply with ONLY valid JSON matching this schema, no markdown fences, no explanation:\n"
        '{"summary": "...", "skills": ["..."], "experience": '
        '[{"company": "...", "bullets": ["...", "..."]}]}\n\n'
        f"REFERENCE SUMMARY: {summary}\n\n"
        f"EXPERIENCE: {json.dumps(experience_for_prompt)}\n\n"
        f"JOB DESCRIPTION: {jd_text[:3000]}"
    )

    try:
        response = client.chat.completions.create(
            model=TAILOR_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
    except Exception:
        return None

    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        parsed = json.loads(content)
    except Exception:
        return None

    tailored_summary = parsed.get("summary", "").strip()
    if not tailored_summary:
        return None

    master_skills_set = {s.lower() for s in master_skills}
    tailored_skills = [
        s for s in parsed.get("skills", [])
        if isinstance(s, str) and s.lower() in master_skills_set
    ]
    if not tailored_skills:
        return None

    original_companies = {job.get("company", "") for job in experience if job.get("company")}
    tailored_experience_by_company = {
        item.get("company", ""): item.get("bullets", [])
        for item in parsed.get("experience", [])
        if isinstance(item, dict) and item.get("company") in original_companies
    }

    final_experience = []
    for job in experience:
        company = job.get("company", "")
        bullets = tailored_experience_by_company.get(company)
        if not bullets or not isinstance(bullets, list):
            bullets = job.get("bullets", [])
        final_experience.append({**job, "bullets": bullets})

    return {
        "summary": tailored_summary,
        "skills": tailored_skills,
        "experience": final_experience,
    }


def generate_tailored_resume_pdf(jd_text: str, output_path: str) -> Optional[str]:
    """
    Loads resume_data.yaml + config.mySkills + profile_data.yaml, tailors content
    via Groq (or falls back to the untailored reference resume on any failure),
    renders the resume template, converts to PDF via WeasyPrint, writes output_path.

    Returns output_path on success, None on any failure — caller must fall back
    to the existing static resume upload flow.
    """
    global _warned_unavailable

    if not WEASYPRINT_AVAILABLE:
        if not _warned_unavailable:
            print(
                "⚠️ AI resume generation is enabled but Jinja2/WeasyPrint are not "
                "available (pip install Jinja2 WeasyPrint, plus WeasyPrint's native "
                "libraries). Falling back to your static resume for this run."
            )
            _warned_unavailable = True
        return None

    resume_data = _load_yaml(RESUME_DATA_FILE)
    if not resume_data.get("summary") or not resume_data.get("experience"):
        return None

    profile = _load_yaml(PROFILE_DATA_FILE)
    master_skills = getattr(config, "mySkills", [])

    tailored = None
    if jd_text and master_skills:
        try:
            tailored = _tailor_resume_content(resume_data, master_skills, jd_text)
        except Exception:
            tailored = None

    if tailored:
        summary = tailored["summary"]
        skills = tailored["skills"]
        experience = tailored["experience"]
    else:
        summary = resume_data.get("summary", "")
        skills = master_skills
        experience = resume_data.get("experience", [])

    full_name = _first_present(profile, ["full name"]) or " ".join(
        filter(None, [_first_present(profile, ["first name"]), _first_present(profile, ["last name"])])
    )

    context = {
        "full_name": full_name or "Your Name",
        "email": _first_present(profile, ["email"]),
        "phone": _first_present(profile, ["phone", "phone number", "mobile"]),
        "location": _first_present(profile, ["location", "current location", "city"]),
        "linkedin": _first_present(profile, ["linkedin", "linkedin profile"]),
        "summary": summary,
        "skills": skills,
        "experience": experience,
        "education": resume_data.get("education", []),
    }

    try:
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(TEMPLATE_NAME)
        html_content = template.render(**context)
    except Exception:
        return None

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        HTML(string=html_content).write_pdf(output_path)
    except Exception:
        return None

    return output_path
