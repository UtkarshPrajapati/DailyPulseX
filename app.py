from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Your World News API key
NEWS_API_KEY = '9eb06d6dcaee45a2a1f72e7bc1216b12'
GEMINI_API_KEY = 'AIzaSyBW--z3TNEdeezRKhoY0Cl52BIXP4UsiAk'

def fetch_top_news(country=None, language='en'):
    """Fetch top news from World News API."""
    url = 'https://api.worldnewsapi.com/top-news'
    params = {
        'api-key': NEWS_API_KEY,
    }
    if country:
        params['source-country'] = country
    # if language:
    #     params['language'] = language

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('top_news'):
            articles = []
            for item in data['top_news']:
                if 'news' in item:
                    articles.extend(item['news'])
            print(f"Fetched {len(articles)} top news for country: {country}, language: {language}")
            return articles
        else:
            print(f"World News API error (top-news): {data.get('message')} - Full response: {data}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching top news: {e} - URL: {url}, Params: {params}")
        return []

def fetch_news(text=None, country=None, language='en', earliest_publish_date=None, latest_publish_date=None, category=None):
    """Search and filter news from World News API."""
    url = 'https://api.worldnewsapi.com/search-news'
    params = {
        'api-key': NEWS_API_KEY,
    }

    # At least one parameter (text or others) is required
    if text:
        params['text'] = text
    elif any([country, language, earliest_publish_date, latest_publish_date, category]):
        pass # Allow searching with other criteria even without text
    else:
        # If no search parameters are provided, fetch top news instead
        return fetch_top_news()

    if country:
        params['source-country'] = country
    if language:
        params['language'] = language
    if earliest_publish_date:
        params['earliest-publish-date'] = earliest_publish_date
    if latest_publish_date:
        params['latest-publish-date'] = latest_publish_date
    if category and category != 'all':
        params['categories'] = category

    if not params.get('text') and not any(params.get(key) for key in ['source-country', 'language', 'earliest-publish-date', 'latest-publish-date', 'categories']) and request.args:
        print("Warning: At least one search parameter (text, country, language, date, category) is required for search-news API.")
        return []

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('news'):
            articles = data['news']
            print(f"Fetched {len(articles)} articles with parameters: {params}")
            return articles
        else:
            print(f"World News API error (search-news): {data.get('message')} - Full response: {data}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching news: {e} - URL: {url}, Params: {params}")
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
                "google_search": {}
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
    """Render the homepage with top news or search results."""
    text = request.args.get('text')
    country = request.args.get('country')
    language = request.args.get('language')
    earliest_date = request.args.get('earliest_date')
    latest_date = request.args.get('latest_date')
    category = request.args.get('category')

    if not request.args:
        # Load top headlines from all over the world in English by default
        articles = fetch_top_news()
    else:
        articles = fetch_news(
            text=text,
            country=country,
            language=language,
            earliest_publish_date=earliest_date,
            latest_publish_date=latest_date,
            category=category
        )
        if not articles and not text and not any([country, language, earliest_date, latest_date, category]):
            # Handle the case where fetch_news returned [] because no search params, so fetch top news
            articles = fetch_top_news()

    return render_template(
        'index.html',
        articles=articles,
        text=text,
        country=country,
        language=language,
        earliest_date=earliest_date,
        latest_date=latest_date,
        category=category
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