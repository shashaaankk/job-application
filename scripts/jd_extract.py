"""Job-description extraction: per-portal, structured, formatted.

Every fetch path MUST get JD text through extract(page, url) so that
cards always come out as readable markdown. Three guarantees this
module owns:

1. Structure survives. The posting's HTML is serialized to markdown
   (list items -> bullets, headings and bold section titles -> headings)
   instead of being flattened through innerText.
2. Chrome is stripped. Leading boilerplate ("View job here", metadata
   stubs) and trailing footers (Impressum, "powered by", apply buttons)
   are removed by tidy().
3. Portal quirks are encoded once, here:
   - LinkedIn: the description is clamped behind a text button reading
     "... more" (aria-label "More options" buttons are menus - never
     click those); the container sits ABOVE the "About the job" heading,
     found by ascending until the text is substantial.
   - Stepstone: [data-at='job-ad-content'] holds the ad; job pages must
     be opened via the card's own href (constructed ...-inline.html URLs
     render an empty shell).
   - Naukri: the description is the [class*='dang-inner-html'] node
     ONLY (broader job-desc containers include widgets); text after
     Naukri's widget markers is cut. Access obeys the Naukri pacing
     protocol (the caller paces, this module only extracts).

An extraction under MIN_CHARS characters returns "" - callers treat
that as failure and never write a card with a stub description.
"""

import re

MIN_CHARS = 300

# DOM -> markdown. Runs inside the page.
_MD = r"""
function mdFromNode(root){
  function walk(n){
    if(n.nodeType===3) return n.textContent;
    if(n.nodeType!==1) return '';
    const tag=n.tagName;
    if(['SCRIPT','STYLE','BUTTON','SVG','NAV'].includes(tag)) return '';
    const kids=[...n.childNodes].map(walk).join('');
    if(/^H[1-6]$/.test(tag)) return '\n\n#### '+kids.trim()+'\n\n';
    if(tag==='LI') return '\n- '+kids.trim().replace(/\n+/g,' ');
    if(tag==='UL'||tag==='OL') return '\n'+kids+'\n';
    if(tag==='BR') return '\n';
    if(tag==='STRONG'||tag==='B'){const t=kids.trim();return t?'**'+t+'**':'';}
    if(tag==='P'||tag==='DIV'||tag==='SECTION'||tag==='ARTICLE') return '\n\n'+kids+'\n\n';
    return kids;
  }
  return walk(root).replace(/[ \t]+\n/g,'\n').replace(/\n{3,}/g,'\n\n').trim();
}
"""

_LEAD_JUNK = re.compile(r"^(view job here|about the job|show more|show less)$", re.I)
_TAIL_JUNK = re.compile(
    r"^(show less|.{0,3}less|see more|"
    r".*?(impressum|datenschutz|powered by|online bewerben|jetzt bewerben).*)$", re.I)


def tidy(text):
    """Strip leading/trailing chrome; keep markdown structure intact."""
    lines = [l.rstrip() for l in text.split("\n")]
    while lines and (not lines[0].strip()
                     or _LEAD_JUNK.match(lines[0].strip())
                     or (len(lines[0].strip()) < 45
                         and not lines[0].strip().startswith(("-", "#", "**"))
                         and not lines[0].strip().endswith((".", ":", "!")))):
        lines.pop(0)
    while lines and (not lines[-1].strip() or _TAIL_JUNK.match(lines[-1].strip())):
        lines.pop()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _linkedin(page):
    # expand the clamped description: TEXT button "... more" only
    try:
        page.evaluate("""()=>{
          const b=[...document.querySelectorAll('button')]
            .find(e=>/(see )?more$/i.test((e.innerText||'').trim())
                     && (e.innerText||'').length<15);
          if (b) b.click();
        }""")
        page.wait_for_timeout(1000)
    except Exception:
        pass
    return page.evaluate("()=>{" + _MD + """
      const heads=[...document.querySelectorAll('h1,h2,h3,strong,span')]
        .filter(e=>/^about the (job|role)$/i.test((e.innerText||'').trim()));
      for (const h of heads){
        let e=h;
        for (let i=0;i<8 && e;i++){
          e=e.parentElement;
          if (e && e.innerText.length>500 && e.innerText.length<40000)
            return mdFromNode(e);
        }
      }
      return '';
    }""")


def _stepstone(page):
    return page.evaluate("()=>{" + _MD + """
      const el=document.querySelector("[data-at='job-ad-content']")
        || document.querySelector('article');
      return el? mdFromNode(el) : '';
    }""")


def _naukri(page):
    # the true description is the [class*='dang-inner-html'] node; broader
    # [class*='job-desc'] containers also hold widgets (match score, key
    # skills) and must not be used. Fallback: ascend from the visible
    # "Job description" heading. Text after Naukri's widget markers is cut.
    txt = page.evaluate("()=>{" + _MD + """
      const el=document.querySelector("[class*='dang-inner-html']");
      if (el) return mdFromNode(el);
      const heads=[...document.querySelectorAll('h1,h2,h3,strong,span')]
        .filter(e=>/^job description$/i.test((e.innerText||'').trim()));
      for (const h of heads){
        let e=h;
        for (let i=0;i<6 && e;i++){
          e=e.parentElement;
          if (e && e.innerText.length>400) return mdFromNode(e);
        }
      }
      return '';
    }""")
    for marker in ("Job match score", "Key Skills", "Keyskills"):
        i = txt.find(marker)
        if i > 0:
            txt = txt[:i]
    return txt


_BY_HOST = {"linkedin.com": _linkedin,
            "stepstone.de": _stepstone,
            "naukri.com": _naukri}


def extract(page, url):
    """Extract the formatted JD from an already-loaded job page.

    Returns markdown text, or "" when the portal is unknown or the
    extraction is too short to be a real description.
    """
    fn = next((f for h, f in _BY_HOST.items() if h in url), None)
    if fn is None:
        return ""
    jd = tidy((fn(page) or "").strip())
    return jd if len(jd) >= MIN_CHARS else ""
