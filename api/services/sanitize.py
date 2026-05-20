"""Sanitizacao de HTML para defesa em profundidade contra XSS e SSRF.

Usado antes de passar conteudo gerado por LLM (`relatorio_md` -> HTML) ou
qualquer entrada de usuario para templates Jinja2 que usem `|safe`.

A allowlist abaixo cobre o subset de HTML produzido por `markdown.markdown()`
com extensoes `tables` e `fenced_code` (que e o que chamamos em
`api/main.py::_render_html`). Qualquer tag fora dessa lista e escapada.

SSRF guard: `img src` aceita apenas `data:` URIs (base64 embutido).
URIs remotos (`http://`, `https://`) sao bloqueados para impedir que
WeasyPrint (gerador de PDF) faca fetch de URLs externas ao renderizar.
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
    # Links e imagens (img src restrito a data URIs — veja _allow_attrs)
    "a", "img",
})


def _allow_attrs(tag: str, name: str, value: str) -> bool:
    """Callable para bleach.clean — filtra atributos por tag, nome e valor.

    Centraliza toda logica de protocolo aqui (em vez de passar `protocols=`
    ao bleach) para ter controle granular por tag.
    """
    # Atributos globais permitidos em qualquer tag
    if name in ("class", "id"):
        return True

    if tag == "a":
        if name not in ("href", "title", "target", "rel"):
            return False
        if name == "href":
            try:
                scheme = value.split(":")[0].lower().strip()
                return scheme in ("https", "mailto", "")
            except Exception:
                return False
        return True

    if tag == "img":
        if name not in ("src", "alt", "title", "width", "height"):
            return False
        if name == "src":
            # Apenas data URIs — bloqueia fetch remoto pelo WeasyPrint (SSRF)
            return value.startswith("data:")
        return True

    if tag in ("th", "td"):
        return name in ("align", "colspan", "rowspan")

    return False


def sanitize_html(body: str) -> str:
    """Remove tags/atributos perigosos preservando markdown renderizado.

    Args:
        body: HTML gerado (tipicamente `markdown.markdown(md, extensions=...)`).

    Returns:
        HTML sanitizado. Scripts inline, atributos `on*`, `javascript:` URIs,
        tags `<iframe>`, `<object>`, `<embed>`, `<style>`, etc. removidos.
        `<img src>` restrito a `data:` URIs — sem fetch remoto (SSRF guard).
        `<a href>` restrito a `https:` e `mailto:` — sem HTTP downgrade.
    """
    if not body:
        return ""
    # protocols é aplicado por bleach INDEPENDENTEMENTE do callable attributes —
    # inclui "data" para data URIs (imagens embutidas) mas NÃO "http" (downgrade).
    # O callable _allow_attrs ainda restringe img src a data: apenas.
    return bleach.clean(
        body,
        tags=_ALLOWED_TAGS,
        attributes=_allow_attrs,
        protocols={"data", "https", "mailto"},
        strip=True,
        strip_comments=True,
    )
