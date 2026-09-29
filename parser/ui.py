HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Applywizard | Resume Parser</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.5);
            --secondary: #8b5cf6;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.15) 0px, transparent 50%);
            background-attachment: fixed;
            line-height: 1.6;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        header {
            text-align: center;
            margin-bottom: 50px;
            animation: fadeInDown 0.8s ease-out;
        }

        h1 {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(135deg, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }

        p.subtitle {
            color: var(--text-muted);
            font-size: 1.1rem;
        }

        .glass-panel {
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: fadeInUp 0.8s ease-out;
            transition: all 0.3s ease;
        }

        .upload-area {
            border: 2px dashed var(--primary);
            border-radius: 16px;
            padding: 50px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            background: rgba(59, 130, 246, 0.05);
        }

        .upload-area:hover, .upload-area.dragover {
            background: rgba(59, 130, 246, 0.1);
            box-shadow: 0 0 20px var(--primary-glow);
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 3rem;
            margin-bottom: 15px;
        }

        .upload-text {
            font-size: 1.2rem;
            font-weight: 500;
            color: var(--primary);
        }

        .upload-hint {
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-top: 8px;
        }

        #file-input {
            display: none;
        }

        /* Loader */
        .loader-container {
            display: none;
            text-align: center;
            padding: 40px 0;
        }
        
        .loader {
            border: 4px solid rgba(255,255,255,0.1);
            border-left-color: var(--primary);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px auto;
        }

        /* Results Area */
        #results {
            display: none;
            margin-top: 40px;
            animation: fadeIn 0.8s ease-out;
        }

        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin: 30px 0 15px 0;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid var(--glass-border);
            padding-bottom: 10px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 20px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
            background: rgba(255, 255, 255, 0.05);
        }

        .card-title {
            font-size: 1.1rem;
            color: #fff;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .card-subtitle {
            color: var(--primary);
            font-size: 0.9rem;
            font-weight: 500;
            margin-bottom: 10px;
        }

        .card-detail {
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .badge-container {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }

        .badge {
            background: rgba(59, 130, 246, 0.2);
            color: #93c5fd;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .info-row {
            display: flex;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding-bottom: 10px;
        }
        
        .info-label {
            width: 120px;
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .info-value {
            flex: 1;
            font-weight: 500;
        }

        .restart-btn {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 30px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            margin: 40px auto 0 auto;
            display: block;
            transition: all 0.3s ease;
            box-shadow: 0 10px 20px -10px var(--primary-glow);
        }

        .restart-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 25px -10px var(--primary-glow);
        }

        .error-message {
            color: #ef4444;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            padding: 15px;
            border-radius: 12px;
            margin-top: 20px;
            display: none;
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>

<div class="container">
    <header>
        <h1>Resume Parser AI</h1>
        <p class="subtitle">Extract intelligent insights from any resume instantly.</p>
    </header>

    <div class="glass-panel" id="main-panel">
        <div class="upload-area" id="drop-zone" onclick="document.getElementById('file-input').click()">
            <div class="upload-icon">📄</div>
            <div class="upload-text">Drag & Drop your Resume here</div>
            <div class="upload-hint">or click to browse (PDF only)</div>
            <input type="file" id="file-input" accept="application/pdf">
        </div>

        <div class="loader-container" id="loader">
            <div class="loader"></div>
            <p>Analyzing document semantics...</p>
        </div>
        
        <div class="error-message" id="error"></div>
    </div>

    <div id="results">
        <!-- Results injected here -->
    </div>
</div>

<script>
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const loader = document.getElementById('loader');
    const resultsArea = document.getElementById('results');
    const mainPanel = document.getElementById('main-panel');
    const errorDiv = document.getElementById('error');

    // Drag & Drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleFile(files[0]);
    });

    fileInput.addEventListener('change', function() {
        if (this.files.length) handleFile(this.files[0]);
    });

    async function handleFile(file) {
        if (file.type !== 'application/pdf') {
            showError('Please upload a valid PDF file.');
            return;
        }

        errorDiv.style.display = 'none';
        dropZone.style.display = 'none';
        loader.style.display = 'block';
        resultsArea.style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/parse', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(errorText || 'Failed to parse resume');
            }

            const data = await response.json();
            renderResults(data);
            
            loader.style.display = 'none';
            mainPanel.style.display = 'none';
            resultsArea.style.display = 'block';
            
        } catch (err) {
            loader.style.display = 'none';
            dropZone.style.display = 'block';
            showError(err.message);
        }
    }

    function showError(msg) {
        errorDiv.textContent = msg;
        errorDiv.style.display = 'block';
    }

    function renderResults(data) {
        let html = '';

        // Personal Info
        const p = data.personal || {};
        html += `<div class="glass-panel" style="margin-bottom: 20px;">
                    <div class="section-title">👤 Personal Information</div>
                    <div class="info-row"><div class="info-label">Name</div><div class="info-value">${p.name || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">Headline</div><div class="info-value">${p.headline || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">Email</div><div class="info-value">${p.emails?.join(', ') || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">Phone</div><div class="info-value">${p.phones?.join(', ') || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">Location</div><div class="info-value">${p.location || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">LinkedIn</div><div class="info-value">${p.linkedin?.join(', ') || 'Not found'}</div></div>
                    <div class="info-row"><div class="info-label">GitHub</div><div class="info-value">${p.github?.join(', ') || 'Not found'}</div></div>
                 </div>`;

        // Skills
        const s = data.skills || {};
        const allSkills = [...(s.explicit || []), ...(s.from_experience || []), ...(s.from_projects || [])];
        const uniqueSkills = [...new Set(allSkills)];
        if (uniqueSkills.length > 0) {
            html += `<div class="section-title">⚡ Skills</div><div class="glass-panel"><div class="badge-container">`;
            uniqueSkills.forEach(skill => {
                html += `<span class="badge">${skill}</span>`;
            });
            html += `</div></div>`;
        }

        // Experience
        if (data.experience && data.experience.length > 0) {
            html += `<div class="section-title">💼 Experience</div><div class="grid">`;
            data.experience.forEach(exp => {
                html += `<div class="card">
                            <div class="card-title">${exp.job_title || 'Unknown Title'}</div>
                            <div class="card-subtitle">${exp.company || 'Unknown Company'} • ${exp.start_date || '?'} - ${exp.end_date || '?'}</div>
                            ${exp.location ? `<div class="card-detail" style="margin-bottom:8px">📍 ${exp.location}</div>` : ''}
                            <div class="card-detail">${(exp.description || []).slice(0,2).join(' ')}...</div>
                         </div>`;
            });
            html += `</div>`;
        }

        // Education
        if (data.education && data.education.length > 0) {
            html += `<div class="section-title">🎓 Education</div><div class="grid">`;
            data.education.forEach(edu => {
                let score = '';
                if (edu.cgpa) score = `CGPA: ${edu.cgpa}/${edu.gpa_scale || 10}`;
                else if (edu.percentage) score = `Score: ${edu.percentage}%`;
                
                html += `<div class="card">
                            <div class="card-title">${edu.degree || edu.level || 'Degree'}</div>
                            <div class="card-subtitle">${edu.institution || 'Unknown Institution'}</div>
                            <div class="card-detail">
                                ${edu.start_year || '?'} - ${edu.end_year || edu.graduation_year || '?'}
                                ${score ? `<br>🏆 ${score}` : ''}
                            </div>
                         </div>`;
            });
            html += `</div>`;
        }

        // Projects
        if (data.projects && data.projects.length > 0) {
            html += `<div class="section-title">🚀 Projects</div><div class="grid">`;
            data.projects.forEach(proj => {
                html += `<div class="card">
                            <div class="card-title">${proj.name || 'Project'}</div>
                            ${proj.technologies && proj.technologies.length ? `<div class="badge-container" style="margin-bottom:10px">${proj.technologies.map(t=>`<span class="badge">${t}</span>`).join('')}</div>` : ''}
                            <div class="card-detail">${(proj.description || []).slice(0,2).join(' ')}...</div>
                         </div>`;
            });
            html += `</div>`;
        }

        html += `<button class="restart-btn" onclick="location.reload()">Upload Another Resume</button>`;
        resultsArea.innerHTML = html;
    }
</script>
</body>
</html>
"""
