import re

from .. import config, h, messages as m


def transformProductionPlaceholders(doc):
    propdescRe = re.compile(r"^'(?:(\S*)/)?([\w*-]+)(?:!!([\w-]+))?'$")  # pylint: disable=redefined-outer-name
    funcRe = re.compile(r"^(?:(\S*)/)?([\w*-]+\(\))$")
    atruleRe = re.compile(r"^(?:(\S*)/)?(@[\w*-]+)$")
    typeRe = re.compile(
        r"""
        ^(?:(\S*)/)?
        (\S+)
        (?:\s+
            \[\s*
            (-?(?:\d+[\w-]*|∞|Infinity))\s*
            ,\s*
            (-?(?:\d+[\w-]*|∞|Infinity))\s*
            \]\s*
        )?$
        """,
        re.X,
    )
    for el in h.findAll("fake-production-placeholder", doc):
        addLineNumber(el)
        text = h.textContent(el)
        h.clearContents(el)
        match = propdescRe.match(text)
        if match:
            linkFor, lt, linkType = match.groups()
            if linkFor == "":
                linkFor = "/"
            if linkType is None:
                if linkFor is None:
                    linkType = "property"
                else:
                    linkType = "propdesc"
            elif linkType in ("property", "descriptor"):
                pass
            else:
                m.die(
                    f"Shorthand <<{match.group(0)}>> gives type as '{match.group(3)}', but only 'property' and 'descriptor' are allowed.",
                    el=el,
                )
                el.tag = "span"
                el.text = "<‘" + text[1:-1] + "’>"
                continue
            el.tag = "a"
            el.set("data-link-type", linkType)
            el.set("data-lt", lt)
            if linkFor is not None:
                el.set("for", linkFor)
            el.text = "<'" + lt + "'>"
            continue
        match = funcRe.match(text)
        if match:
            el.tag = "a"
            el.set("data-link-type", "function")
            el.set("data-lt", match.group(2))
            if match.group(1) is not None:
                el.set("for", match.group(1))
            el.text = "<" + match.group(2) + ">"
            continue
        match = atruleRe.match(text)
        if match:
            el.tag = "a"
            el.set("data-link-type", "at-rule")
            el.set("data-lt", match.group(2))
            if match.group(1) is not None:
                el.set("for", match.group(1))
            el.text = "<" + match.group(2) + ">"
            continue
        match = typeRe.match(text)
        if match:
            for_, term, rangeStart, rangeEnd = match.groups()
            el.tag = "a"
            el.set("data-link-type", "type")
            if for_ is not None:
                el.set("for", for_)
            interior = term
            if rangeStart is not None:
                rangeStart = formatValue(rangeStart)
                rangeEnd = formatValue(rangeEnd)
                if rangeStart is None or rangeEnd is None:
                    m.die(f"Shorthand <<{text}>> has an invalid range.", el=el)
                try:
                    if not correctlyOrderedRange(rangeStart, rangeEnd):
                        m.die(
                            f"Shorthand <<{text}>> has a range whose start is not less than its end.",
                            el=el,
                        )
                except:
                    print(text)
                    raise
                interior += f" [{rangeStart},{rangeEnd}]"
                el.set("data-lt", f"<{term}>")
            el.text = f"<{interior}>"
            continue
        m.die(f"Shorthand <<{text}>> does not match any recognized shorthand grammar.", el=el)
        el.tag = "span"
        el.text = el.get("bs-autolink-syntax")
        continue


def formatValue(val):
    negative = False
    if val[0] in ["-", "−"]:
        negative = True
        val = val[1:]

    if val == "Infinity":
        val = "∞"
    if val == "∞":
        return ("−" if negative else "") + val

    try:
        (num, unit) = re.match(r"(\d+)([\w-]*)", val).groups()
        val = int(num)
    except ValueError:
        return None

    return ("−" if negative else "") + str(val) + unit


def correctlyOrderedRange(start, end):
    start = numFromRangeVal(start)
    end = numFromRangeVal(end)
    return start < end


def numFromRangeVal(val):
    sign = 1
    if val[0] == "−":
        sign = -1
        val = val[1:]
    if val == "∞":
        return sign * float("inf")
    val = re.match(r"(\d+)", val).group(1)
    return sign * int(val)


def transformMaybePlaceholders(doc):
    propRe = re.compile(r"^([\w-]+): .+")
    valRe = re.compile(r"^(?:(\S*)/)?(\S[^!]*)(?:!!([\w-]+))?$")
    for el in h.findAll("fake-maybe-placeholder", doc):
        addLineNumber(el)
        text = h.textContent(el)
        h.clearContents(el)
        match = propRe.match(text)
        if match:
            el.tag = "a"
            el.set("class", "css")
            el.set("data-link-type", "propdesc")
            el.set("data-lt", match.group(1))
            el.text = text
            continue
        match = valRe.match(text)
        if match:
            if match.group(3) is None:
                linkType = "maybe"
            elif match.group(3) in config.maybeTypes:
                linkType = match.group(3)
            else:
                m.die(
                    f"Shorthand ''{match.group(0)}'' gives type as '{match.group(3)}', but only “maybe” types are allowed.",
                    el=el,
                )
                el.tag = "css"
                continue
            el.tag = "a"
            el.set("class", "css")
            el.set("data-link-type", linkType)
            el.set("data-lt", match.group(2))
            if match.group(1) is not None:
                el.set("for", match.group(1))
            el.text = match.group(2)
            continue
        el.tag = "css"
        el.text = text


def transformAutolinkShortcuts(doc):
    # Do the remaining textual replacements

    addedNodes = []

    def transformElement(parentEl):
        processContents = h.isElement(parentEl) and not doc.isOpaqueElement(parentEl)
        if not processContents:
            return
        children = h.childNodes(parentEl, clear=True)
        newChildren = []
        for el in children:
            if isinstance(el, str):
                newChildren.extend(transformText(el))
            elif h.isElement(el):
                transformElement(el)
                newChildren.append(el)
        h.appendChild(parentEl, *newChildren, allowEmpty=True)

    def transformText(text):
        nodes = [text]
        if "css" in doc.md.markupShorthands:
            config.processTextNodes(nodes, propdescRe, propdescReplacer)
        if "dfn" in doc.md.markupShorthands:
            config.processTextNodes(nodes, dfnRe, dfnReplacer)
            config.processTextNodes(nodes, abstractRe, abstractReplacer)
        if "http" in doc.md.markupShorthands:
            config.processTextNodes(nodes, headerRe, headerReplacer)
        if "idl" in doc.md.markupShorthands:
            config.processTextNodes(nodes, idlRe, idlReplacer)
        if "markup" in doc.md.markupShorthands:
            config.processTextNodes(nodes, elementRe, elementReplacer)
        if "biblio" in doc.md.markupShorthands:
            config.processTextNodes(nodes, biblioRe, biblioReplacer)
            config.processTextNodes(nodes, sectionRe, sectionReplacer)
        if "algorithm" in doc.md.markupShorthands:
            config.processTextNodes(nodes, varRe, varReplacer)
        if "markdown" in doc.md.markupShorthands:
            config.processTextNodes(nodes, inlineLinkRe, inlineLinkReplacer)
            config.processTextNodes(nodes, strongRe, strongReplacer)
            config.processTextNodes(nodes, emRe, emReplacer)
            config.processTextNodes(nodes, escapedRe, escapedReplacer)
        for node in nodes:
            if h.isElement(node):
                addedNodes.append(node)
        return nodes

    transformElement(doc.document.getroot())
    for node in addedNodes:
        if h.isElement(node):
            addLineNumber(node)

    for el in h.findAll("var", doc):
        h.fixSurroundingTypography(el)


def transformShorthandElements(doc):
    """
    The <l> element can contain any shorthand,
    and works inside of "opaque" elements too,
    unlike ordinary autolinking shorthands.
    """

    def replacer(reg, rep, el, text):
        match = reg.match(text)
        if match:
            result = rep(match)
            h.replaceNode(el, result)
            if result.tag == "a":
                attrTarget = result
            else:
                attrTarget = h.find("a", result)
            for k, v in el.attrib.items():
                attrTarget.set(k, v)
            return True
        return False

    for el in h.findAll("l", doc):
        # Autolinks that aren't HTML-parsing-compatible
        # are already specially handled by fixAwkwardCSSShorthands().
        child = h.hasOnlyChild(el)
        if child is not None and child.get("bs-autolink-syntax") is not None:
            continue

        text = h.textContent(el)
        if replacer(propdescRe, propdescReplacer, el, text):
            continue
        if replacer(dfnRe, dfnReplacer, el, text):
            continue
        if replacer(idlRe, idlReplacer, el, text):
            continue
        if replacer(elementRe, elementReplacer, el, text):
            continue
        if replacer(biblioRe, biblioReplacer, el, text):
            continue
        if replacer(sectionRe, sectionReplacer, el, text):
            continue
        if replacer(varRe, varReplacer, el, text):
            continue
        m.die(f"<l> element doesn't contain a recognized autolinking syntax:\n{h.outerHTML(el)}", el=el)
        el.tag = "span"


def transformProductionGrammars(doc):
    # Link up the various grammar symbols in CSS grammars to their definitions.
    if "css" not in doc.md.markupShorthands:
        return

    hashMultRe = re.compile(r"#{\s*\d+(\s*,(\s*\d+)?)?\s*}")

    def hashMultReplacer(match):
        return h.E.a({"data-link-type": "grammar", "data-lt": "#", "for": ""}, match.group(0))

    multRe = re.compile(r"{\s*\d+\s*}")

    def multReplacer(match):
        return h.E.a({"data-link-type": "grammar", "data-lt": "{A}", "for": ""}, match.group(0))

    multRangeRe = re.compile(r"{\s*\d+\s*,(\s*\d+)?\s*}")

    def multRangeReplacer(match):
        return h.E.a({"data-link-type": "grammar", "data-lt": "{A,B}", "for": ""}, match.group(0))

    simpleRe = re.compile(r"(\?|!|#|\*|\+|\|\||\||&amp;&amp;|&&|,)(?!')")
    # Note the negative-lookahead, to avoid matching delim tokens.

    def simpleReplacer(match):
        return h.E.a(
            {"data-link-type": "grammar", "data-lt": match.group(0), "for": ""},
            match.group(0),
        )

    addedNodes = []

    def transformElement(parentEl):
        children = h.childNodes(parentEl, clear=True)
        newChildren = []
        for el in children:
            if isinstance(el, str):
                newChildren.extend(transformText(el))
            elif h.isElement(el):
                if el.tag != "a":
                    # Transforms all add links, which aren't allowed in <a>...
                    transformElement(el)
                newChildren.append(el)
        h.appendChild(parentEl, *newChildren, allowEmpty=True)

    def transformText(text):
        nodes = [text]
        config.processTextNodes(nodes, hashMultRe, hashMultReplacer)
        config.processTextNodes(nodes, multRe, multReplacer)
        config.processTextNodes(nodes, multRangeRe, multRangeReplacer)
        config.processTextNodes(nodes, simpleRe, simpleReplacer)
        for node in nodes:
            if h.isElement(node):
                addedNodes.append(node)
        return nodes

    for el in h.findAll(".prod", doc):
        transformElement(el)

    for node in addedNodes:
        if h.isElement(node):
            addLineNumber(node)


biblioRe = re.compile(
    r"""
                        (\\)?
                        \[\[
                        (!)?
                        ([\w.+-]+)
                        (\s+(?:current|snapshot|inline|index|direct|obsolete)\s*)*
                        (?:\|([^\]]+))?
                        \]\]""",
    re.X,
)


def biblioReplacer(match):
    # Allow escaping things that aren't actually biblio links, by preceding with a \
    escape, bang, term, modifiers, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if bang == "!":
        type = "normative"
    else:
        type = "informative"
    if linkText is None:
        linkText = f"[{term}]"
    attrs = {
        "data-lt": term,
        "data-link-type": "biblio",
        "data-biblio-type": type,
        "bs-autolink-syntax": match.group(0),
    }

    modifiers = re.split(r"\s+", modifiers.strip()) if modifiers is not None else []
    statusCurrent = "current" in modifiers
    statusSnapshot = "snapshot" in modifiers
    if statusCurrent and statusSnapshot:
        m.die(f"Biblio shorthand {match.group(0)} contains *both* 'current' and 'snapshot', please pick one.")
    elif statusCurrent or statusSnapshot:
        attrs["data-biblio-status"] = "current" if statusCurrent else "snapshot"

    displayInline = "inline" in modifiers
    displayIndex = "index" in modifiers
    displayDirect = "direct" in modifiers
    if (displayInline + displayIndex + displayDirect) > 1:
        m.die(
            f"Biblio shorthand {match.group(0)} contains more than one of 'inline', 'index' and 'direct', please pick one."
        )
    elif displayInline:
        attrs["data-biblio-display"] = "inline"
    elif displayIndex:
        attrs["data-biblio-display"] = "index"
    elif displayDirect:
        attrs["data-biblio-display"] = "direct"

    if "obsolete" in modifiers:
        attrs["data-biblio-obsolete"] = ""

    return h.E.a(attrs, linkText)


sectionRe = re.compile(
    r"""
                        (\\)?
                        \[\[
                        ([\w.+-]+)?
                        (?:
                            ((?:\/[\w.+-]*)?(?:\#[\w.+-]+)) |
                            (\/[\w.+-]+)
                        )
                        (?:\|([^\]]+))?
                        \]\]""",
    re.X,
)


def sectionReplacer(match):
    escape, spec, section, justPage, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkText is None:
        linkText = ""

    if spec is None:
        # local section link
        return h.E.a(
            {"section": "", "href": section, "bs-autolink-syntax": match.group(0)},
            linkText,
        )
    elif justPage is not None:
        # foreign link, to an actual page from a multipage spec
        return h.E.span(
            {
                "spec-section": justPage + "#",
                "spec": spec,
                "bs-autolink-syntax": match.group(0),
            },
            linkText,
        )
    else:
        # foreign link
        return h.E.span(
            {
                "spec-section": section,
                "spec": spec,
                "bs-autolink-syntax": match.group(0),
            },
            linkText,
        )


propdescRe = re.compile(
    r"""
                        (\\)?
                        '
                        (?:([^\s'|]*)/)?
                        ([\w*-]+)
                        (?:!!([\w-]+))?
                        (?:\|([^']+))?
                        '""",
    re.X,
)


def propdescReplacer(match):
    escape, linkFor, lt, linkType, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkFor == "":
        linkFor = "/"
    if lt == "-":
        # Not a valid property actually.
        return "'-'"
    if linkType is None:
        if linkFor is None:
            linkType = "property"
        else:
            linkType = "propdesc"
    elif linkType in ("property", "descriptor"):
        pass
    else:
        m.die(
            f"Shorthand {match.group(0)} gives type as '{linkType}', but only 'property' and 'descriptor' are allowed.",
        )
        return h.E.span(match.group(0))
    if linkText is None:
        linkText = lt
    return h.E.a(
        {
            "data-link-type": linkType,
            "class": "property",
            "for": linkFor,
            "lt": lt,
            "bs-autolink-syntax": match.group(0),
        },
        linkText,
    )


idlRe = re.compile(
    r"""
                    (\\)?
                    {{
                    (?:([^}|]*)/)?
                    ([^}/|]+?)
                    (?:!!([\w-]+))?
                    (?:\|([^}]+))?
                    }}""",
    re.X,
)


def idlReplacer(match):
    escape, linkFor, lt, linkType, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkFor == "":
        linkFor = "/"
    if linkType is None:
        linkType = "idl"
    elif linkType in config.idlTypes:
        pass
    else:
        m.die(
            f"Shorthand {match.group(0)} gives type as '{linkType}', but only IDL types are allowed.",
        )
        return h.E.span(match.group(0))
    if linkText is None:
        if lt.startswith("constructor(") and linkFor and linkFor != "/":
            # make {{Foo/constructor()}} output as "Foo()" so you know what it's linking to.
            linkText = linkFor + lt[11:]
        else:
            linkText = lt
    return h.E.code(
        {"class": "idl", "nohighlight": ""},
        h.E.a(
            {
                "data-link-type": linkType,
                "for": linkFor,
                "lt": lt,
                "bs-autolink-syntax": match.group(0),
            },
            linkText,
        ),
    )


dfnRe = re.compile(
    r"""
                    (\\)?
                    \[=
                    (?!\s)(?:([^=|]*)/)?
                    ([^\"=]+?)
                    (?:\|([^\"=]+))?
                    =\]""",
    re.X,
)


def dfnReplacer(match):
    escape, linkFor, lt, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkFor == "":
        linkFor = "/"
    if linkText is None:
        linkText = lt
    return h.E.a(
        {
            "data-link-type": "dfn",
            "for": linkFor,
            "lt": lt,
            "bs-autolink-syntax": match.group(0),
        },
        linkText,
    )


abstractRe = re.compile(
    r"""
                        (\\)?
                        \[\$
                        (?!\s)(?:([^$|]*)/)?
                        ([^\"$]+?)
                        (?:\|([^\"$]+))?
                        \$\]""",
    re.X,
)


def abstractReplacer(match):
    escape, linkFor, lt, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkFor == "":
        linkFor = "/"
    if linkText is None:
        linkText = lt
    return h.E.a(
        {
            "data-link-type": "abstract-op",
            "for": linkFor,
            "lt": lt,
            "bs-autolink-syntax": match.group(0),
        },
        linkText,
    )


elementRe = re.compile(
    r"""
                        (?P<escape>\\)?
                        <{
                        (?P<element>[\w*-]+)
                        (?:/
                            (?P<attr>[\w*-]+)
                            (?:/(?P<value>[^}!|]+))?
                        )?
                        (?:!!(?P<linkType>[\w-]+))?
                        (?:\|(?P<linkText>[^}]+))?}>""",
    re.X,
)


def elementReplacer(match):
    groupdict = match.groupdict()
    if groupdict["escape"]:
        return match.group(0)[1:]
    if groupdict["attr"] is None and groupdict["value"] is None:
        linkType = "element"
        linkFor = None
        lt = groupdict["element"]
    elif groupdict["value"] is None:
        linkType = "element-sub"
        linkFor = groupdict["element"]
        lt = groupdict["attr"]
    else:
        linkType = "attr-value"
        linkFor = groupdict["element"] + "/" + groupdict["attr"]
        lt = groupdict["value"]
    if groupdict["linkType"] is not None:
        linkType = groupdict["linkType"]
    if groupdict["linkText"] is not None:
        linkText = groupdict["linkText"]
    else:
        linkText = lt
    return h.E.code(
        {},
        h.E.a(
            {
                "data-link-type": linkType,
                "for": linkFor,
                "lt": lt,
                "bs-autolink-syntax": match.group(0),
            },
            linkText,
        ),
    )


varRe = re.compile(
    r"""
                    (\\)?
                    \|
                    (\w(?:[\w\s-]*\w)?)
                    \|""",
    re.X,
)


def varReplacer(match):
    escape, varText = match.groups()
    if escape:
        return match.group(0)[1:]
    return h.E.var({"bs-autolink-syntax": match.group(0)}, varText)


inlineLinkRe = re.compile(
    r"""
                            (\\)?
                            \[([^\]]*)\]
                            \(\s*
                            ([^\s)]+)
                            \s*(?:"([^"]*)")?\s*
                            \)""",
    re.X,
)


def inlineLinkReplacer(match):
    _, text, href, title = match.groups()
    if title:
        attrs = {"href": href, "title": title}
    else:
        attrs = {"href": href}
    attrs["bs-autolink-syntax"] = match.group(0)
    return h.E.a(attrs, text)


strongRe = re.compile(
    r"""
                        (?<!\\)
                        \*\*
                        (?!\s)([^*]+)(?!\s)
                        (?<!\\)\*\*""",
    re.X,
)


def strongReplacer(match):
    return h.E.strong({"bs-autolink-syntax": match.group(0)}, match.group(1))


emRe = re.compile(
    r"""
                    (?<!\\)
                    \*
                    (?!\s)([^*]+)(?!\s)
                    (?<!\\)\*""",
    re.X,
)


def emReplacer(match):
    return h.E.em({"bs-autolink-syntax": match.group(0)}, match.group(1))


escapedRe = re.compile(r"\\\*")


def escapedReplacer(match):  # pylint: disable=unused-argument
    return "*"


headerRe = re.compile(
    r"""
                    (\\)?
                    \[:
                    (:?[^()<>@,;:\\"/\[\]?={}\s|]+)
                    (?:\|((?:(?!:\]).)+))?
                    :\]""",
    re.X,
)


def headerReplacer(match):
    escape, lt, linkText = match.groups()
    if escape:
        return match.group(0)[1:]
    if linkText is None:
        linkText = lt
    return h.E.a(
        {
            "data-link-type": "http-header",
            "for": "/",
            "lt": lt,
            "bs-autolink-syntax": match.group(0),
        },
        linkText,
    )


def addLineNumber(el):
    if el.get("line-number"):
        return
    line = h.approximateLineNumber(el)
    if line is not None:
        el.set("line-number", line)
