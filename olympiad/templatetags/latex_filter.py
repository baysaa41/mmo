from django import template
import re, hashlib, requests

register = template.Library()

PSTRICKS_SERVER_BASE_URL = 'https://pst.mathminds.club'

@register.filter(name='latex')
def latex(value):
    value = enum2ol(value)
    value = emph2em(value)
    value = bf2strong(value)
    value = center2div(value)
    value = eqno2quad(value)
    return latex_placeholder(value)

def enum2ol(value):
    value=re.sub(r'\\begin{enumerate}.*?\\item',"<ol>\n<li>",value,flags=re.DOTALL)
    value=re.sub(r'\\item\s+','</li>\n<li>',value,flags=re.DOTALL)
    value=re.sub(r'\\end{enumerate}','</li>\n</ol>',value)
    return value

def emph2em(text):
    text = re.sub(r'\\emph{(.*?)}',r'<em>\1</em>',text)
    text = re.sub(r'``(.*?)\'\'',r'<q>\1</q>',text)
    return text

def bf2strong(text):
    text = re.sub(r'\\textbf{(.*?)}',r'<strong>\1</strong>',text)
    return text

def eqno2quad(text):
    return text.replace("eqno", "quad")

def center2div(text):
    return re.sub(
        r'(\\begin{center}\s+(.*?)\s+\\end{center})',
        r'<div class="text-center">\2</div>',
        text,
        flags=re.DOTALL
    )

# --------------------------------------------------------
# PSTricks рендер хийх функц
# --------------------------------------------------------
def render_pstricks(code):
    """
    PSTricks кодыг сервер рүү илгээж, зургийн URL авах
    """
    try:
        response = requests.post(
            f'{PSTRICKS_SERVER_BASE_URL}/render-pstricks',
            json={'code': code},
            timeout=30
        )
        if response.ok:
            result = response.json()
            if result.get('image_url'):
                return f'{PSTRICKS_SERVER_BASE_URL}{result["image_url"]}'
    except Exception as e:
        print(f'PSTricks render error: {e}')
    return None

def pst_replacer(match):
    """
    [pst] блокийг <img> болгох callback
    """
    code = match.group(1).strip()
    image_url = render_pstricks(code)
    if image_url:
        return f'<div class="text-center my-2"><img src="{image_url}" style="max-width: 100%; height: auto;" alt="PSTricks"></div>'
    return '<div class="text-danger">[PSTricks рендер алдаа]</div>'

def psti_replacer(match):
    """
    [psti] inline блокийг <img> болгох callback
    """
    code = match.group(1).strip()
    image_url = render_pstricks(code)
    if image_url:
        return f'<img src="{image_url}" style="max-height: 1.5em; vertical-align: middle;" alt="PSTricks inline">'
    return '<span class="text-danger">[PST алдаа]</span>'

# --------------------------------------------------------
# LaTeX placeholder функц
# --------------------------------------------------------
def latex_placeholder(text):
    """
    Converts [pst]...[/pst], [xlat]...[/xlat], [psti]...[/psti]
    into rendered images or placeholders.
    """

    # PST block - render to image
    text = re.sub(
        r'\[pst\](.*?)\[/pst\]',
        pst_replacer,
        text,
        flags=re.DOTALL
    )

    # XLAT block placeholder (хэрэв хэрэгтэй бол дараа нэмнэ)
    text = re.sub(
        r'\[xlat\](.*?)\[/xlat\]',
        r"<div class='latex-placeholder'>図 зураг: XLAT блок</div>",
        text,
        flags=re.DOTALL
    )

    # PST inline - render to image
    text = re.sub(
        r'\[psti\](.*?)\[/psti\]',
        psti_replacer,
        text,
        flags=re.DOTALL
    )

    return text
