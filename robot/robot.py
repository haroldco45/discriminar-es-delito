"""Robot de Vibras Positivas HM - volumen "Discriminar es delito".
- Noticias reales (Google News RSS) del caso Carabalí y de discriminación en Colombia -> noticias.json
- Fotos reales con licencia libre de Wikimedia Commons -> img/foto-N.jpg + img/creditos.json (se renuevan cada 7 días)
- Imagen de vista previa (og-image.jpg) con foto real de fondo + afiche
Corre en GitHub Actions cada 30 minutos. Solo cambia archivos si hay novedades.
Uso local: python robot/robot.py --solo-og
"""
import json, os, re, sys, html, urllib.request, urllib.parse, datetime, email.utils
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOG = datetime.timezone(datetime.timedelta(hours=-5))
UA = {"User-Agent": "VibrasPositivasHM-robot/1.0 (https://haroldco45.github.io/discriminar-es-delito/)"}

CONSULTAS = [
    '"Carabalí" racismo Cali',
    '"Jazlí" OR "Jazli" Carabalí',
    'discriminación racial Colombia',
    '"Ley 1482" discriminación',
]
FOTOS = [
    "Afro-Colombian people Cali",
    "Petronio Álvarez festival Cali",
    "Policía Nacional de Colombia mujeres",
    "San Basilio de Palenque",
    "Cali Colombia panorama",
    "Afrocolombianos",
]


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def noticias():
    path = os.path.join(ROOT, "noticias.json")
    try:
        actual = json.load(open(path, encoding="utf-8"))
    except Exception:
        actual = {"noticias": []}
    items = list(actual.get("noticias", []))
    vistos = {re.sub(r"\W+", "", n["titulo"].lower())[:60] for n in items}
    nuevos = 0
    for q in CONSULTAS:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": q + " when:30d", "hl": "es-419", "gl": "CO", "ceid": "CO:es-419"})
        try:
            root = ET.fromstring(get(url))
        except Exception as e:
            print("RSS falló", q, e)
            continue
        for it in root.iter("item"):
            titulo = html.unescape(it.findtext("title") or "")
            fuente = it.findtext("source") or ""
            if fuente and titulo.endswith(" - " + fuente):
                titulo = titulo[: -len(fuente) - 3]
            k = re.sub(r"\W+", "", titulo.lower())[:60]
            if not titulo or k in vistos:
                continue
            try:
                f = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(BOG).isoformat()
            except Exception:
                f = datetime.datetime.now(BOG).isoformat()
            vistos.add(k)
            items.append({"titulo": titulo, "url": it.findtext("link"), "fuente": fuente, "fecha": f})
            nuevos += 1
    items.sort(key=lambda n: n["fecha"], reverse=True)
    items = items[:40]
    if nuevos:
        json.dump({"actualizado": datetime.datetime.now(BOG).isoformat(timespec="seconds"), "noticias": items},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Noticias nuevas:", nuevos)


def fotos():
    os.makedirs(os.path.join(ROOT, "img"), exist_ok=True)
    cpath = os.path.join(ROOT, "img", "creditos.json")
    try:
        c = json.load(open(cpath, encoding="utf-8"))
        hecho = datetime.datetime.fromisoformat(c["fecha"])
        if (datetime.datetime.now(BOG) - hecho).days < 7 and len(c.get("fotos", [])) >= 4:
            print("Fotos al día")
            return False
    except Exception:
        pass
    lista, usadas = [], set()
    for term in FOTOS:
        if len(lista) >= 6:
            break
        api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "search", "gsrsearch": term,
            "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600})
        try:
            pages = json.loads(get(api)).get("query", {}).get("pages", {})
        except Exception as e:
            print("Commons falló", term, e)
            continue
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 900 or p["title"] in usadas:
                continue
            md = ii.get("extmetadata", {})
            lic = re.sub("<[^>]+>", "", md.get("LicenseShortName", {}).get("value", ""))
            if not re.search(r"CC|Public domain|PD", lic, re.I):
                continue
            autor = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()[:60]
            n = len(lista) + 1
            try:
                data = get(ii["thumburl"])
            except Exception:
                continue
            arch = f"img/foto-{n}.jpg"
            open(os.path.join(ROOT, arch), "wb").write(data)
            lista.append({"archivo": arch, "titulo": p["title"].replace("File:", ""), "autor": autor,
                          "licencia": lic, "fuente": ii.get("descriptionurl")})
            usadas.add(p["title"])
            break
    if not lista:
        return False
    json.dump({"fecha": datetime.datetime.now(BOG).isoformat(timespec="seconds"), "fotos": lista},
              open(cpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Fotos:", len(lista))
    return True


def og(foto=None):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    W, H = 1200, 630
    if foto and os.path.exists(foto):
        bg = Image.open(foto).convert("RGB")
        r = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1))
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
        bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(2))).enhance(0.38)
    else:
        bg = Image.new("RGB", (W, H), "#0f1b3d")
    tint = Image.new("RGB", (W, H), "#0f1b3d")
    bg = Image.blend(bg, tint, 0.35)
    d = ImageDraw.Draw(bg)
    d.rectangle([0, H - 14, W // 2, H], fill="#f2c14e")
    d.rectangle([W // 2, H - 14, W * 3 // 4, H], fill="#1d3474")
    d.rectangle([W * 3 // 4, H - 14, W, H], fill="#d7263d")

    def font(names, size):
        for n in names:
            for base in ["/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/opentype/inter/",
                         "/usr/share/fonts/truetype/", ""]:
                try:
                    return ImageFont.truetype(base + n, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    bold = ["Inter-Bold.otf", "DejaVuSans-Bold.ttf"]
    serif = ["DejaVuSerif-Bold.ttf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf"]
    reg = ["Inter-Medium.otf", "DejaVuSans.ttf"]
    d.rounded_rectangle([60, 58, 470, 100], 20, fill="#d7263d")
    d.text((82, 66), "BIBLIOTECA LEGAL COLOMBIANA", font=font(bold, 21), fill="white")
    d.text((60, 140), "Discriminar", font=font(serif, 86), fill="white")
    d.text((60, 238), "es delito", font=font(serif, 86), fill="#f2c14e")
    d.text((62, 360), "Ley 1482 de 2011 · prisión de 12 a 36 meses", font=font(reg, 31), fill="#e6ebf7")
    d.text((62, 404), "Multas 2026 · qué hacer · derecho de petición", font=font(reg, 31), fill="#e6ebf7")
    d.text((62, 520), "Vibras Positivas HM · Caso Jazlí Tatiana Carabalí", font=font(bold, 24), fill="#f2c14e")
    afiche = os.path.join(ROOT, "img", "afiche-solidaridad.jpg")
    if os.path.exists(afiche):
        a = Image.open(afiche).convert("RGB")
        h = 540
        a = a.resize((int(a.width * h / a.height), h))
        m = Image.new("L", a.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, a.width, a.height], 22, fill=255)
        sh = Image.new("RGBA", (a.width + 40, a.height + 40), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([20, 26, a.width + 20, a.height + 26], 22, fill=(0, 0, 0, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(12))
        x = W - a.width - 70
        bg.paste(sh, (x - 20, 24), sh)
        bg.paste(a, (x, 38), m)
    bg.save(os.path.join(ROOT, "og-image.jpg"), quality=86, optimize=True)
    print("OG lista")


if __name__ == "__main__":
    if "--solo-og" in sys.argv:
        og()
        sys.exit()
    noticias()
    cambio = fotos()
    ogp = os.path.join(ROOT, "og-image.jpg")
    if cambio or not os.path.exists(ogp):
        og(os.path.join(ROOT, "img", "foto-1.jpg"))
