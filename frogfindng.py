from flask import Flask, request, render_template_string
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urlparse, parse_qs, unquote, urljoin, quote

# --- App & Cache Initialisierung ---
config = {
    "CACHE_TYPE": "SimpleCache",  # Speichert den Cache im Speicher
    "CACHE_DEFAULT_TIMEOUT": 300  # Standard-Timeout von 5 Minuten
}
app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)

# --- System-Erkennung ---
def get_compatibility_level(user_agent_string, override_mode=None):
    if override_mode in ['modern', 'retro', 'ultra_retro']: return override_mode
    if not user_agent_string: return 'modern'
    ua = user_agent_string.lower()
    if any(k in ua for k in ['netscape/4', 'msie 4', 'msie 3', 'msie 2']): return 'ultra_retro'
    if any(k in ua for k in ['msie 6', 'msie 5', 'netscape6', 'mac_powerpc', 'beos', 'amiga', 'atari']): return 'retro'
    return 'modern'

# --- Kernlogik ---
def clean_html_content(html_content, base_url, compatibility_level='modern', persistent_params=None):
    if persistent_params is None: persistent_params = {}
    soup = BeautifulSoup(html_content, 'html.parser')
    tags_to_remove = ['script', 'style', 'nav', 'footer', 'aside', 'form', 'header', 'iframe']
    for tag in soup.find_all(tags_to_remove): tag.decompose()
    for ad in soup.find_all(lambda t: 'ad' in t.get('class', []) or 'ad' in t.get('id', '')): ad.decompose()
    
    if compatibility_level == 'ultra_retro':
        for tag in soup.find_all('img'):
            tag.replace_with(f"[Bild: {tag.get('alt', 'Bild')}]")

    for a_tag in soup.find_all('a', href=True):
        absolute_url = urljoin(base_url, a_tag['href'])
        query_params = f"url={quote(absolute_url)}"
        if persistent_params.get('mode'): query_params += f"&mode={persistent_params['mode']}"
        if persistent_params.get('dark'): query_params += f"&dark={persistent_params['dark']}"
        a_tag['href'] = f"/read?{query_params}"

    for tag in soup.find_all():
        if not tag.get_text(strip=True) and not tag.find_all(True) and tag.name not in ['img', 'br', 'hr']:
            tag.decompose()
            
    allowed_attrs = {'a': ['href', 'title'], 'pre': [], 'code': []}
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs); tag.attrs.clear()
        if tag.name in allowed_attrs:
            for attr, val in attrs.items():
                if attr in allowed_attrs[tag.name]: tag[attr] = val
    return soup.prettify()

@cache.cached(timeout=900, query_string=True) # Cache für 15 Minuten
def get_readable_article_content(url, compatibility_level, persistent_params_str):
    # persistent_params wird als String übergeben, um cacheable zu sein
    import json
    persistent_params = json.loads(persistent_params_str)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        doc = Document(response.text)
        title = doc.title()
        cleaned_body = clean_html_content(doc.summary(), response.url, compatibility_level, persistent_params)
        return {"title": title, "body": cleaned_body, "error": False}
    except requests.exceptions.RequestException as e:
        return {"title": "Fehler", "body": f"<h1>Fehler</h1><p>{e}</p>", "error": True}

# --- Dynamische HTML-Vorlagen & Kontext ---
def get_page_template(title_var, content_var, comp_level, dark_mode=False, is_home=False):
    style_block = ""
    if comp_level != 'ultra_retro':
        css_vars = ":root { --bg-color: #FFF; --text-color: #000; --link-color: #0000EE; --visited-color: #551A8B; --border-color: #999; --block-bg-color: #EEE; }"
        if dark_mode:
            css_vars = ":root { --bg-color: #212121; --text-color: #E0E0E0; --link-color: #82aaff; --visited-color: #c792ea; --border-color: #555; --block-bg-color: #333; }"
        style_block = f"""<style>{css_vars} body {{font-family:Times New Roman,serif;line-height:1.6;max-width:800px;margin:1em auto;padding:0 1em;background-color:var(--bg-color);color:var(--text-color);{'text-align:center;' if is_home else ''}}} h1,h2,h3{{line-height:1.2}} img{{max-width:100%;height:auto}} a{{color:var(--link-color)}} a:visited{{color:var(--visited-color)}} pre{{background-color:var(--block-bg-color);padding:10px;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;border:1px solid var(--border-color)}} blockquote{{border-left:2px solid #ccc;margin-left:20px;padding-left:10px}} input,select{{font-size:1em;margin:5px}} hr{{width:80%;border-style:solid;border-color:var(--border-color);border-width:1px 0 0 0}} .search-result{{margin-bottom:1.5em;text-align:left}} .url-input{{width:80%}} .info-box{{font-size:0.8em;color:#555;background-color:#EEE;padding:5px;border:1px solid #CCC;margin-bottom:1em}} .options-box{{border:1px solid var(--border-color);padding:10px;margin-top:2em;display:inline-block;text-align:left}}</style>"""
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><title>{title_var}</title>{style_block}</head><body><div class="info-box">System-Modus: <b>{comp_level}</b>{' | Dark Mode Aktiv' if dark_mode else ''}</div>{content_var}</body></html>"""

def get_request_context():
    user_agent = request.headers.get('User-Agent', '')
    override_mode = request.args.get('mode') or request.form.get('mode')
    dark_mode = (request.args.get('dark') or request.form.get('dark')) == '1'
    comp_level = get_compatibility_level(user_agent, override_mode)
    persistent_params = {}
    if override_mode: persistent_params['mode'] = override_mode
    if dark_mode: persistent_params['dark'] = '1'
    return { "comp_level": comp_level, "dark_mode": dark_mode, "persistent_params": persistent_params }

# --- Flask-Routen ---
@app.route('/')
def home():
    context = get_request_context()
    hidden_fields = ''.join([f'<input type="hidden" name="{k}" value="{v}">' for k, v in context['persistent_params'].items()])
    content = f"""<h1>FrogFind NG</h1> <p>Eine einfache Schnittstelle zum modernen Web.</p> <hr> <h2>Suche im Web</h2> <form action="/search" method="get">{hidden_fields}<input type="text" name="q" size="40"><input type="submit" value="Suchen"></form> <hr> <h2>URL direkt lesen</h2> <form action="/read" method="post">{hidden_fields}<input type="url" name="url" class="url-input" placeholder="https://..."><input type="submit" value="Lesen"></form> <br> <div class="options-box"><h2>Optionen</h2><form action="/" method="get"><label for="mode">Modus:</label><select name="mode" id="mode"> <option value="modern" {'selected' if context['comp_level'] == 'modern' else ''}>Modern</option> <option value="retro" {'selected' if context['comp_level'] == 'retro' else ''}>Retro</option> <option value="ultra_retro" {'selected' if context['comp_level'] == 'ultra_retro' else ''}>Ultra-Retro</option></select><br><input type="checkbox" name="dark" value="1" id="dark" {'checked' if context['dark_mode'] else ''}><label for="dark">Dark Mode</label><br><br><input type="submit" value="Anwenden"></form></div>"""
    return get_page_template("FrogFind NG", content, context['comp_level'], context['dark_mode'], is_home=True)

@app.route('/search')
def search():
    context = get_request_context()
    query = request.args.get('q', '')
    if not query: return "Bitte einen Suchbegriff eingeben.", 400
    search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; FrogFindNG/1.0)'}
    try:
        response = requests.get(search_url, headers=headers); response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        results_html = f"<h1>Suchergebnisse für '{query}'</h1>"
        for res in soup.find_all('div', class_='result'):
            title = res.find('h2', class_='result__title').find('a')
            snippet = res.find('a', class_=['result__snippet', 'result__snippet--video'])
            url_tag = res.find('a', class_='result__url')
            if not all([title, snippet, url_tag]): continue
            real_url = parse_qs(urlparse(url_tag['href']).query).get('uddg', [''])[0]
            if real_url:
                params = [f"url={quote(real_url)}"] + [f"{k}={v}" for k,v in context['persistent_params'].items()]
                results_html += f"""<div class="search-result"><h3><a href="/read?{'&'.join(params)}">{title.text.strip()}</a></h3><p>{snippet.text.strip()}</p><a href="/read?{'&'.join(params)}"><small>{unquote(real_url)}</small></a></div>"""
        back_link = f"/?{'&'.join([f'{k}={v}' for k,v in context['persistent_params'].items()])}"
        return get_page_template(f"Suche: {query}", f'<p><a href="{back_link}">&larr; Zurück</a></p><hr>{results_html}', context['comp_level'], context['dark_mode'])
    except requests.RequestException as e: return f"Fehler bei der Suche: {e}", 500

@app.route('/read', methods=['POST', 'GET'])
def read_article():
    import json
    context = get_request_context()
    url = request.args.get('url') or request.form.get('url')
    if not url: return "URL fehlt.", 400
    article_data = get_readable_article_content(url, context['comp_level'], json.dumps(context['persistent_params']))
    back_link = f"/?{'&'.join([f'{k}={v}' for k,v in context['persistent_params'].items()])}"
    content = f'<p><a href="{back_link}">&larr; Zurück</a></p><hr><h1>{article_data["title"]}</h1>{article_data["body"]}'
    return get_page_template(article_data["title"], content, context['comp_level'], context['dark_mode'])

# --- Hauptprogramm ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
