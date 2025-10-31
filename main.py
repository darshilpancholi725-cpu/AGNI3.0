"""
A.G.N.I. AI - Real-time News Verification with Google Search Integration
Advanced misinformation detection with live source verification
"""

import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import re
from urllib.parse import quote_plus

import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging without Unicode characters for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agni.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="A.G.N.I. AI - Real-time Verification",
    description="Advanced news verification with real-time search integration",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create and mount static directory
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

# Configure Gemini AI
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("SUCCESS: Gemini AI configured successfully")
    except Exception as e:
        logger.error(f"ERROR: Failed to configure Gemini AI: {e}")
        GEMINI_API_KEY = None
else:
    logger.warning("WARNING: GEMINI_API_KEY not found")

# Check Google Search API
if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
    logger.info("SUCCESS: Google Search API configured")
else:
    logger.warning("WARNING: Google Search API not fully configured")

# Pydantic models
class NewsVerificationRequest(BaseModel):
    text: str
    
    @field_validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError('Text field cannot be empty')
        if len(v.strip()) < 10:
            raise ValueError('Text must be at least 10 characters long')
        if len(v) > 5000:
            raise ValueError('Text cannot exceed 5000 characters')
        return v.strip()

class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str
    source: str

class VerificationResult(BaseModel):
    classification: str
    reason: str
    sources: List[str]
    search_results: List[SearchResult]
    timestamp: str
    confidence: float

async def extract_key_claims(text: str) -> List[str]:
    """Extract key factual claims from the text using Gemini AI"""
    if not GEMINI_API_KEY:
        return [text]  # Fallback to using the entire text
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
Analyze the following text and extract 2-3 key factual claims that can be verified through search.
Focus on specific, verifiable statements (names, dates, events, statistics, etc.).
Ignore opinions and subjective statements.

Text: "{text}"

Return the claims as a JSON array of strings. Example:
["claim 1", "claim 2", "claim 3"]

If no verifiable claims are found, return: ["no verifiable claims"]
"""
        
        response = model.generate_content(prompt)
        if response and response.text:
            # Clean and parse the response
            claims_text = response.text.strip()
            if claims_text.startswith('```'):
                claims_text = re.sub(r'```(?:json)?\n?|```', '', claims_text).strip()
            
            try:
                claims = json.loads(claims_text)
                if isinstance(claims, list) and len(claims) > 0:
                    logger.info(f"INFO: Extracted {len(claims)} claims: {claims}")
                    return claims
            except json.JSONDecodeError:
                logger.warning("WARNING: Failed to parse claims JSON, using fallback")
        
    except Exception as e:
        logger.error(f"ERROR: Error extracting claims: {e}")
    
    # Fallback: use the original text
    return [text[:200]]  # Limit to 200 chars for search

async def search_google(query: str, num_results: int = 5) -> List[SearchResult]:
    """Search Google for information about a query"""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logger.warning("WARNING: Google Search API not configured")
        return []
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_SEARCH_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'num': num_results,
            'dateRestrict': 'm6'  # Last 6 months for recent info
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    for item in data.get('items', []):
                        try:
                            # Extract domain name as source
                            source = item.get('displayLink', item.get('link', ''))
                            if source.startswith('www.'):
                                source = source[4:]
                            
                            result = SearchResult(
                                title=item.get('title', ''),
                                link=item.get('link', ''),
                                snippet=item.get('snippet', ''),
                                source=source
                            )
                            results.append(result)
                        except Exception as e:
                            logger.warning(f"WARNING: Error parsing search result: {e}")
                            continue
                    
                    logger.info(f"INFO: Found {len(results)} search results for: {query[:50]}...")
                    return results
                else:
                    logger.error(f"ERROR: Google Search API error: {response.status}")
                    return []
                    
    except Exception as e:
        logger.error(f"ERROR: Search error: {e}")
        return []

async def verify_with_ai_and_search(text: str) -> Dict[str, Any]:
    """Comprehensive verification using both AI analysis and real-time search"""
    
    logger.info("INFO: Starting A.G.N.I. real-time verification...")
    
    # Step 1: Extract key claims
    logger.info("INFO: Extracting key claims...")
    claims = await extract_key_claims(text)
    
    # Step 2: Search for each claim
    logger.info("INFO: Searching for verification sources...")
    all_search_results = []
    search_tasks = []
    
    for claim in claims[:3]:  # Limit to 3 claims to avoid quota issues
        if claim != "no verifiable claims":
            search_tasks.append(search_google(claim, 3))
    
    if search_tasks:
        search_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)
        for results in search_results_lists:
            if isinstance(results, list):
                all_search_results.extend(results)
    
    # Step 3: AI analysis with search context
    logger.info("INFO: Performing AI analysis with search context...")
    
    if not GEMINI_API_KEY:
        return {
            "classification": "Unverifiable",
            "reason": "AI analysis unavailable - API key not configured",
            "sources": [result.link for result in all_search_results[:5]],
            "search_results": [result.dict() for result in all_search_results[:5]],
            "confidence": 0.3
        }
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Prepare search context
        search_context = ""
        if all_search_results:
            search_context = "\n\nRELEVANT SEARCH RESULTS:\n"
            for i, result in enumerate(all_search_results[:5], 1):
                search_context += f"{i}. Source: {result.source}\n"
                search_context += f"   Title: {result.title}\n"
                search_context += f"   Content: {result.snippet}\n"
                search_context += f"   URL: {result.link}\n\n"
        
        analysis_prompt = f"""
You are A.G.N.I. (Advanced General News Intelligence), an expert fact-checker with access to real-time information.

TASK: Analyze the following claim and determine its accuracy using the provided search results.

CLAIM TO VERIFY: "{text}"

{search_context}

INSTRUCTIONS:
1. Carefully analyze the claim against the search results
2. Look for corroboration or contradiction in reliable sources
3. Consider source credibility (news outlets, official sites, fact-checkers)
4. Assign a confidence score (0.0 to 1.0) based on evidence strength

RESPONSE FORMAT (JSON only):
{{
    "classification": "Verified" | "Misinformation" | "Unverifiable",
    "reason": "2-3 sentence explanation citing specific sources when possible",
    "confidence": 0.0-1.0,
    "key_findings": ["finding 1", "finding 2"]
}}

CLASSIFICATION RULES:
- "Verified": Multiple reliable sources confirm the claim (confidence > 0.7)
- "Misinformation": Reliable sources contradict the claim (confidence > 0.7)  
- "Unverifiable": Insufficient evidence, opinion-based, or conflicting information

Respond with JSON only, no additional text.
"""
        
        response = model.generate_content(analysis_prompt)
        
        if response and response.text:
            # Clean and parse response
            response_text = response.text.strip()
            if response_text.startswith('```'):
                response_text = re.sub(r'```(?:json)?\n?|```', '', response_text).strip()
            
            try:
                result = json.loads(response_text)
                
                # Validate and enhance result
                valid_classifications = ['Verified', 'Misinformation', 'Unverifiable']
                if result.get('classification') not in valid_classifications:
                    result['classification'] = 'Unverifiable'
                
                if not isinstance(result.get('confidence'), (int, float)):
                    result['confidence'] = 0.5
                else:
                    result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))
                
                if not result.get('reason'):
                    result['reason'] = 'Analysis completed with available information.'
                
                # Add search results and sources
                result['sources'] = [r.link for r in all_search_results[:5]]
                result['search_results'] = [r.dict() for r in all_search_results[:5]]
                
                logger.info(f"SUCCESS: Verification complete: {result['classification']} (confidence: {result['confidence']:.2f})")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"ERROR: Failed to parse AI response: {e}")
        
    except Exception as e:
        logger.error(f"ERROR: AI analysis error: {e}")
    
    # Fallback response
    return {
        "classification": "Unverifiable",
        "reason": "Unable to complete analysis due to technical limitations.",
        "sources": [result.link for result in all_search_results[:3]],
        "search_results": [result.dict() for result in all_search_results[:3]],
        "confidence": 0.3
    }

@app.post("/api/verify_news")
async def verify_news(request: NewsVerificationRequest):
    """
    Real-time news verification with AI analysis and live search
    """
    start_time = datetime.now()
    logger.info(f"INFO: New verification request: {request.text[:100]}...")
    
    try:
        # Perform comprehensive verification
        result = await verify_with_ai_and_search(request.text)
        
        # Prepare response
        response = {
            "classification": result['classification'],
            "reason": result['reason'],
            "sources": result.get('sources', []),
            "search_results": result.get('search_results', []),
            "confidence": result.get('confidence', 0.5),
            "timestamp": datetime.now().isoformat(),
            "processing_time": (datetime.now() - start_time).total_seconds()
        }
        
        logger.info(f"SUCCESS: Verification completed in {response['processing_time']:.2f}s: {result['classification']}")
        return response
        
    except Exception as e:
        logger.error(f"ERROR: Verification failed: {e}")
        return {
            "classification": "Unverifiable",
            "reason": "Service temporarily unavailable due to technical error.",
            "sources": [],
            "search_results": [],
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "processing_time": (datetime.now() - start_time).total_seconds()
        }

@app.get("/")
async def root():
    """Main application page"""
    if static_dir.exists() and (static_dir / "index.html").exists():
        return RedirectResponse(url="/static/index.html")
    else:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>A.G.N.I. AI - Real-time Verification</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f5f7fa; }}
                .header {{ background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }}
                .status-card {{ background: white; padding: 25px; border-radius: 12px; margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .status-item {{ display: flex; justify-content: space-between; align-items: center; margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 8px; }}
                .status-ok {{ color: #10b981; font-weight: bold; }}
                .status-warning {{ color: #f59e0b; font-weight: bold; }}
                .status-error {{ color: #ef4444; font-weight: bold; }}
                .setup-instructions {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                .api-endpoints {{ background: #e0f2fe; border-left: 4px solid #0284c7; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                code {{ background: #374151; color: #e5e7eb; padding: 4px 8px; border-radius: 4px; font-family: 'Consolas', monospace; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧠 A.G.N.I. AI</h1>
                <h2>Advanced General News Intelligence</h2>
                <p>Real-time Verification System with Google Search Integration</p>
            </div>
            
            <div class="status-card">
                <h3>System Status</h3>
                <div class="status-item">
                    <span><strong>Gemini AI:</strong></span>
                    <span class="{'status-ok' if GEMINI_API_KEY else 'status-error'}">
                        {'ACTIVE' if GEMINI_API_KEY else 'NOT CONFIGURED'}
                    </span>
                </div>
                <div class="status-item">
                    <span><strong>Google Search API:</strong></span>
                    <span class="{'status-ok' if (GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID) else 'status-error'}">
                        {'ACTIVE' if (GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID) else 'NOT CONFIGURED'}
                    </span>
                </div>
                <div class="status-item">
                    <span><strong>Static Files:</strong></span>
                    <span class="{'status-ok' if static_dir.exists() else 'status-warning'}">
                        {'READY' if static_dir.exists() else 'MISSING'}
                    </span>
                </div>
            </div>
            
            <div class="setup-instructions">
                <h3>Quick Setup</h3>
                <ol>
                    <li><strong>Gemini AI:</strong> Get API key from <a href="https://ai.google.dev/" target="_blank">Google AI Studio</a></li>
                    <li><strong>Google Search:</strong> Set up Custom Search API at <a href="https://developers.google.com/custom-search/v1/introduction" target="_blank">Google Developers</a></li>
                    <li><strong>.env file:</strong> Add your API keys</li>
                    <li><strong>Static files:</strong> Add HTML/CSS/JS files to <code>static/</code> directory</li>
                </ol>
                
                <h4>Required .env variables:</h4>
                <pre><code>GEMINI_API_KEY=your_gemini_key_here
GOOGLE_SEARCH_API_KEY=your_search_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id</code></pre>
            </div>
            
            <div class="api-endpoints">
                <h3>API Endpoints</h3>
                <p><strong>Verify News:</strong> <code>POST /api/verify_news</code></p>
                <p><strong>Health Check:</strong> <code>GET /health</code></p>
                <p><strong>Documentation:</strong> <code>GET /docs</code></p>
                <p><strong>Interactive Docs:</strong> <code>GET /redoc</code></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "A.G.N.I. AI Real-time Verification",
        "version": "2.0.0",
        "capabilities": {
            "gemini_ai": GEMINI_API_KEY is not None,
            "google_search": GOOGLE_SEARCH_API_KEY is not None and GOOGLE_SEARCH_ENGINE_ID is not None,
            "static_files": static_dir.exists(),
            "real_time_verification": True
        },
        "api_status": {
            "gemini_configured": bool(GEMINI_API_KEY),
            "search_configured": bool(GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID),
            "full_functionality": bool(GEMINI_API_KEY and GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID)
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("A.G.N.I. AI - Real-time Verification System")
    print("=" * 50)
    print(f"Gemini AI: {'READY' if GEMINI_API_KEY else 'MISSING'}")
    print(f"Google Search: {'READY' if (GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID) else 'MISSING'}")
    print("Server starting at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")