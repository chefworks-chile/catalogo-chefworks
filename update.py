#!/usr/bin/env python3
"""Actualiza el catálogo Chef Works desde chefworks.cl.
Uso: W=/ruta/trabajo python3 update.py
Genera en W: catalog.json, img/*.webp, jpg/*.jpg, hi/*.jpg, pub/ (página + packs de imágenes)
"""
import os, re, json, html, base64, io, unicodedata, datetime, concurrent.futures as cf
import requests
from bs4 import BeautifulSoup
from PIL import Image

W = os.environ.get('W', os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://chefworks.cl'
CDN = 'https://cdnx.jumpseller.com/chefworks/image'
S = requests.Session()
S.headers['User-Agent'] = 'Mozilla/5.0 (catalogo ICB)'

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)  # Chile (aprox.)
FECHA_LARGA = f'{now.day} de {MESES[now.month-1]} de {now.year}'
FECHA_CORTA = f'{now.day} {MESES[now.month-1][:3]} {now.year}'

CATS = [
 ['Chaquetas','Unisex manga larga','/chaquetas/chaquetas-unisex-manga-larga'],['Chaquetas','Unisex manga corta','/chaquetas-unisex-manga-corta'],['Chaquetas','Mujer manga larga','/chaqueta-mujer-manga-larga'],['Chaquetas','Mujer manga corta','/chaquetas-mujer-manga-corta'],['Chaquetas','Casual','/chaquetas/casual'],['Chaquetas','Otras','/chaquetas'],
 ['Pantalones','Unisex','/pantalon-unisex'],['Pantalones','Mujer','/pantalon-mujer'],['Pantalones','Otros','/pantalones'],
 ['Pecheras y Mandiles','Pecheras','/pecheras-y-mandiles/pecheras'],['Pecheras y Mandiles','Mandiles','/pecheras-y-mandiles/mandiles'],['Pecheras y Mandiles','Otros','/pecheras-y-mandiles'],
 ['Gorros','Gorros de chef','/gorro-linea'],['Gorros','Beanies','/beanies'],['Gorros','Bandanas','/gorros/bandanas'],['Gorros','Jockeys','/gorros/jockey'],['Gorros','Otros','/gorros'],
 ['Calzado','Zuecos','/zuecos'],['Calzado','Zapatillas','/zapatillas'],['Calzado','Otros','/calzado'],
 ['Accesorios','Accesorios','/accesorios'],
 ['Horeca','Camisas','/uniformes-hoteleria-restaurantes-casinos/camisas-2'],['Horeca','Blusas','/blusas'],['Horeca','Chalecos','/uniformes-hoteleria-restaurantes-casinos/chalecos-2'],['Horeca','Otros','/horeca'],
 ['Kit Estudiantes','INACAP','/uniformes-para-alumnos/inacap-3'],['Kit Estudiantes','Culinary','/uniformes-para-alumnos/culinary'],['Kit Estudiantes','Otros institutos / liceos','/uniformes-para-alumnos/todo-institutos'],['Kit Estudiantes','Servicio','/uniformes-para-alumnos/servicio'],['Kit Estudiantes','Otros','/uniformes-para-alumnos'],
 ['Sale','Sale','/sale']]
ORDER = ['Chaquetas','Poleras','Pantalones','Pecheras y Mandiles','Gorros','Calzado','Horeca','Accesorios','Kit Estudiantes']

def to_rgb(data):
    im = Image.open(io.BytesIO(data))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3]); return bg
    return im.convert('RGB')

def get(url):
    for _ in range(3):
        try:
            r = S.get(url, timeout=40)
            if r.status_code == 200: return r
        except Exception: pass
    raise RuntimeError('No se pudo descargar ' + url)

# 1) Recorrer categorías
cmap = {}
for c, s, u in CATS:
    pg = 1
    while pg < 20:
        soup = BeautifulSoup(get(BASE + u + f'?page={pg}').text, 'html.parser')
        arts = soup.select('article.product-block')
        hs = []
        for a in arts:
            l = a.select_one('a.product-block__anchor, a.product-block__name')
            if l and l.get('href'): hs.append(l['href'].split('?')[0])
        for h in hs:
            cmap.setdefault(h, [])
            if [c, s] not in cmap[h]: cmap[h].append([c, s])
        if not hs or not soup.select_one(f'a[href*="page={pg+1}"]'): break
        pg += 1
print('productos encontrados', len(cmap))

# 2) Fichas de producto
def _ldprice(ld):
    o = ld.get('offers') or {}
    if isinstance(o, list): o = o[0] if o else {}
    for k in ('price', 'lowPrice'):
        try: return float(o.get(k))
        except Exception: pass
    return 0
def parse(url):
    t = get(BASE + url).text
    soup = BeautifulSoup(t, 'html.parser')
    scripts = [x.string or x.get_text() for x in soup.find_all('script') if not x.get('src')]
    scripts = [x.strip() for x in scripts if x]
    variants = []
    vs = next((x for x in scripts if x.startswith('[{"variant"')), None)
    if vs:
        try: variants = json.loads(vs)
        except Exception: variants = []
    options, sku, name = [], '', ''
    ps = next((x for x in scripts if '"add_to_cart_url"' in x), '')
    m = re.search(r'"options":\s*(\[.*\]),\s*\n', ps)
    if m:
        try: options = json.loads(m.group(1))
        except Exception: pass
    m = re.search(r'"sku":\s*"([^"]*)"', ps); sku = m.group(1).strip() if m else ''
    m = re.search(r'"name":\s*"((?:[^"\\]|\\.)*)"', ps); name = json.loads('"' + m.group(1) + '"').strip() if m else ''
    pp = None
    mp = re.search(r'"product":\s*\{\s*"id":\s*\d+,\s*"price":\s*([\d.]+),\s*"status":\s*"\w+",\s*"discount":\s*([\d.]+)', next((x for x in scripts if '"percentage_off"' in x), ''))
    if mp: pp = (float(mp.group(1)), float(mp.group(2)))
    ms = re.search(r'"stock":\s*(\d+),[\s\S]*?"stock_unlimited":\s*(true|false)', ps)
    pstock = (int(ms.group(1)) > 0 or ms.group(2) == 'true') if ms else None
    disc = {}
    pr = next((x for x in scripts if '"percentage_off"' in x and '"variants"' in x), '')
    for vid, price, d in re.findall(r'"id":\s*(\d+),\s*"price":\s*([\d.]+),\s*"status":\s*"\w+",\s*"discount":\s*([\d.]+)', pr):
        disc[int(vid)] = float(price) - float(d)
    bc, ld = [], {}
    for x in soup.find_all('script', type='application/ld+json'):
        try:
            j = json.loads(x.get_text())
            for o in (j if isinstance(j, list) else [j]):
                if o.get('@type') == 'BreadcrumbList': bc = [e['item']['name'].strip() for e in o['itemListElement']]
                if o.get('@type') == 'Product': ld = o
        except Exception: pass
    de = soup.select_one('.product-page__description, [class*="product-description"], [class*=description]')
    feats = [li.get_text(' ', strip=True) for li in de.find_all('li')] if de else []
    feats = [f for f in feats if f]
    dtext = re.sub(r'\s+', ' ', de.get_text(' ')) if de else ''
    imgs = []
    for im in soup.find_all('img'):
        m = re.search(r'cdnx\.jumpseller\.com/chefworks/image/(\d+)', im.get('src') or '')
        if m and int(m.group(1)) not in imgs: imgs.append(int(m.group(1)))
    mi = re.search(r'/image/(\d+)', ld.get('image', '') or '')
    return dict(url=url, name=name or (ld.get('name') or '').strip(), sku=sku or ld.get('sku') or '', bc=bc, options=options,
                variants=variants, disc=disc, pp=pp, pstock=pstock, ldp=_ldprice(ld), feats=feats, dtext=dtext, imgs=imgs, main=int(mi.group(1)) if mi else (imgs[0] if imgs else None))

with cf.ThreadPoolExecutor(6) as ex:
    raw = list(ex.map(parse, list(cmap)))
print('fichas leídas', len(raw))

# 3) Normalizar
def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')
BOIL = re.compile(r'¿Personalizas esta prenda\?.*?(agregar también la Matriz\.|$)')
out, seen = [], set()
for r in raw:
    name = re.sub(r'\s+', ' ', r['name']).strip()
    cats = cmap[r['url']]
    real = [c for c in cats if c[0] != 'Sale']
    prim = None
    if name.lower().startswith('polera'):
        prim = ('Poleras', '')
    else:
        for sec in ORDER:
            subs = [c[1] for c in real if c[0] == sec and c[1] not in ('Otros', 'Otras')]
            if any(c[0] == sec for c in real):
                prim = (sec, subs[0] if subs else ''); break
    if not prim:
        prim = ('Chaquetas', '') if 'chaqueta' in name.lower() else ('Accesorios', '')
    kit = sorted({c[1] for c in cats if c[0] == 'Kit Estudiantes' and c[1] != 'Otros'})
    if any(c[0] == 'Kit Estudiantes' for c in cats) and not kit: kit = ['General']
    opts = r['options']
    copt = next((o for o in opts if o.get('type') == 'color'), None) or next((o for o in opts if 'color' in o.get('name', '').lower()), None)
    sopt = next((o for o in opts if o is not copt and o.get('name', '').lower().startswith('talla')), None)
    ci = opts.index(copt) if copt else -1
    si = opts.index(sopt) if sopt else -1
    sizes = [v['name'] for v in sopt['values']] if sopt else []
    V = []
    for v in r['variants']:
        vals = [x['value']['name'] for x in v.get('values', [])]
        vv = v['variant']
        V.append(dict(vals=vals, c=(vals[ci].strip() if ci >= 0 and ci < len(vals) else ''), s=(vals[si] if si >= 0 and si < len(vals) else ''),
                      p=float(v['price']), e=r['disc'].get(vv['id'], float(v['price'])),
                      ok=bool(vv.get('stock_unlimited')) or (vv.get('stock') or 0) > 0, img=v.get('image_id')))
    # precios
    regs = [x['p'] for x in V] or [0]
    pmin, pmax = min(regs), max(regs)
    by_color = {}
    for x in V: by_color.setdefault(x['c'], set()).add(x['p'])
    vc = bool(copt) and pmax > pmin and all(len(s) == 1 for s in by_color.values())
    disc_v = [x for x in V if x['e'] < x['p'] - 0.5]
    pct, sp, po = 0, None, None
    if V and disc_v and len(disc_v) == len(V) and len({round(x['e'] / x['p'], 3) for x in V}) == 1:
        pct = round(100 * (1 - V[0]['e'] / V[0]['p'])); sp = round(min(x['e'] for x in V))
    elif disc_v:
        e0 = round(min(x['e'] for x in disc_v)); p0 = disc_v[0]['p']
        pctp = round(100 * (1 - e0 / p0))
        dcols = sorted({x['c'] for x in disc_v})
        full_cols = [c for c in dcols if all(x['e'] < x['p'] - 0.5 for x in V if x['c'] == c)]
        allc = [v['name'].strip() for v in copt['values']] if copt else []
        if copt and len(full_cols) == len(dcols):
            rest = [c for c in allc if c not in dcols]
            t = ('en todos los colores excepto ' + ', '.join(rest)) if rest and len(rest) < len(dcols) else ('solo en ' + ', '.join(dcols))
        else:
            t = 'solo en ' + ', '.join(f"{x['c']} talla {x['s']}".strip() for x in disc_v[:6]) + (' y otras' if len(disc_v) > 6 else '')
        po = dict(e=e0, pct=pctp, t=t, v=[f"{x['c']}|{x['s']}" for x in disc_v])
    if not V and not r['pp'] and r.get('ldp'):
        pmin = pmax = r['ldp']
    if not V and r['pp']:
        pmin = pmax = r['pp'][0]
        if r['pp'][1] > 0:
            sp = round(r['pp'][0] - r['pp'][1]); pct = round(100 * r['pp'][1] / r['pp'][0])
    if not vc and not pct and not po and pmax > pmin:
        pmax = pmin  # varía por opción (ej. bolso), se muestra precio base
    # colores
    colors = []
    if copt:
        for v in copt['values']:
            cn = v['name'].strip()
            mine = [x for x in V if x['c'] == cn]
            img = next((x['img'] for x in mine if x['img']), None)
            av = [x['s'] for x in mine if x['ok']]
            colors.append(dict(n=cn, h=v.get('custom') or '#cccccc', i=img, s=[s for s in sizes if s in av], a=any(x['ok'] for x in mine),
                               **({'pr': round(mine[0]['p'])} if vc and mine else {})))
    avs = sorted({x['s'] for x in V if x['ok'] and x['s']}, key=lambda s: sizes.index(s) if s in sizes else 99) if not copt else []
    extra = [dict(n=o['name'], v=[v['name'] for v in o['values']]) for o in opts if o is not copt and o is not sopt]
    st = ('na' if r['pstock'] is None else ('ok' if r['pstock'] else 'out')) if not V else ('ok' if any(x['ok'] for x in V) else 'out')
    g = 'Mujer' if re.search(r'\bmujer\b', name, re.I) else ('Unisex' if re.search('unisex', name, re.I) else '')
    d = BOIL.sub('', r['dtext'].replace('Descripción', '', 1)).replace('Ver guía de tallas', '').strip()
    m = re.search(r'Ajuste [A-ZÁÉÍÓÚ][a-záéíóúñ]+', d); fit = m.group(0) if m else ''
    if r['feats']:
        for f in r['feats']: d = d.replace(f, '')
        d = ''
    sid = slug(r['url'].lstrip('/').split('/')[0]); b0, k = sid, 2
    while sid in seen: sid = f'{b0}-{k}'; k += 1
    seen.add(sid)
    p = round(pmin)
    rec = dict(id=sid, u=BASE + r['url'], n=name, s=(r['sku'] or '').strip(), sec=prim[0], sub=prim[1], kit=kit,
               sale=bool(pct or po) or any(c[0] == 'Sale' for c in cats), g=g, p=p, px=round(pmax), pct=pct, sp=sp,
               c=colors, sz=sizes, avs=avs, x=extra, st=st, fit=fit, d=d[:900], f=r['feats'], img=r['main'],
               imgs=[i for i in r['imgs'] if i][:4], vc=vc)
    if po: rec['po'] = po
    rec['ep'] = sp if (pct and sp) else p
    out.append(rec)
out.sort(key=lambda x: (ORDER.index(x['sec']), x['sub'], x['ep'] or 0))

# 4) Imágenes
for dname in ('img', 'jpg', 'hi', 'pub/img'): os.makedirs(f'{W}/{dname}', exist_ok=True)
ids = []
for x in out:
    for i in [x['img']] + [c['i'] for c in x['c']] + x['imgs']:
        if i and i not in ids: ids.append(i)
def fetch_img(i):
    if os.path.exists(f'{W}/img/{i}.webp') and os.path.exists(f'{W}/jpg/{i}.jpg'): return i, True
    try:
        im = to_rgb(get(f'{CDN}/{i}/resize/360/540').content)
        im.save(f'{W}/img/{i}.webp', 'WEBP', quality=72)
        im.save(f'{W}/jpg/{i}.jpg', 'JPEG', quality=80, optimize=True)
        return i, True
    except Exception:
        return i, False
with cf.ThreadPoolExecutor(8) as ex:
    res = dict(ex.map(fetch_img, ids))
bad = {i for i, ok in res.items() if not ok}
for x in out:
    if x['img'] in bad: x['img'] = next((i for i in x['imgs'] if i not in bad), None)
    x['imgs'] = [i for i in x['imgs'] if i not in bad]
    for c in x['c']:
        if c['i'] in bad: c['i'] = None
for i in (76840238, 76773829, 76674273):
    if not os.path.exists(f'{W}/hi/{i}.jpg'):
        try: to_rgb(get(f'{CDN}/{i}/resize/900/1350').content).save(f'{W}/hi/{i}.jpg', 'JPEG', quality=82)
        except Exception: pass
json.dump(out, open(f'{W}/catalog.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# 5) Página web + packs
used = [i for i in ids if i not in bad]
main = []
for x in out:
    if x['img'] and x['img'] not in main: main.append(x['img'])
rest = [i for i in used if i not in main]
def pack(lst, fn):
    json.dump({str(i): base64.b64encode(open(f'{W}/img/{i}.webp', 'rb').read()).decode() for i in lst}, open(f'{W}/pub/img/{fn}', 'w'), separators=(',', ':'))
pack(main, 'main.json')
k = (len(rest) + 2) // 3
for j in range(3): pack(rest[j*k:(j+1)*k], f'more-{j+1}.json')
for f in ('logo.png', 'logo-dark.png'):
    open(f'{W}/pub/img/{f}', 'wb').write(open(f'{W}/{f}', 'rb').read())
for i in (76840238, 76773829, 76674273):
    if os.path.exists(f'{W}/hi/{i}.jpg'): open(f'{W}/pub/img/cover-{i}.jpg', 'wb').write(open(f'{W}/hi/{i}.jpg', 'rb').read())
head = open(f'{W}/head.html').read(); body = open(f'{W}/body.html').read()
body = body.replace('__FECHA_LARGA__', FECHA_LARGA).replace('__FECHA_CORTA__', FECHA_CORTA)
data = json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
open(f'{W}/pub/catalogo-chefworks.html', 'w').write(head + body.replace('__DATA__', data))
open(f'{W}/fecha.txt', 'w').write(FECHA_LARGA)
print(json.dumps(dict(productos=len(out), imagenes=len(used), sin_imagen=len(bad), fecha=FECHA_LARGA,
                      ofertas=sum(x['sale'] for x in out), por_color=[x['n'] for x in out if x['vc']],
                      ofertas_parciales=[(x['n'], x['po']['t']) for x in out if x.get('po')]), ensure_ascii=False, indent=1))
