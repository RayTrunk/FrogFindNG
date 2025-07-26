from flask import Flask, request, render_template_string, Response
from flask_caching import Cache
import requests
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urlparse, parse_qs, unquote, urljoin, quote
import json

# --- App & Cache Initialization ---
config = {
    "CACHE_TYPE": "SimpleCache",  # Using in-memory cache
    "CACHE_DEFAULT_TIMEOUT": 300  # Default timeout of 5 minutes
}
app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)

# --- System Detection ---
def get_compatibility_level(user_agent_string, override_mode=None):
    """Determines the compatibility level based on User-Agent or an override parameter."""
    if override_mode in ['modern', 'retro', 'ultra_retro', 'wap']:
        return override_mode
    if not user_agent_string:
        return 'modern'
    ua = user_agent_string.lower()
    if any(k in ua for k in ['netscape/4', 'msie 4', 'msie 3', 'msie 2']):
        return 'ultra_retro'
    if any(k in ua for k in ['msie 6', 'msie 5', 'netscape6', 'mac_powerpc', 'beos', 'amiga', 'atari']):
        return 'retro'
    return 'modern'

# --- WML Conversion ---
def convert_html_to_wml(soup):
    """Converts a BeautifulSoup object into a WML string."""
    wml_body = ""
    # Find all relevant tags for WML conversion
    for tag in soup.find_all(['p', 'h1', 'h2', 'h3', 'a', 'br', 'hr', 'pre']):
        if tag.name in ['h1', 'h2', 'h3']:
            # WML doesn't have headers, so we use bold paragraphs
            wml_body += f"<p><b>{tag.get_text(strip=True)}</b></p>"
        elif tag.name == 'p':
            wml_body += f"<p>{tag.get_text(strip=True)}</p>"
        elif tag.name == 'a' and tag.has_attr('href'):
            # Keep the links as they are (already rewritten)
            wml_body += f"<a href=\"{tag['href']}\">{tag.get_text(strip=True)}</a><br/>"
        elif tag.name == 'br':
            wml_body += "<br/>"
        elif tag.name == 'hr':
            wml_body += "<p>----------</p>"
        elif tag.name == 'pre':
             wml_body += f"<p>{tag.get_text()}</p>" # Simple text representation for pre
    return wml_body

# --- Core Logic ---
def clean_html_content(html_content, base_url, compatibility_level='modern', persistent_params=None):
    """Cleans HTML content and prepares it for display."""
    if persistent_params is None:
        persistent_params = {}
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Universal cleaning for all modes
    tags_to_remove = ['script', 'style', 'nav', 'footer', 'aside', 'form', 'header', 'iframe']
    for tag in soup.find_all(tags_to_remove):
        tag.decompose()
    for ad in soup.find_all(lambda t: 'ad' in t.get('class', []) or 'ad' in t.get('id', '')):
        ad.decompose()

    # Rewrite all links to point back to our service
    for a_tag in soup.find_all('a', href=True):
        absolute_url = urljoin(base_url, a_tag['href'])
        query_params = f"url={quote(absolute_url)}"
        if persistent_params.get('mode'):
            query_params += f"&mode={persistent_params['mode']}"
        if persistent_params.get('dark'):
            query_params += f"&dark={persistent_params['dark']}"
        a_tag['href'] = f"/read?{query_params}"

    # Mode-specific processing
    if compatibility_level == 'wap':
        return convert_html_to_wml(soup)

    if compatibility_level == 'ultra_retro':
        for tag in soup.find_all('img'):
            tag.replace_with(f"[Image: {tag.get('alt', 'Image')}]")

    # Remove tags that are empty and not self-closing
    for tag in soup.find_all():
        if not tag.get_text(strip=True) and not tag.find_all(True) and tag.name not in ['img', 'br', 'hr']:
            tag.decompose()
            
    # Whitelist attributes for security and simplicity
    allowed_attrs = {'a': ['href', 'title'], 'pre': [], 'code': []}
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        tag.attrs.clear()
        if tag.name in allowed_attrs:
            for attr, val in attrs.items():
                if attr in allowed_attrs[tag.name]:
                    tag[attr] = val
    return soup.prettify()

@cache.cached(timeout=900, query_string=True) # Cache for 15 minutes
def get_readable_article_content(url, compatibility_level, persistent_params_str):
    """Fetches and processes an article from a URL."""
    # persistent_params is passed as a string to be cacheable
    persistent_params = json.loads(persistent_params_str)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        doc = Document(response.text)
        title = doc.title()
        # The cleaning function will now handle WML conversion if needed
        cleaned_body = clean_html_content(doc.summary(), response.url, compatibility_level, persistent_params)
        return {"title": title, "body": cleaned_body, "error": False}
    except requests.exceptions.RequestException as e:
        return {"title": "Error", "body": f"<h1>Error</h1><p>{e}</p>", "error": True}

# --- Dynamic HTML & WML Templates & Context ---
def get_wml_template(title, content):
    """Creates a WML page structure."""
    return f"""<?xml version="1.0"?><!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml"><wml><card id="main" title="{title}"><p>{content}</p></card></wml>"""

def get_page_template(title_var, content_var, comp_level, dark_mode=False, is_home=False):
    """Creates an HTML page structure."""
    style_block = ""
    if comp_level != 'ultra_retro':
        css_vars = ":root { --bg-color: #FFF; --text-color: #000; --link-color: #0000EE; --visited-color: #551A8B; --border-color: #999; --block-bg-color: #EEE; }"
        if dark_mode:
            css_vars = ":root { --bg-color: #212121; --text-color: #E0E0E0; --link-color: #82aaff; --visited-color: #c792ea; --border-color: #555; --block-bg-color: #333; }"
        style_block = f"""<style>{css_vars} body {{font-family:Times New Roman,serif;line-height:1.6;max-width:800px;margin:1em auto;padding:0 1em;background-color:var(--bg-color);color:var(--text-color);{'text-align:center;' if is_home else ''}}} h1,h2,h3{{line-height:1.2}} img{{max-width:100%;height:auto}} a{{color:var(--link-color)}} a:visited{{color:var(--visited-color)}} pre{{background-color:var(--block-bg-color);padding:10px;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;border:1px solid var(--border-color)}} blockquote{{border-left:2px solid #ccc;margin-left:20px;padding-left:10px}} input,select{{font-size:1em;margin:5px}} hr{{width:80%;border-style:solid;border-color:var(--border-color);border-width:1px 0 0 0}} .search-result{{margin-bottom:1.5em;text-align:left}} .url-input{{width:80%}} .info-box{{font-size:0.8em;color:#555;background-color:#EEE;padding:5px;border:1px solid #CCC;margin-bottom:1em}} .options-box{{border:1px solid var(--border-color);padding:10px;margin-top:2em;display:inline-block;text-align:left}}</style>"""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{title_var}</title>{style_block}</head><body><div class="info-box">System Mode: <b>{comp_level}</b>{' | Dark Mode Active' if dark_mode else ''}</div>{content_var}</body></html>"""

def get_request_context():
    """Gathers context from the current request (mode, dark mode, etc.)."""
    user_agent = request.headers.get('User-Agent', '')
    override_mode = request.args.get('mode') or request.form.get('mode')
    dark_mode = (request.args.get('dark') or request.form.get('dark')) == '1'
    comp_level = get_compatibility_level(user_agent, override_mode)
    persistent_params = {}
    if override_mode: persistent_params['mode'] = override_mode
    if dark_mode: persistent_params['dark'] = '1'
    return { "comp_level": comp_level, "dark_mode": dark_mode, "persistent_params": persistent_params }

# --- Flask Routes ---
@app.route('/')
def home():
    context = get_request_context()
    hidden_fields = ''.join([f'<input type="hidden" name="{k}" value="{v}">' for k, v in context['persistent_params'].items()])
    # Added 'WAP' to the options dropdown
    content = f"""<h1>FrogFind NG</h1> <p>A simple interface to the modern web.</p> <hr> <h2>Search the Web</h2> <form action="/search" method="get">{hidden_fields}<input type="text" name="q" size="40"><input type="submit" value="Search"></form> <hr> <h2>Read URL Directly</h2> <form action="/read" method="post">{hidden_fields}<input type="url" name="url" class="url-input" placeholder="https://..."><input type="submit" value="Read"></form> <br> <div class="options-box"><h2>Options</h2><form action="/" method="get"><label for="mode">Mode:</label><select name="mode" id="mode"> <option value="modern" {'selected' if context['comp_level'] == 'modern' else ''}>Modern</option> <option value="retro" {'selected' if context['comp_level'] == 'retro' else ''}>Retro</option> <option value="ultra_retro" {'selected' if context['comp_level'] == 'ultra_retro' else ''}>Ultra-Retro</option><option value="wap" {'selected' if context['comp_level'] == 'wap' else ''}>WAP</option></select><br><input type="checkbox" name="dark" value="1" id="dark" {'checked' if context['dark_mode'] else ''}><label for="dark">Dark Mode</label><br><br><input type="submit" value="Apply"></form></div>"""
    return get_page_template("FrogFind NG", content, context['comp_level'], context['dark_mode'], is_home=True)

@app.route('/search')
def search():
    context = get_request_context()
    query = request.args.get('q', '')
    if not query: return "Please enter a search term.", 400
    search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; FrogFindNG/1.0)'}
    try:
        response = requests.get(search_url, headers=headers); response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Build results for both HTML and WML
        results_html = f"<h1>Search Results for '{query}'</h1>"
        results_wml = f"<b>Search Results for '{query}'</b><br/>"
        
        for res in soup.find_all('div', class_='result'):
            title_tag = res.find('h2', class_='result__title').find('a')
            snippet_tag = res.find('a', class_=['result__snippet', 'result__snippet--video'])
            url_tag = res.find('a', class_='result__url')
            if not all([title_tag, snippet_tag, url_tag]): continue
            
            real_url = parse_qs(urlparse(url_tag['href']).query).get('uddg', [''])[0]
            if real_url:
                params = [f"url={quote(real_url)}"] + [f"{k}={v}" for k,v in context['persistent_params'].items()]
                read_link = f"/read?{'&'.join(params)}"
                
                # HTML version
                results_html += f"""<div class="search-result"><h3><a href="{read_link}">{title_tag.text.strip()}</a></h3><p>{snippet_tag.text.strip()}</p><a href="{read_link}"><small>{unquote(real_url)}</small></a></div>"""
                # WML version
                results_wml += f"<p><a href=\"{read_link}\">{title_tag.text.strip()}</a><br/>{snippet_tag.text.strip()}</p>"

        back_link_params = '&'.join([f'{k}={v}' for k, v in context['persistent_params'].items()])
        back_link_href = f"/?{back_link_params}"
        
        if context['comp_level'] == 'wap':
            wml_content = f'<p><a href="{back_link_href}">&lt;&lt; Back</a></p><hr/>{results_wml}'
            wml_output = get_wml_template(f"Search: {query}", wml_content)
            return Response(wml_output, mimetype='text/vnd.wap.wml')
        else:
            html_content = f'<p><a href="{back_link_href}">&larr; Back</a></p><hr>{results_html}'
            return get_page_template(f"Search: {query}", html_content, context['comp_level'], context['dark_mode'])

    except requests.RequestException as e: return f"Error during search: {e}", 500

@app.route('/read', methods=['POST', 'GET'])
def read_article():
    context = get_request_context()
    url = request.args.get('url') or request.form.get('url')
    if not url: return "URL missing.", 400
    
    # Pass persistent params as a JSON string for caching
    article_data = get_readable_article_content(url, context['comp_level'], json.dumps(context['persistent_params']))
    
    back_link_params = '&'.join([f'{k}={v}' for k, v in context['persistent_params'].items()])
    back_link_href = f"/?{back_link_params}"

    if context['comp_level'] == 'wap':
        if article_data["error"]:
            content = f"<b>Error:</b> {article_data['title']}"
        else:
            # Body is already WML-formatted by clean_html_content
            content = f'<b>{article_data["title"]}</b><br/>{article_data["body"]}'
        
        wml_content = f'<p><a href="{back_link_href}">&lt;&lt; Back</a></p><hr/>{content}'
        wml_output = get_wml_template(article_data["title"], wml_content)
        return Response(wml_output, mimetype='text/vnd.wap.wml')
    else:
        content = f'<p><a href="{back_link_href}">&larr; Back</a></p><hr><h1>{article_data["title"]}</h1>{article_data["body"]}'
        return get_page_template(article_data["title"], content, context['comp_level'], context['dark_mode'])

# --- Main Program ---
if __name__ == '__main__':
    # Running in debug mode. For production, use a proper WSGI server.
    app.run(debug=True, port=5000)
