from django import template
import re, hashlib

register = template.Library()

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
# NEW FUNCTION: no TeX, no dvips, no convert → placeholder only
# --------------------------------------------------------
def latex_placeholder(text):
    """
    Converts [pst]...[/pst], [xlat]...[/xlat], [psti]...[/psti]
    into a lightweight placeholder <div> (NO image generation).
    """

    # PST block placeholder
    text = re.sub(
        r'\[pst\](.*?)\[/pst\]',
        r"<div class='latex-placeholder'>図 зураг: PST блок</div>",
        text,
        flags=re.DOTALL
    )

    # XLAT block placeholder
    text = re.sub(
        r'\[xlat\](.*?)\[/xlat\]',
        r"<div class='latex-placeholder'>図 зураг: XLAT блок</div>",
        text,
        flags=re.DOTALL
    )

    # PST inline placeholder
    text = re.sub(
        r'\[psti\](.*?)\[/psti\]',
        r"<span class='latex-placeholder-inline'>図 inline</span>",
        text,
        flags=re.DOTALL
    )

    return text
