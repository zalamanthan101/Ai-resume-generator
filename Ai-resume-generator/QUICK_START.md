# AI Resume Generator - Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure AI API
Choose **ONE** option:

#### **Option A: OpenAI (Recommended)**
1. Get free API key: https://platform.openai.com/api-keys
2. Edit `.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

#### **Option B: Google Gemini (Free Tier)**
1. Get free API key: https://aistudio.google.com/app/apikey
2. Edit `.env`:
   ```
   GOOGLE_API_KEY=your-key-here
   ```

### Step 3: Start Flask
```bash
python app.py
```

### Step 4 (Optional): Admin Panel
Add these to `.env` (first run creates the admin account automatically):
```
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me
```
Then open:
`/admin/login`

---

## 🚀 Available AI Features

| Feature | Endpoint | What It Does |
|---------|----------|-------------|
| **Generate Bullets** | `/api/ai/generate-bullets` | Creates achievement statements for a job role |
| **Optimize Content** | `/api/ai/optimize-content` | Improves resume for ATS (Applicant Tracking Systems) |
| **Extract Skills** | `/api/ai/extract-skills` | Gets skills from job descriptions |
| **Generate Summary** | `/api/ai/generate-summary` | Creates professional profile summary |
| **Improve Description** | `/api/ai/improve-description` | Refines single bullet points |

---

## 🎯 Quick Examples

### Example 1: Generate Bullet Points
```bash
curl -X POST http://localhost:5000/api/ai/generate-bullets \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Data Scientist",
    "skills": ["Python", "Machine Learning", "SQL"],
    "num_bullets": 3
  }'
```

**Output:**
```json
{
  "bullets": "• Built ML models achieving 95% accuracy in customer churn prediction...\n• Optimized SQL queries reducing data pipeline latency by 60%..."
}
```

### Example 2: Extract Skills from Job Description
```bash
curl -X POST http://localhost:5000/api/ai/extract-skills \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Looking for Senior Full Stack Developer with React, Node.js, PostgreSQL, Docker experience...",
    "category": "technical"
  }'
```

**Output:**
```json
{
  "skills": ["React", "Node.js", "PostgreSQL", "Docker", "Full Stack Development"]
}
```

---

## 📝 Add to Your HTML Templates

Copy the starter code from `AI_TEMPLATE_EXAMPLE.html` into your resume template:

```html
<!-- Add this section to templates/resume.html -->
<div class="ai-helper-section">
  <h3>✨ AI Resume Assistant</h3>
  
  <!-- Generate Bullets -->
  <input id="job_title_input" placeholder="Job title...">
  <input id="skills_input" placeholder="Skills (comma-separated)...">
  <button onclick="generateBullets()">Generate Bullets</button>
  <textarea id="generated_bullets" placeholder="Output..."></textarea>
  
  <!-- More features... -->
</div>

<script>
  async function generateBullets() {
    const jobTitle = document.getElementById('job_title_input').value;
    const response = await fetch('/api/ai/generate-bullets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_title: jobTitle,
        skills: ['skill1', 'skill2'],
        num_bullets: 3
      })
    });
    const data = await response.json();
    document.getElementById('generated_bullets').value = data.bullets;
  }
</script>
```

---

## 📚 Full Documentation

For detailed setup and API documentation, see: **`AI_SETUP.md`**

---

## ❓ Troubleshooting

### "No AI API key configured"
- Make sure you added the API key to `.env`
- Restart Flask app after editing `.env`

### "OpenAI API error"
- Check API key is valid at https://platform.openai.com/api-keys
- Verify you have API credits

### "Gemini API error"
- Check API key at https://aistudio.google.com/app/apikey
- Verify you haven't exceeded free tier (1,000 requests/day)

### "Groq API error"
- Check GROQ_API_KEY is set in `.env`
- Verify the model name in `GROQ_MODEL` (or remove it to use the default)

### Slow responses
- First request may be slower due to API setup
- Subsequent requests are faster (~2-3 seconds per request)

---

## 💡 Pro Tips

1. **For fast iteration:** Use Groq
2. **For bulk generation:** Use OpenAI
3. **For free testing:** Use Google Gemini (free tier)
3. **Always review AI output:** Edit as needed for your context
4. **Combine features:** Extract skills → Generate bullets → Optimize for ATS
5. **Test locally first:** Use curl or Postman before adding to frontend

---

## 📋 File Summary

- **`ai_utils.py`** - Core AI functions (don't edit unless customizing)
- **`AI_SETUP.md`** - Complete setup guide with API docs
- **`AI_TEMPLATE_EXAMPLE.html`** - Copy-paste UI code for your templates
- **`.env.example`** - Environment variable template (copy to `.env`)
- **`requirements.txt`** - Python dependencies

---

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Get API key (Groq, OpenAI, or Gemini)
3. ✅ Add API key to `.env`
4. ✅ Restart Flask: `python app.py`
5. ✅ Copy HTML/JS from `AI_TEMPLATE_EXAMPLE.html` to your templates
6. ✅ Test in browser or with curl
7. ✅ Customize styling and integrate with your UI

---

## Support

- **OpenAI Help:** https://help.openai.com
- **Gemini Help:** https://support.google.com/googlecloud
- **Flask Docs:** https://flask.palletsprojects.com

Happy resume building! 🎉
