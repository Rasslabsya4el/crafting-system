"""The route view as one HTML page: `render_page(page) -> str`.

Self-contained HTML5: the style is inline and follows the accepted prototype (light and dark by
`prefers-color-scheme`), there is no script, no external file and no font or CDN, so the page opens offline.
Every text goes through `html.escape`. The only address in the page is the trade search link of a buy
step, opened by the owner (`rel="noopener noreferrer" target="_blank"`); the program never requests it.
Rows are `.rw` grids: the step card (`id` = the row's anchor) on the left, the item card of the state after
it on the right, `↓` between rows. The goal card and the target item card are the top row, a `.tg` border
marks the target and the final state. Deterministic: the same page model gives the same bytes.
"""

from html import escape

from ._route_card import ItemCard, Slot

CSS = """\
:root{--text-primary:#1f1e1d;--text-secondary:#5f5e5a;--text-muted:#6b6a64;--text-warning:#854f0b;--text-success:#27500a;--text-accent:#3c3489;--text-link:#1a5fb4;
--bg-success:#eaf3de;--bg-accent:#eeedfe;--border:#d3d1c7;--border-success:#97c459;--border-accent:#afa9ec;--border-warning:#ef9f27;--surface-0:#ffffff;--surface-1:#f8f7f3}
@media (prefers-color-scheme: dark){:root{--text-primary:#f1efe8;--text-secondary:#b4b2a9;--text-muted:#9c9a92;--text-warning:#fac775;--text-success:#c0dd97;--text-accent:#cecbf6;--text-link:#8ab4f8;
--bg-success:#173404;--bg-accent:#26215c;--border:#444441;--border-success:#3b6d11;--border-accent:#534ab7;--border-warning:#854f0b;--surface-0:#1f1e1d;--surface-1:#2c2c2a}}
body{margin:0;padding:16px;background:var(--surface-0);color:var(--text-primary);font-family:system-ui,sans-serif}
main{max-width:980px;margin:0 auto}
h1{font-size:18px;font-weight:500;margin:0 0 8px}
h2{font-size:16px;font-weight:500;margin:22px 0 10px}
nav{font-size:12px;margin:0 0 6px;display:flex;gap:12px}
a{color:var(--text-link)}
.rw{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:10px;align-items:start}
@media (max-width:640px){.rw{grid-template-columns:1fr}}
.cd{border:0.5px solid var(--border);border-radius:12px;padding:10px 12px;background:var(--surface-1);font-size:12px;line-height:1.45}
.cd h3{font-size:14px;font-weight:500;margin:0 0 6px}
.f{display:grid;grid-template-columns:104px minmax(0,1fr);gap:4px 8px}
.k{color:var(--text-muted)}.v{color:var(--text-primary)}.vl{color:var(--text-warning)}
.nm{font-size:13px;font-weight:500;margin-bottom:3px}
.pr{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px}
.pl{font-size:11px;border:0.5px solid var(--border);border-radius:4px;padding:0 5px;color:var(--text-secondary)}
.sd{font-size:11px;color:var(--text-muted);margin:5px 0 2px}
.s{font-size:12px;padding:2px 7px;border-radius:6px;margin:2px 0;border:0.5px solid var(--border)}
.w{background:var(--bg-success);color:var(--text-success);border-color:var(--border-success)}
.c{background:var(--bg-accent);color:var(--text-accent);border-color:var(--border-accent)}
.m{color:var(--text-primary)}
.a{color:var(--text-secondary)}.e{border-style:dashed;color:var(--text-muted);background:transparent}.i{color:var(--text-secondary);background:transparent}
.n{opacity:.85}
.b{font-size:11px;border:0.5px solid var(--border-warning);color:var(--text-warning);border-radius:4px;padding:0 4px;margin-left:4px}
.ar{text-align:center;color:var(--text-muted);font-size:14px;margin:2px 0}
.tg{border:1px solid var(--border-success)}.ml div{margin:1px 0}
"""

_TONES = {"wanted": "w", "mod": "m", "crafted": "c", "any": "a", "empty": "e", "implicit": "i"}


def _link(href: str, text: str, external: bool = False) -> str:
    rel = ' rel="noopener noreferrer" target="_blank"' if external else ""
    return f'<a href="{escape(href, quote=True)}"{rel}>{escape(text)}</a>'


def _line(line) -> str:
    if line.href is None:
        return escape(line.text)
    external = not line.href.startswith("#")
    if line.anchor:
        return f"{escape(line.text)} {_link(line.href, line.anchor, external)}"
    return _link(line.href, line.text, external)


def _field(field) -> tuple[str, str]:
    lines = "".join(f"<div>{_line(line)}</div>" for line in field.lines)
    cls = "vl" if field.tone == "warn" else "v"
    return f'<div class="k">{escape(field.label)}</div>', f'<div class="{cls} ml">{lines}</div>'


def _fields(fields) -> str:
    cells = "".join("".join(_field(field)) for field in fields)
    return f'<div class="f">{cells}</div>'


def _slot(slot: Slot) -> str:
    note = f'<span class="n"> · {escape(slot.note)}</span>' if slot.note else ""
    marks = "".join(f'<span class="b">{escape(mark)}</span>' for mark in slot.marks)
    return f'<div class="s {_TONES[slot.tone]}">{escape(slot.text)}{note}{marks}</div>'


def _item(card: ItemCard, target: bool = False) -> str:
    parts = [
        f'<div class="cd{" tg" if target else ""}">',
        f'<div class="nm">{escape(card.name)}</div>',
        '<div class="pr">' + "".join(f'<span class="pl">{escape(p)}</span>' for p in card.properties) + "</div>",
    ]
    if card.implicits:
        parts.append('<div class="sd">Implicit</div>')
        parts += [_slot(slot) for slot in card.implicits]
    if card.enchantments:
        parts.append('<div class="sd">Enchantment</div>')
        parts += [f'<div class="s i">{escape(text)}</div>' for text in card.enchantments]
    parts.append('<div class="sd">Prefixes</div>')
    parts += [_slot(slot) for slot in card.prefixes]
    parts.append('<div class="sd">Suffixes</div>')
    parts += [_slot(slot) for slot in card.suffixes]
    if card.offer:
        parts.append('<div class="sd">Unveil offer</div>')
        parts += [_slot(slot) for slot in card.offer]
    parts.append("</div>")
    return "".join(parts)


def _section(section, heading: bool) -> str:
    out = [f'<section id="{escape(section.anchor, quote=True)}">']
    if heading:
        out.append(f"<h2>{escape(section.title)}</h2>")
    out.append(
        '<div class="rw"><div class="cd tg"><h3>Route goal</h3>'
        + _fields(section.goal.fields)
        + "</div>"
        + _item(section.goal.target, target=True)
        + "</div>"
    )
    for row in section.rows:
        out.append('<div class="ar">↓</div>')
        out.append(
            f'<div class="rw"><div class="cd" id="{escape(row.anchor, quote=True)}">'
            f"<h3>{row.number}. {escape(row.title)}</h3>" + _fields(row.fields) + "</div>"
            + _item(row.after, target=row.final)
            + "</div>"
        )
    out.append("</section>")
    return "".join(out)


def render_page(page) -> str:
    """The whole document for a `Page` of the route view: its title, a nav when there are several sections, the sections."""
    several = len(page.sections) > 1
    nav = ""
    if several:
        nav = "<nav>" + "".join(_link(f"#{section.anchor}", section.title) for section in page.sections) + "</nav>"
    body = "".join(_section(section, several) for section in page.sections)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(page.title)}</title>\n<style>\n{CSS}</style>\n</head>\n<body>\n<main>\n"
        f"<h1>{escape(page.title)}</h1>\n{nav}\n{body}\n</main>\n</body>\n</html>\n"
    )
