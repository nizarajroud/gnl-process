"""
Lightweight URL content fetcher — for the generic Doc→Meta tool.

Fetches a web page and extracts its readable text (requests + BeautifulSoup).
No JS rendering (static HTML only); good enough for docs/articles. Raises
ValueError with a clear message on failure.

Independent of the exam pipeline.
"""

import re


def fetch_url_text(url, timeout=20, max_chars=400000):
    """Fetch a URL and return clean readable text. Raises ValueError on error."""
    url = (url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        raise ValueError(f"URL invalide (doit commencer par http/https): {url[:60]}")
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception as e:
        raise ValueError(f"Dépendance manquante pour le scraping: {e}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; GNL-Process/1.0; +doc-export)'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"Échec du téléchargement: {str(e)[:100]}")

    ctype = resp.headers.get('Content-Type', '')
    if 'html' not in ctype and 'text' not in ctype and not url.lower().endswith(('.html', '.htm')):
        # Not HTML — return raw text if it's textual, else error.
        if resp.text and len(resp.text) < max_chars:
            return resp.text.strip()
        raise ValueError(f"Type de contenu non géré: {ctype or 'inconnu'}")

    soup = BeautifulSoup(resp.text, 'lxml')
    # Drop noise
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside',
                     'noscript', 'form', 'svg']):
        tag.decompose()
    # Prefer main/article if present
    main = soup.find('main') or soup.find('article') or soup.body or soup
    text = main.get_text('\n')
    # Collapse excessive blank lines/whitespace
    lines = [ln.strip() for ln in text.splitlines()]
    text = '\n'.join(ln for ln in lines if ln)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if not text:
        raise ValueError("Aucun texte lisible extrait de la page.")
    return text[:max_chars]
