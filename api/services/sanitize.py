"""Sanitizacao de HTML para defesa em profundidade contra XSS.

Usado antes de passar conteudo gerado por LLM (`relatorio_md` -> HTML) ou
qualquer entrada de usuario para templates Jinja2 que usem `|safe`.

A allowlist abaixo cobre o subset de HTML produzido por `markdown.markdown()`
com extensoes `tables` e `fenced_code` (que e o que chamamos em
`api/main.py::_render_html`). Qualquer tag fora dessa lista e escapada.
"""
from __future__ import annotations

import bleach


# Tags permitidas: corpo Markdown padrao + tabelas + code fenced
_ALLOWED_TAGS = frozenset({
    # Estrutura
    "p", "br", "hr", "div", "span", "pre",
    # Headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Enfase
    "strong", "em", "b", "i", "u", "del", "s",
    # Listas
    "ul", "ol", "li",
    # Tabelas
    "table", "thead", "tbody", "tr", "th", "td",
    # Codigo
    "code", "pre",
    # Citacao
    "blockquote",
    # Links e imagens (img precisa de img-src do CSP)
    "a", "img",
})

# Atributos por tag: minimo necessario, sem on*=, sem javascript:
_ALLOWED_ATTRIBUTES = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["align", "colspan", "rowspan"],
    "td": ["align", "colspan", "rowspan"],
}

# Protocolos seguros para href/src
_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


def sanitize_html(body: str) -> str:
    """Remove tags/atributos perigosos preservando markdown renderizado.

    Args:
        body: HTML gerado (tipicamente `markdown.markdown(md, extensions=...)`).

    Returns:
        HTML sanitizado. Scripts inline, atributos `on*`, `javascript:` URIs,
        tags `<iframe>`, `<object>`, `<embed>`, `<style>`, etc. removidos.
    """
    if not body:
        return ""
    return bleach.clean(
        body,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,                # remove tags nao permitidas (em vez de escapar)
        strip_comments=True,       # remove <!-- ... -->
    )
