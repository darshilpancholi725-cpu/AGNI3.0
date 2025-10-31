/**
 * A.G.N.I. AI - Frontend JavaScript
 * Advanced General News Intelligence interface
 */

// Application state
const AppState = {
    isVerifying: false,
    currentText: '',
    lastResult: null
};

// DOM elements
const elements = {};

// Configuration
const CONFIG = {
    API_ENDPOINT: '/api/verify_news',
    MAX_CHARS: 5000,
    MIN_CHARS: 10
};

// Classification configurations
const CLASSIFICATIONS = {
    'Verified': {
        icon: 'fas fa-check-circle',
        class: 'verified',
        title: 'Verified Information',
        badge: 'Verified'
    },
    'Misinformation': {
        icon: 'fas fa-times-circle',
        class: 'misinformation',
        title: 'Misinformation Detected',
        badge: 'False'
    },
    'Unverifiable': {
        icon: 'fas fa-question-circle',
        class: 'unverifiable',
        title: 'Cannot Verify',
        badge: 'Unverifiable'
    }
};

/**
 * Initialize DOM elements safely
 */
function initializeElements() {
    const elementIds = [
        'news-text', 'verify-btn', 'char-count', 'loading', 'results', 'error',
        'result-icon', 'classification-text', 'classification-badge', 
        'reason-text', 'sources-list', 'timestamp', 'error-message'
    ];
    
    elementIds.forEach(id => {
        elements[id.replace('-', '_')] = document.getElementById(id);
    });
    
    // Check if all required elements exist
    const missingElements = elementIds.filter(id => !document.getElementById(id));
    if (missingElements.length > 0) {
        console.error('Missing elements:', missingElements);
    }
}

/**
 * Initialize the application
 */
function initializeApp() {
    try {
        initializeElements();
        setupEventListeners();
        updateCharacterCount();
        updateVerifyButtonState();
        console.log('A.G.N.I. AI initialized successfully');
    } catch (error) {
        console.error('Failed to initialize A.G.N.I. AI:', error);
    }
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Text input events
    if (elements.news_text) {
        elements.news_text.addEventListener('input', handleTextInput);
        elements.news_text.addEventListener('keydown', handleKeyDown);
    }
    
    // Verify button click
    if (elements.verify_btn) {
        elements.verify_btn.addEventListener('click', handleVerifyClick);
    }
    
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', handleSmoothScroll);
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            handleVerifyClick();
        }
        if (e.key === 'Escape') {
            resetForm();
        }
    });
}

/**
 * Handle text input changes
 */
function handleTextInput() {
    updateCharacterCount();
    updateVerifyButtonState();
}

/**
 * Handle keyboard events in textarea
 */
function handleKeyDown(e) {
    // Tab key support
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = e.target.selectionStart;
        const end = e.target.selectionEnd;
        const value = e.target.value;
        
        e.target.value = value.substring(0, start) + '    ' + value.substring(end);
        e.target.selectionStart = e.target.selectionEnd = start + 4;
    }
}

/**
 * Update character count display
 */
function updateCharacterCount() {
    if (!elements.news_text || !elements.char_count) return;
    
    const currentLength = elements.news_text.value.length;
    elements.char_count.textContent = currentLength;
    
    // Color feedback for character limits
    if (currentLength > CONFIG.MAX_CHARS * 0.9) {
        elements.char_count.style.color = '#ef4444';
    } else if (currentLength > CONFIG.MAX_CHARS * 0.75) {
        elements.char_count.style.color = '#f59e0b';
    } else {
        elements.char_count.style.color = '#64748b';
    }
}

/**
 * Update verify button state
 */
function updateVerifyButtonState() {
    if (!elements.news_text || !elements.verify_btn) return;
    
    const text = elements.news_text.value.trim();
    const isValidLength = text.length >= CONFIG.MIN_CHARS && text.length <= CONFIG.MAX_CHARS;
    const isNotVerifying = !AppState.isVerifying;
    
    elements.verify_btn.disabled = !(isValidLength && isNotVerifying);
    
    // Update button content
    if (AppState.isVerifying) {
        elements.verify_btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>A.G.N.I. Analyzing...</span>';
    } else if (text.length < CONFIG.MIN_CHARS) {
        elements.verify_btn.innerHTML = '<i class="fas fa-brain"></i><span>Enter text to analyze</span>';
    } else if (text.length > CONFIG.MAX_CHARS) {
        elements.verify_btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>Text too long</span>';
    } else {
        elements.verify_btn.innerHTML = '<i class="fas fa-brain"></i><span>Analyze with A.G.N.I.</span>';
    }
}

/**
 * Handle verify button click
 */
async function handleVerifyClick() {
    if (!elements.news_text) return;
    
    const text = elements.news_text.value.trim();
    
    if (!validateInput(text) || AppState.isVerifying) {
        return;
    }
    
    try {
        await performVerification(text);
    } catch (error) {
        console.error('Verification failed:', error);
        showError('An unexpected error occurred. Please try again.');
    }
}

/**
 * Validate user input
 */
function validateInput(text) {
    if (text.length < CONFIG.MIN_CHARS) {
        showError(`Please enter at least ${CONFIG.MIN_CHARS} characters.`);
        if (elements.news_text) elements.news_text.focus();
        return false;
    }
    
    if (text.length > CONFIG.MAX_CHARS) {
        showError(`Text must be under ${CONFIG.MAX_CHARS} characters.`);
        if (elements.news_text) elements.news_text.focus();
        return false;
    }
    
    return true;
}

/**
 * Perform news verification
 */
async function performVerification(text) {
    try {
        AppState.isVerifying = true;
        AppState.currentText = text;
        
        showLoading();
        updateVerifyButtonState();
        
        console.log('Starting A.G.N.I. analysis');
        
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text })
        });
        
        const result = await response.json();
        
        console.log('A.G.N.I. analysis completed:', result);
        
        AppState.lastResult = result;
        showResults(result);
        
    } catch (error) {
        console.error('A.G.N.I. analysis error:', error);
        showError('Network error occurred. Please check your connection and try again.');
    } finally {
        AppState.isVerifying = false;
        updateVerifyButtonState();
    }
}

/**
 * Show loading state
 */
function showLoading() {
    hideAllSections();
    if (elements.loading) {
        elements.loading.classList.remove('hidden');
    }
}

/**
 * Show verification results
 */
function showResults(result) {
    hideAllSections();
    
    if (!elements.results) return;
    
    const classification = result.classification || 'Unverifiable';
    const config = CLASSIFICATIONS[classification] || CLASSIFICATIONS['Unverifiable'];
    
    // Update result display
    if (elements.result_icon) {
        elements.result_icon.className = config.icon;
    }
    
    if (elements.classification_text) {
        elements.classification_text.textContent = config.title;
    }
    
    if (elements.classification_badge) {
        elements.classification_badge.textContent = config.badge;
        elements.classification_badge.className = `classification-badge ${config.class}`;
    }
    
    if (elements.reason_text) {
        elements.reason_text.textContent = result.reason || 'Analysis completed by A.G.N.I. AI.';
    }
    
    // Update timestamp
    if (elements.timestamp) {
        const timestamp = new Date().toLocaleString();
        elements.timestamp.textContent = timestamp;
    }
    
    // Update sources
    displaySources(result.sources || []);
    
    // Apply classification styling
    elements.results.className = `results ${config.class}`;
    elements.results.classList.remove('hidden');
    
    // Scroll to results
    setTimeout(() => {
        elements.results.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
    }, 100);
}

/**
 * Display sources list
 */
function displaySources(sources) {
    if (!elements.sources_list) return;
    
    elements.sources_list.innerHTML = '';
    
    if (!sources || sources.length === 0) {
        const noSources = document.createElement('div');
        noSources.className = 'no-sources';
        noSources.textContent = 'No external sources were referenced for this analysis.';
        elements.sources_list.appendChild(noSources);
        return;
    }
    
    sources.forEach((source, index) => {
        if (isValidUrl(source)) {
            const sourceLink = createSourceLink(source, index + 1);
            elements.sources_list.appendChild(sourceLink);
        }
    });
}

/**
 * Create a source link element
 */
function createSourceLink(url, index) {
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'source-link';
    
    const domain = extractDomain(url);
    
    link.innerHTML = `
        <i class="fas fa-external-link-alt"></i>
        <span>Source ${index}: ${domain}</span>
    `;
    
    link.addEventListener('click', () => {
        console.log(`Source clicked: ${url}`);
    });
    
    return link;
}

/**
 * Show error state
 */
function showError(message) {
    hideAllSections();
    
    if (elements.error_message) {
        elements.error_message.textContent = message || 'An unexpected error occurred.';
    }
    
    if (elements.error) {
        elements.error.classList.remove('hidden');
        
        setTimeout(() => {
            elements.error.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        }, 100);
    }
}

/**
 * Hide all result sections
 */
function hideAllSections() {
    ['loading', 'results', 'error'].forEach(section => {
        const element = elements[section];
        if (element) {
            element.classList.add('hidden');
        }
    });
}

/**
 * Reset form to initial state
 */
function resetForm() {
    if (elements.news_text) {
        elements.news_text.value = '';
        elements.news_text.focus();
    }
    
    updateCharacterCount();
    updateVerifyButtonState();
    hideAllSections();
    
    AppState.currentText = '';
    AppState.lastResult = null;
    
    console.log('Form reset');
}

/**
 * Handle smooth scrolling for anchor links
 */
function handleSmoothScroll(e) {
    const href = e.currentTarget.getAttribute('href');
    
    if (href && href.startsWith('#')) {
        e.preventDefault();
        const target = document.querySelector(href);
        
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    }
}

/**
 * Utility function to validate URLs
 */
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (error) {
        return false;
    }
}

/**
 * Extract domain from URL
 */
function extractDomain(url) {
    try {
        const domain = new URL(url).hostname;
        return domain.replace(/^www\./, '');
    } catch (error) {
        return 'Unknown Source';
    }
}

/**
 * Error boundary for unhandled errors
 */
window.addEventListener('error', (e) => {
    console.error('Unhandled error:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
});

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// Make resetForm globally available for onclick handlers
window.resetForm = resetForm;