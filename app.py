from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

 
NEWS_DATA_API_KEY = 'pub_790006bba0b56dd2d4be338d020dd1c976bde'  
GEMINI_API_KEY = 'AIzaSyBW--z3TNEdeezRKhoY0Cl52BIXP4UsiAk'

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

def fetch_news_data(query=None, country=None, category=None):
    """Fetch news from Newsdata.io API."""
    base_url = 'https://newsdata.io/api/1/latest'
    params = {
        'apikey': NEWS_DATA_API_KEY,
        'language': 'en',
        'q': query if query else None,
        'country': country if country and country != '' else None,
        'category': category if category and category != 'all' else None
    }
    # Remove None values from params
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            print(f"Fetched {len(data.get('results', []))} articles with parameters: {params}")
            return data.get('results', [])
        else:
            print(f"Newsdata.io API error: {data.get('message')} - Full response: {data}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching news from Newsdata.io: {e} - URL: {base_url}, Params: {params}")
        return []

def get_gemini_description(title):
    """Fetch a description from the Gemini API for a given news title using search grounding."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt = f"Search for the news article titled '{title}' and provide a concise description based on the search results."
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
                "Google Search": {}
            }
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        description = data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.RequestException as e:
        description = f"Error: Unable to fetch description - {str(e)}"
    except (KeyError, IndexError):
        description = "Description not available"
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
        search_query=query
    )

@app.route('/describe', methods=['POST'])
def describe():
    """Handle AJAX request to fetch description for an article."""
    data = request.get_json()
    title = data.get('title')
    if not title:
        return jsonify({'error': 'No title provided'}), 400
    description = get_gemini_description(title)
    return jsonify({'desc': description})

if __name__ == '__main__':
    app.run(debug=True)