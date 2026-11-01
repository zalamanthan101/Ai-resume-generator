"""
AI utilities for resume generation, optimization, and skill extraction.
Supports Groq, OpenAI, and Google Gemini APIs.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional


ATS_SUMMARY_PROMPT_TEMPLATE = """You are an expert resume writer.
Write a professional ATS-friendly resume summary.
Guidelines:
- Maximum 3 to 4 sentences only
- Use clear professional language
- Include important keywords from the skills
- Avoid first person words like "I" or "my"
- Focus on strengths, technologies, and career goals
- Make it suitable for recruiters and ATS systems
- Do NOT use markdown (no **bold**, no *italics*, no bullets)
Input:
Job Title: {job_title}
Years of Experience: {experience}
Skills: {skills}
Output:
Write a concise professional summary suitable for a resume."""

ATS_PROJECT_PROMPT_TEMPLATE = """You are a professional resume writer.
Write an ATS-friendly project description for a resume.
Guidelines:
- Exactly 2 bullet points (one per line)
- Each line should start with an action verb
- Highlight technologies used
- Focus on functionality, impact, and technical implementation
- Use simple ATS-friendly wording
- Do NOT use markdown (no **bold**, no *italics*, no backticks)
- Do NOT include headings, role names, company names, or extra commentary
- Do NOT prefix with bullets like •, -, *, or numbering
Input:
Project Name: {project_name}
Technologies Used: {technologies}
Project Details: {project_details}

Output:
Return ONLY the bullet point lines."""

ATS_EXPERIENCE_PROMPT_TEMPLATE = """You are an expert resume writer.
Write ATS-friendly work experience bullet points.
Guidelines:
- Exactly 2 bullet points (one per line)
- Each line should start with an action verb
- Focus on responsibilities and achievements
- Mention tools, technologies, and measurable results if possible
- Use clear and simple ATS-friendly wording
- Do NOT use markdown (no **bold**, no *italics*, no backticks)
- Do NOT include headings, job titles, company names, or extra commentary
- Do NOT prefix with bullets like •, -, *, or numbering
Input:
Job Title: {job_title}
Company Type or Industry: {company_type}
Technologies Used: {technologies}
Responsibilities: {responsibilities}
Output:
Return ONLY the bullet point lines."""


def get_ai_provider():
    """Determine which AI provider to use based on environment variables."""
    forced = (os.getenv('AI_PROVIDER') or '').strip().lower()
    if forced:
        if forced not in {'groq', 'openai', 'gemini'}:
            raise ValueError("Invalid AI_PROVIDER. Use one of: groq, openai, gemini")
        if forced == 'groq' and not os.getenv('GROQ_API_KEY'):
            raise ValueError("AI_PROVIDER=groq but GROQ_API_KEY is not set")
        if forced == 'openai' and not os.getenv('OPENAI_API_KEY'):
            raise ValueError("AI_PROVIDER=openai but OPENAI_API_KEY is not set")
        if forced == 'gemini' and not os.getenv('GOOGLE_API_KEY'):
            raise ValueError("AI_PROVIDER=gemini but GOOGLE_API_KEY is not set")
        return forced

    if os.getenv('GROQ_API_KEY'):
        return 'groq'
    if os.getenv('OPENAI_API_KEY'):
        return 'openai'
    if os.getenv('GOOGLE_API_KEY'):
        return 'gemini'
    raise ValueError("No AI API key configured. Set GROQ_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY in .env")


def _strip_code_fences(text: str) -> str:
    text = (text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _strip_markdown_emphasis(text: str) -> str:
    """Remove common markdown emphasis tokens while preserving the text."""
    value = (text or '').strip()
    if not value:
        return ''

    # Inline code
    value = value.replace('`', '')

    # Bold/italic: **text**, __text__, *text*, _text_
    value = re.sub(r'(\*\*|__)(.+?)\1', r'\2', value)
    value = re.sub(r'(\*|_)([^*_]+?)\1', r'\2', value)

    # Remove any leftover emphasis markers that often slip through.
    value = value.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
    return value.strip()


def _normalize_resume_lines(
    text: str,
    max_items: Optional[int] = None,
    banned_lines: Optional[List[str]] = None,
) -> str:
    """
    Normalize AI output into resume-ready lines:
    - one item per line
    - no bullet symbols / numbering
    - no markdown emphasis
    """
    banned_norm = {
        re.sub(r'[^a-z0-9]+', '', (item or '').strip().lower())
        for item in (banned_lines or [])
        if (item or '').strip()
    }

    value = _strip_code_fences(text or '')
    # If the model returns inline bullets, split them into lines first.
    value = re.sub(r'\s*•\s*', '\n• ', value)
    value = re.sub(r'\s*(\d+[.)])\s*', r'\n\1 ', value)
    raw_lines = [ln.strip() for ln in value.splitlines()]
    lines: List[str] = []
    for line in raw_lines:
        if not line:
            continue
        if line.lower().startswith(('bullet', 'bullets', 'output', 'here are', 'example')):
            continue

        # Remove list prefixes (•, -, *, 1., 1), etc.)
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip()
        line = _strip_markdown_emphasis(line)
        if not line:
            continue

        normalized = re.sub(r'[^a-z0-9]+', '', line.lower())
        if normalized in banned_norm:
            continue

        # Keep lines ATS-friendly and sentence-like.
        if len(line) > 200:
            line = line[:197].rstrip() + '...'
        if line and line[-1] not in {'.', '!', '?'}:
            line = f"{line}."

        lines.append(line)
        if max_items and len(lines) >= max_items:
            break
    return "\n".join(lines).strip()


def _normalize_bullets(text: str, max_items: Optional[int] = None) -> str:
    """Ensure one bullet per line and each line starts with '• '."""
    raw_lines = [ln.strip() for ln in (text or '').splitlines()]
    lines: List[str] = []
    for line in raw_lines:
        if not line:
            continue
        if line.lower().startswith(('bullet', 'bullets', 'output', 'here are')):
            continue
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip()
        if not line:
            continue
        lines.append(f"• {line}")
        if max_items and len(lines) >= max_items:
            break
    return "\n".join(lines).strip()


def _generate_text(prompt: str, *, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    provider = get_ai_provider()
    if provider == 'openai':
        return _generate_with_openai(prompt, temperature=temperature, max_tokens=max_tokens)
    if provider == 'gemini':
        return _generate_with_gemini(prompt, temperature=temperature, max_tokens=max_tokens)
    return _generate_with_groq(prompt, temperature=temperature, max_tokens=max_tokens)


def generate_ats_resume_summary(job_title: str, experience: str, skills: str, user_prompt: str = "") -> str:
    prompt = ATS_SUMMARY_PROMPT_TEMPLATE.format(
        job_title=(job_title or '').strip(),
        experience=(experience or '').strip(),
        skills=(skills or '').strip(),
    )
    extra = (user_prompt or '').strip()
    if extra:
        prompt = f"{prompt}\n\nAdditional user instructions (optional; follow only if truthful/relevant):\n{extra}"
    raw = _generate_text(prompt).strip()
    cleaned = _strip_markdown_emphasis(raw)
    cleaned = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', cleaned).strip()
    cleaned = re.sub(r'\s*\n+\s*', ' ', cleaned).strip()
    return cleaned


def generate_ats_project_bullets(
    project_name: str,
    technologies: str,
    project_details: str,
    bullet_count: int = 3,
    user_prompt: str = "",
) -> str:
    bullet_count = max(2, min(int(bullet_count or 3), 4))
    prompt = ATS_PROJECT_PROMPT_TEMPLATE.format(
        project_name=(project_name or '').strip(),
        technologies=(technologies or '').strip(),
        project_details=(project_details or '').strip(),
    )
    extra = (user_prompt or '').strip()
    if extra:
        prompt = f"{prompt}\n\nAdditional user instructions (optional; follow only if truthful/relevant):\n{extra}"
    # The prompt asks for 3-4 lines; clip for consistent UX.
    return _normalize_resume_lines(
        _generate_text(prompt),
        max_items=bullet_count,
        banned_lines=[project_name],
    )


def generate_ats_experience_bullets(
    job_title: str,
    company_type: str,
    technologies: str,
    responsibilities: str,
    bullet_count: int = 3,
    user_prompt: str = "",
) -> str:
    bullet_count = max(2, min(int(bullet_count or 3), 4))
    prompt = ATS_EXPERIENCE_PROMPT_TEMPLATE.format(
        job_title=(job_title or '').strip(),
        company_type=(company_type or '').strip() or 'Not provided',
        technologies=(technologies or '').strip(),
        responsibilities=(responsibilities or '').strip(),
    )
    extra = (user_prompt or '').strip()
    if extra:
        prompt = f"{prompt}\n\nAdditional user instructions (optional; follow only if truthful/relevant):\n{extra}"
    # Prompt asks for 3-4 lines; clip for consistent UX.
    return _normalize_resume_lines(
        _generate_text(prompt),
        max_items=bullet_count,
        banned_lines=[job_title, company_type],
    )


def generate_bullet_points(
    job_title: str,
    skills: List[str],
    num_bullets: int = 3,
    kind: str = "experience",
    context: str = "",
    target_job_description: str = "",
    keywords: Optional[List[str]] = None,
) -> str:
    """
    Generate professional bullet points for a job role using AI.
    
    Args:
        job_title: The job title or role
        skills: List of relevant skills
        num_bullets: Number of bullet points to generate
    
    Returns:
        String with bullet points (one per line, formatted with •)
    """
    provider = get_ai_provider()
    
    skills_text = ", ".join(skills) if skills else "relevant technical skills"
    kind = (kind or "experience").strip().lower()
    if kind not in {"experience", "project"}:
        kind = "experience"

    keywords_text = ", ".join([k.strip() for k in (keywords or []) if k and str(k).strip()])
    keywords_block = f"\nATS keywords to incorporate (only if truthful/relevant): {keywords_text}" if keywords_text else ""
    context_block = f"\nContext (use only what is provided; do not invent facts):\n{context.strip()}" if context.strip() else ""
    jd_block = f"\nTarget job description (optional; use as keyword guidance):\n{target_job_description.strip()}" if target_job_description.strip() else ""

    subject = "work experience" if kind == "experience" else "project"
    prompt = f"""You are an expert resume writer. Generate {num_bullets} ATS-friendly resume bullet points for a {subject} for someone targeting a {job_title} role.
Use action verbs, include relevant tools/tech (from: {skills_text}), and include metrics only when supported by the context.
Avoid first-person pronouns. Keep each bullet to one sentence and one line.
Format: each line must start with • and contain no extra commentary.{keywords_block}{context_block}{jd_block}
Return only the bullet lines."""

    if provider == 'openai':
        return _normalize_bullets(_generate_with_openai(prompt), max_items=num_bullets)
    if provider == 'gemini':
        return _normalize_bullets(_generate_with_gemini(prompt), max_items=num_bullets)
    return _normalize_bullets(_generate_with_groq(prompt), max_items=num_bullets)


def optimize_resume_content(resume_text: str, job_description: str = "") -> str:
    """
    Optimize resume content for ATS (Applicant Tracking System) and readability.
    
    Args:
        resume_text: The current resume content
        job_description: Optional job description to tailor content
    
    Returns:
        Optimized resume text
    """
    provider = get_ai_provider()
    
    job_context = f"\nJob Description:\n{job_description}" if job_description else ""
    prompt = f"""Optimize the following resume content for ATS systems and readability:

{resume_text}
{job_context}

Please:
1. Use strong action verbs and industry-specific keywords
2. Ensure proper formatting and spacing
3. Enhance clarity and professionalism
4. Add quantifiable metrics where possible
5. Remove redundancy
6. Keep the same overall structure but improve quality

Return only the optimized resume content, nothing else."""

    if provider == 'openai':
        return _generate_with_openai(prompt)
    if provider == 'gemini':
        return _generate_with_gemini(prompt)
    return _generate_with_groq(prompt)


def extract_skills(job_description: str, category: str = "technical") -> List[str]:
    """
    Extract skills from a job description.
    
    Args:
        job_description: The job description text
        category: Type of skills to extract ('technical', 'soft', or 'all')
    
    Returns:
        List of extracted skills
    """
    provider = get_ai_provider()
    
    category_instruction = {
        "technical": "technical and programming skills",
        "soft": "soft skills and competencies",
        "all": "both technical and soft skills"
    }.get(category, "both technical and soft skills")
    
    prompt = f"""Extract {category_instruction} from the following job description. 
Return only a JSON array of skills (strings), with no additional text.
Example format: ["Python", "Machine Learning", "Communication", "Project Management"]

Job Description:
{job_description}

Return only the JSON array."""

    if provider == 'openai':
        response = _generate_with_openai(prompt)
    elif provider == 'gemini':
        response = _generate_with_gemini(prompt)
    else:
        response = _generate_with_groq(prompt)
     
    try:
        # Try to parse JSON response
        response = _strip_code_fences(response)
        skills = json.loads(response)
        if isinstance(skills, list):
            return [str(s).strip() for s in skills if s]
    except (json.JSONDecodeError, TypeError):
        # Fall back to simple parsing if JSON fails
        skills = [s.strip(' "\'[],-') for s in response.split('\n') if s.strip()]
        return [s for s in skills if s and len(s) > 1]
    
    return []


def generate_profile_summary(name: str, job_title: str, years_experience: int, skills: List[str]) -> str:
    """
    Generate a professional profile summary for the top of a resume.
    
    Args:
        name: Person's name
        job_title: Target job title or field
        years_experience: Years of professional experience
        skills: Key skills
    
    Returns:
        Professional summary text
    """
    provider = get_ai_provider()
    
    skills_text = ", ".join(skills) if skills else "relevant skills"
    prompt = f"""Write a professional 2-3 sentence resume summary for:
Name: {name}
Target Role: {job_title}
Years of Experience: {years_experience}
Key Skills: {skills_text}

Make it compelling, concise, and tailored to the {job_title} field.
Use active voice and strong action verbs.
Return only the summary text, nothing else."""

    if provider == 'openai':
        return _generate_with_openai(prompt)
    if provider == 'gemini':
        return _generate_with_gemini(prompt)
    return _generate_with_groq(prompt)


def summarize_text(text: str, kind: str = "general", max_sentences: int = 2) -> str:
    """
    Summarize a block of text into a resume-friendly 1-2 sentence summary.

    Args:
        text: Source text to summarize (project/experience/raw notes)
        kind: 'project', 'experience', or 'general'
        max_sentences: Clamp to 1-4 sentences

    Returns:
        Summary text (no bullets unless present in the input)
    """
    provider = get_ai_provider()
    kind = (kind or "general").strip().lower()
    if kind not in {"project", "experience", "general"}:
        kind = "general"
    max_sentences = max(1, min(int(max_sentences or 2), 4))

    prompt = f"""Summarize the following {kind} text into {max_sentences} concise sentence(s) suitable for a resume.
Do not invent facts. Keep it ATS-friendly with relevant keywords from the text. Avoid first-person pronouns.
Return only the summary sentence(s), nothing else.

Text:
{text.strip()}"""

    if provider == 'openai':
        return _generate_with_openai(prompt)
    if provider == 'gemini':
        return _generate_with_gemini(prompt)
    return _generate_with_groq(prompt)


def organize_technical_skills(technical_skills: str, user_prompt: str = "") -> str:
    """
    Convert a flat technical skills list into ATS-friendly categorized lines:
    Languages: ...
    Frameworks: ...
    Libraries: ...
    Databases: ...
    Tools: ...
    Concepts: ...
    """
    provider = get_ai_provider()
    skills = (technical_skills or '').strip()
    if not skills:
        return ""

    extra = (user_prompt or '').strip()
    extra_text = f"\nExtra instructions: {extra}\n" if extra else ""

    prompt = f"""Organize the following technical skills into a clean, ATS-friendly categorized format.

Input skills (may be comma-separated or mixed text):
{skills}
{extra_text}
Rules:
- Output ONLY plain text lines, no bullets, no numbering, no markdown.
- Each line MUST be: Category: item1, item2, item3
- Use these categories when applicable (omit empty ones):
  Languages, Frameworks, Libraries, Databases, Tools, Concepts, Cloud, Testing, DevOps
- Keep items short; remove duplicates; normalize names (e.g., PostgreSQL, NumPy).
- Maximum 9 lines total.
"""

    if provider == 'openai':
        response = _generate_with_openai(prompt)
    elif provider == 'gemini':
        response = _generate_with_gemini(prompt)
    else:
        response = _generate_with_groq(prompt)

    lines = []
    seen = set()
    for raw_line in (response or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = raw_line.strip().lstrip('•').lstrip('-').strip()
        if not line or ':' not in line:
            continue
        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip().strip(',')
        if not key or not val:
            continue
        norm_key = key.lower()
        if norm_key in seen:
            continue
        seen.add(norm_key)
        lines.append(f"{key}: {val}")
        if len(lines) >= 9:
            break
    return "\n".join(lines).strip()

def improve_job_description(current_description: str) -> str:
    """
    Improve a job description or work experience bullet point.
    
    Args:
        current_description: The existing job description
    
    Returns:
        Improved description with better language and metrics
    """
    provider = get_ai_provider()
    
    prompt = f"""Improve the following job description for a resume to be more impactful and professional:

{current_description}

Make it:
1. More specific with quantifiable results if possible
2. Use stronger action verbs
3. More concise but comprehensive
4. More impressive to potential employers
5. ATS-friendly

Return only the improved description, nothing else."""

    if provider == 'openai':
        return _generate_with_openai(prompt)
    if provider == 'gemini':
        return _generate_with_gemini(prompt)
    return _generate_with_groq(prompt)


def _generate_with_openai(prompt: str, *, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    """Generate content using OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment variables")
    
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional resume writer and career advisor. Provide high-quality, concise responses."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {str(e)}")


def _generate_with_gemini(prompt: str, *, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    """Generate content using Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("Google GenerativeAI package not installed. Run: pip install google-generativeai")
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment variables")
    
    genai.configure(api_key=api_key)
    
    try:
        model = genai.GenerativeModel(os.getenv('GOOGLE_MODEL', 'gemini-1.5-flash'))
        response = model.generate_content(
            f"""You are a professional resume writer and career advisor. Provide high-quality, concise responses.

{prompt}""",
            generation_config=genai.types.GenerationConfig(
                temperature=float(temperature),
                max_output_tokens=int(max_tokens),
            )
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {str(e)}")


def _generate_with_groq(prompt: str, *, temperature: float = 0.7, max_tokens: int = 1000) -> str:
    """Generate content using Groq API."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("Groq package not installed. Run: pip install groq")

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in environment variables")

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant'),
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional resume writer and career advisor. Provide high-quality, concise responses.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"Groq API error: {str(e)}")


def _extract_json_object(text: str) -> str:
    value = _strip_code_fences(text)
    value = value.strip()
    if not value:
        raise ValueError("Empty response")
    if value.startswith('{') and value.endswith('}'):
        return value
    start = value.find('{')
    end = value.rfind('}')
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return value[start:end + 1].strip()


def _as_clean_str(value: Any, *, max_len: int = 2000) -> str:
    text = (value or '')
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _as_str_list(value: Any, *, max_items: int = 60, max_item_len: int = 120) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        cleaned = _as_clean_str(item, max_len=max_item_len)
        if cleaned:
            items.append(cleaned)
        if len(items) >= max_items:
            break
    # de-dupe while preserving order
    seen = set()
    unique: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def parse_resume_form_state(resume_text: str) -> Dict[str, Any]:
    """
    Use AI to extract resume text into the app's resume form state JSON.
    Returns a partial dict (missing keys omitted). Does not invent facts.
    """
    resume_text = (resume_text or '').strip()
    if not resume_text:
        return {}

    schema = {
        "first_name": "",
        "middle_name": "",
        "last_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "job_title": "",
        "summary": "",
        "profile_links": "",
        "profile_link_items": [{"type": "LinkedIn", "url": "https://..." }],
        "education_entries": [{"degree": "", "college": "", "year": "", "cgpa": ""}],
        "project_entries": [{"title": "", "tech": "", "desc": ""}],
        "experience_entries": [{"role": "", "company": "", "duration": "", "desc": ""}],
        "achievement_items": [""],
        "technical_skills": "",
        "technical_skill_items": [""],
        "technical_skills_grouped": "",
        "soft_skills": "",
        "soft_skill_items": [""],
    }

    prompt = f"""You are an information extraction engine.
Extract the following resume text into a JSON object matching this schema (example shape only):
{json.dumps(schema, indent=2)}

Rules:
- Return ONLY valid JSON (no markdown, no commentary).
- Use empty string "" or empty array [] if information is missing/unknown.
- Do NOT invent facts. Only use what is present in the resume text.
- Keep descriptions concise (1-3 lines) and ATS-friendly.
- profile_links: newline-separated URLs.
- profile_link_items: array of objects with keys: type, url (type examples: LinkedIn, GitHub, Portfolio).
- education_entries: most relevant 1-5 entries.
- experience_entries: 0-10 entries.
- project_entries: 0-8 entries.
- achievement_items: 0-20 items.

Resume text:
{resume_text}
"""

    raw = _generate_text(prompt, temperature=0.2, max_tokens=1400)
    json_text = _extract_json_object(raw)
    parsed = json.loads(json_text)
    if not isinstance(parsed, dict):
        raise ValueError("AI response was not a JSON object")

    allowed_keys = set(schema.keys())
    result: Dict[str, Any] = {}
    for key in allowed_keys:
        if key not in parsed:
            continue
        result[key] = parsed.get(key)

    # Clean strings
    for key in [
        "first_name", "middle_name", "last_name", "email", "phone", "location", "job_title",
        "summary", "profile_links", "technical_skills", "technical_skills_grouped", "soft_skills",
    ]:
        if key in result:
            result[key] = _as_clean_str(result.get(key), max_len=3000 if key in {"summary", "technical_skills_grouped"} else 200)

    # Clean list-of-strings
    if "achievement_items" in result:
        result["achievement_items"] = _as_str_list(result.get("achievement_items"), max_items=20, max_item_len=220)
    if "technical_skill_items" in result:
        result["technical_skill_items"] = _as_str_list(result.get("technical_skill_items"), max_items=60, max_item_len=80)
    if "soft_skill_items" in result:
        result["soft_skill_items"] = _as_str_list(result.get("soft_skill_items"), max_items=30, max_item_len=80)

    def clean_entries(value: Any, *, keys: List[str], max_items: int) -> List[Dict[str, str]]:
        if not isinstance(value, list):
            return []
        entries: List[Dict[str, str]] = []
        for raw_item in value:
            if not isinstance(raw_item, dict):
                continue
            entry = {k: _as_clean_str(raw_item.get(k), max_len=500 if k == "desc" else 160) for k in keys}
            if not any(entry.values()):
                continue
            entries.append(entry)
            if len(entries) >= max_items:
                break
        return entries

    if "profile_link_items" in result:
        items = clean_entries(result.get("profile_link_items"), keys=["type", "url"], max_items=8)
        result["profile_link_items"] = items
    if "education_entries" in result:
        result["education_entries"] = clean_entries(result.get("education_entries"), keys=["degree", "college", "year", "cgpa"], max_items=5)
    if "project_entries" in result:
        result["project_entries"] = clean_entries(result.get("project_entries"), keys=["title", "tech", "desc"], max_items=8)
    if "experience_entries" in result:
        result["experience_entries"] = clean_entries(result.get("experience_entries"), keys=["role", "company", "duration", "desc"], max_items=10)

    # Drop empty values to keep merge clean.
    return {k: v for k, v in result.items() if v not in ("", [], None)}
