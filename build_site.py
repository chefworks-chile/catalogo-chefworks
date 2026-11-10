#!/usr/bin/env python3
"""Genera index.html e img/ del catálogo desde chefworks.cl (para GitHub Pages)."""
import os, sys, json, shutil, subprocess, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'scripts')
W = tempfile.mkdtemp(prefix='cw_')
for f in ('update.py', 'head.html', 'body.html', 'logo.png', 'logo-dark.png'):
    shutil.copy(os.path.join(SRC, f), W)
res = subprocess.run([sys.executable, '-I', os.path.join(W, 'update.py')], env={**os.environ, 'W': W}, capture_output=True, text=True)
print(res.stdout[-3000:]); print(res.stderr[-3000:], file=sys.stderr)
if res.returncode != 0: sys.exit('Error al leer chefworks.cl; no se publica nada.')
resumen = json.loads(res.stdout[res.stdout.index('{'):])
page = os.path.join(W, 'pub', 'catalogo-chefworks.html')
if resumen.get('productos', 0) < 100 or os.path.getsize(page) < 100_000:
    sys.exit(f"Datos incompletos ({resumen.get('productos')} productos); no se publica nada.")
html = open(page, encoding='utf-8').read()
head, rest = html.split('</style>', 1)
doc = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       '<meta name="robots" content="noindex">\n<link rel="icon" href="img/logo.png">\n<link rel="apple-touch-icon" href="img/logo.png">\n'
       '<meta name="apple-mobile-web-app-title" content="Catálogo Chef Works">\n'
       '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font-size:14px}img{max-width:100%}[hidden]{display:none!important}</style>\n'
       + head + '</style>\n</head>\n<body>\n' + rest + '\n</body>\n</html>\n')
open(os.path.join(REPO, 'index.html'), 'w', encoding='utf-8').write(doc)
os.makedirs(os.path.join(REPO, 'img'), exist_ok=True)
for f in os.listdir(os.path.join(W, 'pub', 'img')):
    shutil.copy(os.path.join(W, 'pub', 'img', f), os.path.join(REPO, 'img', f))
for extra in ('portada.jpg', 'logo-white.png'):
    for cand in (os.path.join(REPO, extra), os.path.join(SRC, extra)):
        if os.path.exists(cand):
            shutil.copy(cand, os.path.join(REPO, 'img', extra)); break
print('Catálogo generado:', resumen.get('productos'), 'productos,', resumen.get('fecha'))
