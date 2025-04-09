from flask import Flask, render_template, request, jsonify, current_app
import requests
import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# API keys from environment variables with fallbacks
NEWS_DATA_API_KEY = os.environ.get('NEWS_DATA_API_KEY', 'pub_790006bba0b56dd2d4be338d020dd1c976bde')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyBW--z3TNEdeezRKhoY0Cl52BIXP4UsiAk')

# News data cache
NEWS_CACHE = {}
CACHE_DURATION = 15 * 60  # 15 minutes in seconds

# Category and Country options for the UI
CATEGORIES = [
    ('all', 'All'),
    ('politics', 'Politics'),
    ('sports', 'Sports'),
    ('business', 'Business'),
    ('technology', 'Technology'),
    ('entertainment', 'Entertainment'),
    ('science', 'Science'),
    ('health', 'Health'),
    ('world', 'World')
    # Add more categories as needed based on Newsdata.io documentation
]

COUNTRIES = [
    ('', 'All'),
    ('us', 'United States'),
    ('gb', 'United Kingdom'),
    ('in', 'India'),
    ('au', 'Australia'),
    ('jp', 'Japan'),
    ('de', 'Germany'),
    ('fr', 'France'),
    ('ca', 'Canada')
    # Add more countries as needed based on Newsdata.io documentation
]

def get_cache_key(query, country, category):
    """Generate a unique cache key based on request parameters."""
    return f"{query}:{country}:{category}"

def fetch_news_data(query=None, country=None, category=None):
    """Fetch news from Newsdata.io API with caching."""
    # Check cache first
    cache_key = get_cache_key(query, country, category)
    cached_data = NEWS_CACHE.get(cache_key)
    
    if cached_data:
        cache_time, results = cached_data
        # Return cached data if it's still valid
        if time.time() - cache_time < CACHE_DURATION:
            print(f"Using cached data for {cache_key}")
            return results
    
    base_url = 'https://newsdata.io/api/1/latest'
    params = {
        'apikey': NEWS_DATA_API_KEY,
        'language': 'en',
        'q': query if query else None,
        'country': country if country and country != '' else 'in',
        'category': category if category and category != 'all' else None
    }
    # Remove None values from params
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            results = data.get('results', [])
            print(f"Fetched {len(results)} articles with parameters: {params}")
            # Cache the results
            NEWS_CACHE[cache_key] = (time.time(), results)
            return results
        else:
            error_msg = data.get('message', 'Unknown API error')
            print(f"Newsdata.io API error: {error_msg} - Full response: {data}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching news from Newsdata.io: {e} - URL: {base_url}, Params: {params}")
        return []
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return []

# Apply rate limiting to Gemini API calls
@lru_cache(maxsize=100)
def get_gemini_description(title):
    """Fetch a description from the Gemini API for a given news title using search grounding."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt = f"Search for the news article titled '{title}' and provide a concise description based on the search results. Keep it under 200 words."
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {
                "google_search": {}
            }
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        description = data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.Timeout:
        description = "Error: Request to Gemini API timed out. Please try again later."
    except requests.RequestException as e:
        description = f"Error: Unable to fetch description - {str(e)}"
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini API response: {e}, Response: {response.text if 'response' in locals() else 'No response'}")
        description = "Description not available due to an error in processing the API response."
    return description

@app.route('/')
def index():
    """Render the homepage with news based on filters."""
    query = request.args.get('q')
    country = request.args.get('country')
    category = request.args.get('category')

    if not request.args:
        # Load latest headlines from all categories on first load
        articles = fetch_news_data()
    else:
        articles = fetch_news_data(query=query, country=country, category=category)

    return render_template(
        'index.html',
        articles=articles,
        categories=CATEGORIES,
        countries=COUNTRIES,
        current_category=category,
        current_country=country,
        search_query=query,
        last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/describe', methods=['POST'])
@limiter.limit("10 per minute")
def describe():
    """Handle AJAX request to fetch description for an article."""
    data = request.get_json()
    title = data.get('title')
    print('Title Got:-', title)
    if not title:
        return jsonify({'error': 'No title provided'}), 400
    description = get_gemini_description(title)
    print(description)
    return jsonify({'desc': description})

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Admin endpoint to clear the news cache."""
    if request.headers.get('X-Admin-Key') != os.environ.get('ADMIN_KEY'):
        return jsonify({'error': 'Unauthorized'}), 403
    NEWS_CACHE.clear()
    get_gemini_description.cache_clear()
    return jsonify({'message': 'Cache cleared successfully'})

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors."""
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)