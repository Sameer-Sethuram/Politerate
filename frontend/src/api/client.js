const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';


class APIError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}


async function fetchAPI(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        ...options,
    });
    
    if (!response.ok) {
        let errorMessage;
        try {
            const errorBody = await response.json();
            errorMessage = errorBody.detail || `Error ${response.status}`;
        } catch {
            errorMessage = `Error ${response.status}`;
        }
        throw new APIError(errorMessage, response.status);
    }
    
    return response.json();
}


export async function analyzeArticle(params) {
    const { text, url = null, title = null, source = null } = params;
    
    return fetchAPI('/analyze', {
        method: 'POST',
        body: JSON.stringify({ text, url, title, source }),
    });
}


export async function checkHealth() {
    return fetchAPI('/health');
}