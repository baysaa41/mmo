from django import template
import re, hashlib, io, os

register = template.Library()


@register.filter(name='pst')
def pst(value):
    return pst2png(value)

def pst2png(text):
    TEX_ROOT = "/home/deploy/django/mmo/static/latex"
    latex = '/usr/bin/latex'
    dvips = '/usr/bin/dvips'
    convert = 'convert -density 140 -trim -transparent \"#FFFFFF\"'
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
            # os.system('rm *.tex *.ps *.dvi *.log *.aux')

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
