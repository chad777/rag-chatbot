// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;

// DOM elements
let chatMessages, chatInput, sendButton, totalCourses, courseTitles, themeToggle;
let attachButton, imageInput, imagePreviewContainer, imagePreview, imageRemoveBtn;
let newChatBtn;

// Selected image state
let selectedImageData = null;
let selectedImageMediaType = null;

// ── Theme ─────────────────────────────────────────

/**
 * Apply a theme ('dark' | 'light') to the document.
 * Updates the data-theme attribute, persists the choice,
 * and keeps the toggle button's aria-label in sync.
 */
function applyTheme(theme) {
    document.documentElement.dataset.theme = theme === 'light' ? 'light' : '';
    localStorage.setItem('theme', theme);
    if (themeToggle) {
        themeToggle.setAttribute(
            'aria-label',
            theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'
        );
    }
}

/**
 * Toggle between dark and light, wrapping the switch in a
 * short-lived transition class so colors animate smoothly.
 */
function toggleTheme() {
    const current = localStorage.getItem('theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';

    document.body.classList.add('theme-transition');
    applyTheme(next);
    setTimeout(() => document.body.classList.remove('theme-transition'), 350);
}

/**
 * TODO: Implement theme initialisation.
 *
 * Decide how the app should pick a theme on first load.
 * Two valid approaches — choose one (or combine them):
 *
 * Option A — Always default to dark (matches the current design):
 *   const saved = localStorage.getItem('theme') || 'dark';
 *   applyTheme(saved);
 *
 * Option B — Respect the visitor's OS preference on first visit,
 *            then remember any manual override:
 *   const systemPrefers = window.matchMedia('(prefers-color-scheme: light)').matches
 *       ? 'light' : 'dark';
 *   const saved = localStorage.getItem('theme') || systemPrefers;
 *   applyTheme(saved);
 *
 * Add your 2–3 lines here:
 */
function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    applyTheme(saved);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalCourses = document.getElementById('totalCourses');
    courseTitles = document.getElementById('courseTitles');
    themeToggle = document.getElementById('themeToggle');
    attachButton = document.getElementById('attachButton');
    imageInput = document.getElementById('imageInput');
    imagePreviewContainer = document.getElementById('imagePreviewContainer');
    imagePreview = document.getElementById('imagePreview');
    imageRemoveBtn = document.getElementById('imageRemoveBtn');
    newChatBtn = document.getElementById('newChatBtn');

    initTheme();
    setupEventListeners();
    createNewSession();
    loadCourseStats();
});

// Event Listeners
function setupEventListeners() {
    // New chat
    newChatBtn.addEventListener('click', startNewChat);

    // Theme toggle
    themeToggle.addEventListener('click', toggleTheme);

    // Image attach
    attachButton.addEventListener('click', () => imageInput.click());
    imageInput.addEventListener('change', handleImageSelect);
    imageRemoveBtn.addEventListener('click', clearSelectedImage);

    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    
    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
        });
    });
}


// Image handling
function handleImageSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    selectedImageMediaType = file.type;
    const reader = new FileReader();
    reader.onload = (ev) => {
        // Strip the "data:image/...;base64," prefix — API wants raw base64
        selectedImageData = ev.target.result.split(',')[1];
        imagePreview.src = ev.target.result;
        imagePreviewContainer.style.display = 'block';
        attachButton.classList.add('has-image');
    };
    reader.readAsDataURL(file);
    // Reset so the same file can be re-selected
    imageInput.value = '';
}

function clearSelectedImage() {
    selectedImageData = null;
    selectedImageMediaType = null;
    imagePreview.src = '';
    imagePreviewContainer.style.display = 'none';
    attachButton.classList.remove('has-image');
}

// Chat Functions
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query && !selectedImageData) return;

    // Capture and clear image before disabling UI
    const imageDataToSend = selectedImageData;
    const imageMediaTypeToSend = selectedImageMediaType;
    const imageSrcForDisplay = imagePreview.src;
    if (imageDataToSend) clearSelectedImage();

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;
    attachButton.disabled = true;

    // Add user message (with image if present)
    addMessage(query || '(image)', 'user', null, false, imageDataToSend ? imageSrcForDisplay : null);

    // Add loading message - create a unique container for it
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query || '(image)',
                session_id: currentSessionId,
                image_data: imageDataToSend || null,
                image_media_type: imageMediaTypeToSend || null,
            })
        });

        if (!response.ok) throw new Error('Query failed');

        const data = await response.json();

        // Debug: Log what we're receiving from the API
        console.log("API Response - Full data:", data);
        console.log("API Response - Sources type:", typeof data.sources);
        console.log("API Response - Sources content:", data.sources);
        if (data.sources && data.sources.length > 0) {
            console.log("First source:", data.sources[0]);
            console.log("First source type:", typeof data.sources[0]);
        }

        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources);

    } catch (error) {
        // Replace loading message with error
        loadingMessage.remove();
        addMessage(`Error: ${error.message}`, 'assistant');
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        attachButton.disabled = false;
        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false, imageSrc = null) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;

    // Debug: Log what addMessage receives
    console.log("addMessage called with sources:", sources);
    console.log("sources type:", typeof sources);
    if (sources && sources.length > 0) {
        console.log("First source in addMessage:", sources[0]);
    }

    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);

    const imageHtml = imageSrc
        ? `<img class="chat-image" src="${escapeHtml(imageSrc)}" alt="Attached image">`
        : '';

    let html = `<div class="message-content">${imageHtml}${displayContent}</div>`;

    if (sources && sources.length > 0) {
        const sourceItems = sources.map(source => {
            if (typeof source === 'object' && source.text) {
                if (source.url) {
                    return `<li class="source-item">
                        <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
                            <svg class="source-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                            <span>${escapeHtml(source.text)}</span>
                        </a>
                    </li>`;
                } else {
                    return `<li class="source-item source-item--no-link">
                        <svg class="source-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        <span>${escapeHtml(source.text)}</span>
                    </li>`;
                }
            } else {
                return `<li class="source-item source-item--no-link"><span>${escapeHtml(source)}</span></li>`;
            }
        }).join('');

        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">
                    <svg class="sources-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
                    Sources <span class="sources-count">${sources.length}</span>
                </summary>
                <ul class="sources-list">${sourceItems}</ul>
            </details>
        `;
    }

    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function startNewChat() {
    if (currentSessionId) {
        try {
            await fetch(`${API_URL}/session/${currentSessionId}`, { method: 'DELETE' });
        } catch (e) {
            console.warn('Could not clear session on backend:', e);
        }
    }
    createNewSession();
    clearSelectedImage();
}

async function createNewSession() {
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?', 'assistant', null, true);
}

// Load course statistics
async function loadCourseStats() {
    try {
        console.log('Loading course stats...');
        const response = await fetch(`${API_URL}/courses`);
        if (!response.ok) throw new Error('Failed to load course stats');
        
        const data = await response.json();
        console.log('Course data received:', data);
        
        // Update stats in UI
        if (totalCourses) {
            totalCourses.textContent = data.total_courses;
        }
        
        // Update course titles
        if (courseTitles) {
            if (data.course_titles && data.course_titles.length > 0) {
                courseTitles.innerHTML = data.course_titles
                    .map(title => `<div class="course-title-item">${title}</div>`)
                    .join('');
            } else {
                courseTitles.innerHTML = '<span class="no-courses">No courses available</span>';
            }
        }
        
    } catch (error) {
        console.error('Error loading course stats:', error);
        // Set default values on error
        if (totalCourses) {
            totalCourses.textContent = '0';
        }
        if (courseTitles) {
            courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
        }
    }
}/* Cache bust */
