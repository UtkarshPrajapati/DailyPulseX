from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

NEWS_API_KEY = '9756f582d032441dbb82df7a303f97b9'
GEMINI_API_KEY = 'AIzaSyBW--z3TNEdeezRKhoY0Cl52BIXP4UsiAk'

def fetch_news():
    """Fetch top business headlines from NewsAPI."""
    url = f'https://newsapi.org/v2/top-headlines?country=us&category=business&apiKey={NEWS_API_KEY}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'ok':
            return data.get('articles', [])
        else:
            print(f"NewsAPI error: {data.get('message')}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching news: {e}")
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
        response.raise_for_status()  # Raises an exception for 4xx/5xx errors
        data = response.json()
        description = data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.RequestException as e:
        description = f"Error: Unable to fetch description - {str(e)}"
    except (KeyError, IndexError):
        description = "Description not available"
    return description

@app.route('/')
def index():
    """Render the homepage with news articles."""
    articles = fetch_news()
    return render_template('index.html', articles=articles)

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