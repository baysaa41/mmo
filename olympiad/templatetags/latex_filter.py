from django import template
import re, hashlib, io, os

register = template.Library()


@register.filter(name='latex')
def latex(value):
    value = enum2ol(value)
    value = emph2em(value)
    value = bf2strong(value)
    value = center2div(value)
    value = eqno2quad(value)
    return pst2png(value)


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
    text.replace("eqno","quad")
    return text


def center2div(text):
    text = re.sub(r'(\\begin{center}\s+(.*?)\s+\\end{center})',r'<div class="text-center">\2</div>',text,flags=re.DOTALL)
    return text


def pst2png(text):
    TEX_ROOT = "/home/deploy/django/static/latex"
    latex = '/usr/bin/latex'
    dvips = '/usr/bin/dvips'
    convert = '/usr/bin/convert -density 140 -trim -transparent \"#FFFFFF\"'
    os.chdir( TEX_ROOT )
    matches=re.findall(r'\[pst\](.*?)\[/pst\]',text, re.MULTILINE|re.DOTALL)
    for match in matches:
        match = match.strip()
        result = hashlib.md5(match.encode())
        name = result.hexdigest()
        text = text.replace(match, "<div class='picture text-center'><img src='/static/latex/{}.png'></div>".format(name))
        if not os.path.isfile("{}/{}.png".format(TEX_ROOT,name)):
            with io.open('{}.tex'.format(name),"w") as f:
                print(match, file=f)
            os.system('{} {}.tex'.format(latex, name))
            os.system('{} {}.dvi'.format(dvips, name))
            os.system('{} {}.ps {}.png'.format(convert, name,name))
            #os.system('rm *.tex *.ps *.dvi *.log *.aux')

    matches=re.findall(r'\[psti\](.*?)\[/psti\]',text, re.MULTILINE|re.DOTALL)
    for match in matches:
        match = match.strip()
        result = hashlib.md5(match.encode())
        name = result.hexdigest()
        text = text.replace(match, "<span class='inline-picture'><img src='/static/latex/{}.png'></span>".format(name))
        if not os.path.isfile("{}/{}.png".format(TEX_ROOT,name)):
            with io.open('{}.tex'.format(name),"w") as f:
                print(match, file=f)
            os.system('{} {}.tex'.format(latex, name))
            os.system('{} {}.dvi'.format(dvips, name))
            os.system('{} {}.ps {}.png'.format(convert, name,name))
            os.system('rm *.tex *.ps *.dvi *.log *.aux')
    text = re.sub(r'\[(/*)pst(i*)\](\n*)','',text)
    return text


def multicol2fix(text):
    text.replace("[multicols=2]", "<div style='-webkit-column-count: 2;-moz-column-count: 2;column-count: 2;'>")
    text.replace("[multicols=3]", "<div style='-webkit-column-count: 2;-moz-column-count: 2;column-count: 3;'>")
    text.replace("[multicols=4]", "<div style='-webkit-column-count: 2;-moz-column-count: 2;column-count: 4;'>")
    text.replace("[multicols=5]", "<div style='-webkit-column-count: 2;-moz-column-count: 2;column-count: 5;'>")
    text.replace("[/multicols]", "</div>")
    return text
