# AI Resume Generator - Setup & Usage Guide

This guide walks you through setting up and using the AI integration features for your resume generator.

## 📋 Table of Contents
1. [Installation](#installation)
2. [API Setup](#api-setup)
3. [API Endpoints](#api-endpoints)
4. [Frontend Integration](#frontend-integration)
5. [Usage Examples](#usage-examples)

---

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables
Copy the example .env file and add your API credentials:

```bash
cp .env.example .env
```

Then edit `.env` with your actual API keys.

---

## API Setup

### Option A: OpenAI (Recommended - Best Quality)

1. **Get an API Key:**
   - Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
   - Create a new API key
   - Copy the key

2. **Update .env:**
   ```
   OPENAI_API_KEY=sk-your-key-here
   OPENAI_MODEL=gpt-4o-mini
   ```

3. **Cost:**
   - GPT-4o-mini is affordable (~$0.00015 per bullet point)
   - Pay-as-you-go pricing

### Option B: Google Gemini (Free Trial Available)

1. **Get an API Key:**
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Copy the key

2. **Update .env:**
   ```
   GOOGLE_API_KEY=your-key-here
   GOOGLE_MODEL=gemini-1.5-flash
   ```

3. **Cost:**
   - Free tier available (1,000 requests/day limit)
   - Paid tier available if you need more

### Option C: Groq (Fast Inference)

1. **Get an API Key:**
   - Create an API key in your Groq account

2. **Update .env:**
   ```
   GROQ_API_KEY=your-key-here
   GROQ_MODEL=llama-3.1-8b-instant
   ```

3. **Optional (recommended if you have multiple keys set):**
   ```
   AI_PROVIDER=groq
   ```

---

## API Endpoints

All AI endpoints require JSON requests and return JSON responses.

### 1. Generate Bullet Points
**Endpoint:** `POST /api/ai/generate-bullets`

Generate professional bullet points for a job role.

**Request:**
```json
{
  "job_title": "Software Engineer",
  "skills": ["Python", "JavaScript", "Docker"],
  "num_bullets": 3,
  "kind": "experience",
  "context": "Company: Acme Inc. Built internal tooling to automate deployments; reduced release time from 2 hours to 20 minutes.",
  "keywords": ["CI/CD", "Kubernetes", "observability"],
  "job_description": "Looking for an engineer with experience in Docker, Kubernetes, CI/CD, and monitoring."
}
```

**Response:**
```json
{
  "bullets": "• Developed scalable microservices architecture using Python and Docker, reducing deployment time by 40%\n• Led cross-functional team of 5 engineers to implement real-time data processing system\n• Optimized database queries improving application performance by 60%"
}
```

### 2. Optimize Resume Content
**Endpoint:** `POST /api/ai/optimize-content`

Optimize resume content for ATS (Applicant Tracking System) and readability.

**Request:**
```json
{
  "resume_text": "Worked on a project that used Python to build things",
  "job_description": "Looking for Senior Python Developer with 5+ years experience in machine learning"
}
```

**Response:**
```json
{
  "optimized_content": "Architected and deployed machine learning pipeline using Python, processing 1M+ records daily with 95% accuracy..."
}
```

### 3. Extract Skills
**Endpoint:** `POST /api/ai/extract-skills`

Extract skills from a job description.

**Request:**
```json
{
  "job_description": "We're hiring a Full Stack Developer skilled in React, Node.js, PostgreSQL, Docker, AWS...",
  "category": "technical"
}
```

**Response:**
```json
{
  "skills": ["React", "Node.js", "PostgreSQL", "Docker", "AWS", "Full Stack Development"]
}
```

**Categories:**
- `technical` - Technical and programming skills
- `soft` - Soft skills and competencies
- `all` - Both technical and soft skills (default)

### 4. Generate Profile Summary
**Endpoint:** `POST /api/ai/generate-summary`

Generate a professional profile summary for the resume header.

**Request:**
```json
{
  "name": "John Doe",
  "job_title": "Senior Software Engineer",
  "years_experience": 8,
  "skills": ["Python", "Machine Learning", "System Design"]
}
```

**Response:**
```json
{
  "summary": "Results-driven Senior Software Engineer with 8+ years of experience designing and implementing scalable Python-based systems. Proven expertise in machine learning applications and system architecture optimization. Seeking to leverage advanced technical skills and leadership experience in a challenging role."
}
```

### 5. Improve Job Description
**Endpoint:** `POST /api/ai/improve-description`

Improve a single job description or work experience bullet point.

**Request:**
```json
{
  "description": "Worked on website design and made it faster"
}
```

**Response:**
```json
{
  "improved_description": "Optimized website performance by refactoring frontend code and implementing CDN integration, resulting in 50% faster page load times and 35% improvement in user engagement metrics"
}
```

### 6. Summarize Text (Projects / Experience)
**Endpoint:** `POST /api/ai/summarize`

Summarize a block of text into 1-4 resume-friendly sentences.

**Request:**
```json
{
  "text": "Built a full-stack web app with React and Flask. Implemented caching and background jobs. Users grew to 5k.",
  "kind": "project",
  "max_sentences": 2
}
```

**Response:**
```json
{
  "summary": "Built a full-stack React + Flask web app and implemented caching/background jobs to improve performance and scalability. Grew adoption to 5,000 users."
}
```

---

## Frontend Integration

### Example 1: Generate Bullets with JavaScript

```javascript
async function generateBulletPoints() {
  const jobTitle = document.getElementById('job_title').value;
  const skillsInput = document.getElementById('skills').value;
  const skills = skillsInput.split(',').map(s => s.trim()).filter(s => s);

  try {
    const response = await fetch('/api/ai/generate-bullets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_title: jobTitle,
        skills: skills,
        num_bullets: 3
      })
    });

    const data = await response.json();
    if (response.ok) {
      document.getElementById('bullets_output').value = data.bullets;
    } else {
      alert('Error: ' + data.error);
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
}
```

### Example 2: Extract Skills from Job Description

```javascript
async function extractSkills() {
  const jobDescription = document.getElementById('job_description').value;

  try {
    const response = await fetch('/api/ai/extract-skills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: jobDescription,
        category: 'technical'
      })
    });

    const data = await response.json();
    if (response.ok) {
      // Display skills as tags
      const skillsContainer = document.getElementById('extracted_skills');
      skillsContainer.innerHTML = data.skills
        .map(skill => `<span class="skill-tag">${skill}</span>`)
        .join('');
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
}
```

### Example 3: Optimize Resume Section

```javascript
async function optimizeContent() {
  const resumeText = document.getElementById('work_description').value;
  const jobDescription = document.getElementById('target_job').value;

  try {
    const response = await fetch('/api/ai/optimize-content', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_text: resumeText,
        job_description: jobDescription
      })
    });

    const data = await response.json();
    if (response.ok) {
      document.getElementById('work_description').value = data.optimized_content;
    } else {
      console.error('Error:', data.error);
    }
  } catch (error) {
    console.error('Request failed:', error);
  }
}
```

---

## Usage Examples

### Workflow 1: Create Resume from Job Description

1. **User pastes job description**
2. Click "Extract Skills" → Get relevant skills
3. Click "Generate Summary" → Create professional intro
4. For each role, click "Generate Bullets" → Get achievement statements
5. Optional: Click "Optimize" → Refine for ATS

### Workflow 2: Optimize Existing Resume

1. **User pastes resume content**
2. Click "Optimize for ATS" → Get improved version
3. Review and copy improved content
4. Paste into resume editor

### Workflow 3: Improve Single Bullet Point

1. **User selects a bullet point**
2. Click "Improve Description" → Get better version
3. Replace in resume
4. Save resume

---

## Troubleshooting

### Error: "No AI API key configured"
- Make sure you've set either `OPENAI_API_KEY` or `GOOGLE_API_KEY` in `.env`
- Restart your Flask app after updating `.env`

### Error: "OpenAI API error"
- Check your API key is correct and hasn't expired
- Verify you have sufficient API credits in your OpenAI account
- Check your internet connection

### Error: "Gemini API error"
- Verify your Google API key is valid
- Check you haven't exceeded the free tier limits (1,000 requests/day)
- Ensure the API is enabled in Google Cloud Console

### Slow responses
- First request may be slower due to API latency
- Optimize prompt complexity by reducing input length
- Consider using a faster model (gpt-4o-mini instead of gpt-4)

### Low quality output
- Provide more context in the job title or job description
- Include specific skills for better bullet points
- Review and manually edit AI-generated content as needed

---

## Cost Estimates

### OpenAI (GPT-4o-mini)
- ~$0.00015 per 1,000 tokens
- Average bullet point: 50-100 tokens = $0.0000075-$0.000015
- 100 bullet points = ~$0.001-$0.0015

### Google Gemini
- Free tier: 1,000 requests/day
- Paid: ~$0.05-$0.10 per 1M input tokens
- Very affordable at scale

---

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Add your API key to `.env`
3. ✅ Restart Flask app
4. ✅ Add HTML buttons/forms to your templates
5. ✅ Use the JavaScript examples above to call the endpoints
6. ✅ Test with sample data and refine as needed

For more help, refer to the individual API provider documentation:
- [OpenAI API Docs](https://platform.openai.com/docs/api-reference)
- [Google Gemini API Docs](https://ai.google.dev/docs)
