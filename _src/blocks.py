"""HTML for each content block type. All markup of the page body lives here."""
import re


def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(s):
    return esc_text(s).replace('"', "&quot;")


def indent(lines, n=1):
    return ["    " * n + l for l in lines]


class Ctx:
    """What a block needs to know about the page it is rendered into."""
    def __init__(self, shots_dir, root, site_url, badge_file, badge_alt, app_store_url, contact, contact_lang):
        self.shots_dir, self.root, self.site_url = shots_dir, root, site_url
        self.badge_file, self.badge_alt, self.app_store_url = badge_file, badge_alt, app_store_url
        self.contact, self.contact_lang = contact, contact_lang


def inline(text, ctx):
    s = esc_text(text)
    link = lambda url, label: f'<a href="{url}" target="_blank" rel="noopener" class="contact-link">{label}</a>'
    s = re.sub(r"\[([^\]]+)\]\((https://[^)]+)\)", lambda m: link(m.group(2), m.group(1)), s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s.replace("{site_link}", link(ctx.site_url, ctx.site_url.removeprefix("https://")))


def screenshot(shot, ctx):
    cls = "app-screenshot dark" if shot.get("dark") else "app-screenshot"
    return (f'<img src="{ctx.root}images/screenshots/{ctx.shots_dir}/{shot["name"]}.webp" '
            f'alt="{esc_attr(shot["alt"])}" class="{cls}">')


def badge(ctx):
    return [f'<a href="{ctx.app_store_url}" target="_blank" rel="noopener">',
            f'    <img src="{ctx.root}images/badges/{ctx.badge_file}" alt="{esc_attr(ctx.badge_alt)}" class="download-cta-badge">',
            '</a>']


def contact_box(ctx):
    c, l = ctx.contact, ctx.contact_lang
    tel = "tel:" + c["phone"].replace(" ", "")
    lines = [f'<strong>{esc_text(c["organization"])}</strong><br><br>', f'{esc_text(c["person"])}<br>']
    lines += [f"{esc_text(a)}<br>" for a in c["address"]]
    lines += [f'{esc_text(l["country"])}<br><br>',
              f'<strong>{esc_text(l["phone_label"])}</strong> <a href="{tel}" class="contact-link">{esc_text(c["phone"])}</a><br>',
              f'<strong>{esc_text(l["email_label"])}</strong> <a href="mailto:{c["email"]}" class="contact-link">{esc_text(c["email"])}</a>']
    return ['<div class="contact-box">', '    <p>'] + indent(lines, 2) + ['    </p>', '</div>']


def element(el, ctx):
    t = el["type"]
    if t == "p":
        return [f'<p>{inline(el["text"], ctx)}</p>']
    if t == "h3":
        return [f'<h3>{esc_text(el["text"])}</h3>']
    if t == "list":
        return ["<ul>"] + indent([f"<li>{inline(i, ctx)}</li>" for i in el["items"]]) + ["</ul>"]
    return contact_box(ctx)


def hero(b, ctx):
    out = [f'<h1>{esc_text(b["heading"])}</h1>']
    if "subtitle" in b:
        out.append(f'<p class="subtitle">{inline(b["subtitle"], ctx)}</p>')
    if b.get("screenshots"):
        out.append('<div class="hero-visual-double">')
        for role, shot in zip(["primary", "secondary"], b["screenshots"]):
            out += indent([f'<div class="screenshot-wrapper {role}">', "    " + screenshot(shot, ctx), "</div>"])
        out.append("</div>")
    return out


def section(b, ctx):
    out = ['<section>' if b.get("divider", True) else '<section class="no-divider">']
    body = [f'<h2>{esc_text(b["heading"])}</h2>'] if "heading" in b else []
    for el in b["content"]:
        body += element(el, ctx)
    return out + indent(body) + ["</section>"]


def download(b, ctx):
    return (['<section class="download-cta">', '    <div class="download-cta-box">',
             f'        <p class="download-text">{inline(b["text"], ctx)}</p>']
            + indent(badge(ctx), 2) + ['    </div>', '</section>'])


def final_cta(b, ctx):
    return ['<div class="final-cta">'] + indent(badge(ctx)) + ['</div>']


def feature(b, ctx):
    items = []
    for it in b["items"]:
        items += [f'<h3>{esc_text(it["title"])}</h3>', f'<p>{inline(it["text"], ctx)}</p>']
    split = "feature-split reverse" if b.get("reverse") else "feature-split"
    return (['<section class="feature-block">', '    <div class="feature-header">',
             f'        <h2>{esc_text(b["heading"])}</h2>', f'        <p>{inline(b["intro"], ctx)}</p>', '    </div>',
             f'    <div class="{split}">', '        <div class="feature-text">']
            + indent(items, 3)
            + ['        </div>', '        <div class="feature-image">', "            " + screenshot(b["screenshot"], ctx),
               '        </div>', '    </div>', '</section>'])


TRUST_CLASS = {"default": "trust-statement", "feature": "feature-block trust-statement", "last": "trust-statement last-section"}


def trust(b, ctx):
    body = [f'<h2>{esc_text(b["heading"])}</h2>']
    if "emphasis" in b:
        body.append(f'<p class="emphasized"><strong>{esc_text(b["emphasis"])}</strong></p>')
    body += [f'<p>{inline(p, ctx)}</p>' for p in b["paragraphs"]]
    return ([f'<section class="{TRUST_CLASS[b.get("variant", "default")]}">', '    <div class="container-small">']
            + indent(body, 2) + ['    </div>', '</section>'])


RENDERERS = {"hero": hero, "section": section, "download": download, "final_cta": final_cta,
             "feature": feature, "trust": trust}


def render_blocks(blocks, ctx):
    out = []
    for b in blocks:
        out += RENDERERS[b["type"]](b, ctx)
    return "\n".join(out)
