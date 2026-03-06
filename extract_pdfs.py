import pdfplumber
import json
import re
import os

PDF_DIR = "/Users/antwan/Downloads/Prayer Room"
WEEKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weeks.json")

SECTIONS = [
    {"id": "love-god", "title": "Love God",
     "verse": "\"This, then, is how you should pray: 'Our Father in heaven, hallowed be your name...' We pray the name of God.",
     "icon": "heart", "subsection_count": 1},
    {"id": "help-others", "title": "Help Others",
     "verse": "\"May Your kingdom come soon. May Your will be done on earth, as it is in heaven.\"",
     "icon": "users", "subsection_count": 3},
    {"id": "our-needs", "title": "Our Needs",
     "verse": "\"Give us today the food we need.\"",
     "icon": "hand", "subsection_count": 4},
    {"id": "sorry-forgive", "title": "Sorry & Forgive",
     "verse": "\"And forgive us our sins, as we have forgiven those who sin against us.\"",
     "icon": "refresh", "subsection_count": 1},
    {"id": "stay-safe", "title": "Stay Safe",
     "verse": "\"And don't let us yield to temptation, but rescue us from the evil one.\"",
     "icon": "shield", "subsection_count": 4},
    {"id": "thank-you", "title": "Thank You",
     "verse": "\"For Yours is the kingdom and the power and the glory forever. Amen.\"",
     "icon": "star", "subsection_count": 1}
]

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def strip_page_numbers(text):
    lines = text.split('\n')
    return '\n'.join(l for l in lines if not re.match(r'^\s*\d{1,2}\s*$', l))

def extract_pray_page(text):
    text = strip_page_numbers(text)
    text = re.sub(r'^\s*PRAY\s*\n', '', text.strip(), flags=re.IGNORECASE)

    scripture_text = ""
    scripture_ref = ""
    adult_prayer = ""
    kids_prayer = ""

    parts_adult = re.split(r'ADULTS?\s*PRAY', text, flags=re.IGNORECASE)

    if len(parts_adult) >= 2:
        scripture_raw = strip_page_numbers(parts_adult[0]).strip()

        ref_match = re.search(r'-\s*((?:\d\s*)?[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)?\s+\d+[:\d\-]*)\s*$', scripture_raw)
        if ref_match:
            ref_raw = re.sub(r'\s+', ' ', ref_match.group(1).strip())
            words = ref_raw.split()
            ref_parts = []
            for w in words:
                if re.match(r'^\d', w) or ':' in w or '-' in w:
                    ref_parts.append(w)
                else:
                    ref_parts.append(w.capitalize())
            scripture_ref = ' '.join(ref_parts)
            scripture_raw = scripture_raw[:ref_match.start()].strip()

        scripture_text = clean_text(scripture_raw)
        scripture_text = scripture_text.strip('""\u201c\u201d\u2018\u2019\'')
        if scripture_text:
            scripture_text = '"' + scripture_text + '"'

        after_adult = strip_page_numbers(parts_adult[1])
        parts_kids = re.split(r'KIDS?\s*PRAY', after_adult, flags=re.IGNORECASE)

        if len(parts_kids) >= 1:
            adult_prayer = clean_text(strip_page_numbers(parts_kids[0]))
        if len(parts_kids) >= 2:
            kids_prayer = clean_text(strip_page_numbers(parts_kids[1]))

    return scripture_text, scripture_ref, adult_prayer, kids_prayer

def parse_topic_page(raw_text):
    """Parse topic page using the Canva interleaved layout pattern."""
    text = strip_page_numbers(raw_text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Remove FOCUS: line
    lines = [l for l in lines if not l.startswith('FOCUS:')]

    # Join all text into one string
    full = ' '.join(lines)

    # The pattern is: FOCUS_KEYWORD [mixed desc words] KEYWORD_CONT: TITLE_WORDS
    # We need to find the colon, then work backwards for focus and forwards for title

    # Known focus fragments that appear before the colon
    focus_fragments = {
        'SALVATION': 'Salvation',
        'DELIVERANCE': 'Deliverance',
        'HEALING': 'Healing',
        'PASTORS & LEADERS': 'Pastors & Leaders',
        'PASTORS &': 'Pastors & Leaders',
        'CHURCH & MEMBERS': 'Church & Members',
        'CHURCH MEMBERS': 'Church & Members',
        'CHURCH &': 'Church & Members',
        'CHURCH': 'Church & Members',
        'FAMILY & FRIENDS': 'Family & Friends',
        'FAMILY &': 'Family & Friends',
        'NATIONS': 'Nations',
        'CONFES SION': 'Confession',
        'CONFESSION': 'Confession',
        'GRATITUDE': 'Gratitude',
        'FOR': 'Gratitude'
    }

    # Strategy: rebuild the text by finding the colon position
    # Everything after the colon that's UPPERCASE = title
    # The focus keyword is split around mixed-case description text
    # Description is the mixed-case text

    # Find colon in the full text
    colon_idx = full.find(':')
    if colon_idx == -1:
        # No colon found - try to split uppercase vs lowercase
        words = full.split()
        upper_words = []
        desc_words = []
        for w in words:
            alpha = re.sub(r'[^A-Za-z]', '', w)
            if alpha and alpha == alpha.upper():
                upper_words.append(w)
            else:
                desc_words.append(w)
        return "Prayer", clean_text(' '.join(upper_words)) or "PRAYER POINT", clean_text(' '.join(desc_words))

    before_colon = full[:colon_idx].strip()
    after_colon = full[colon_idx+1:].strip()

    # Extract description: mixed-case words from before_colon
    # Extract focus fragments: uppercase words from before_colon
    before_words = before_colon.split()
    focus_parts = []
    desc_parts = []
    for w in before_words:
        alpha = re.sub(r'[^A-Za-z]', '', w)
        if alpha and alpha == alpha.upper():
            focus_parts.append(w)
        else:
            desc_parts.append(w)

    # Extract title: uppercase words from after_colon
    # Any remaining mixed-case in after_colon is also description
    after_words = after_colon.split()
    title_parts = []
    for w in after_words:
        alpha = re.sub(r'[^A-Za-z]', '', w)
        if alpha and alpha == alpha.upper():
            title_parts.append(w)
        else:
            desc_parts.append(w)

    focus_raw = ' '.join(focus_parts).strip()
    title = clean_text(' '.join(title_parts))
    desc = clean_text(' '.join(desc_parts))

    # Map focus
    focus = ""
    focus_upper = focus_raw.upper()
    # Try longest match first
    for key in sorted(focus_fragments.keys(), key=len, reverse=True):
        if key in focus_upper:
            focus = focus_fragments[key]
            break

    if not focus:
        focus = focus_raw.title() if focus_raw else "Prayer"
    if not title:
        title = "PRAYER POINT"

    return focus, title, desc

def extract_love_god_pages(pages, start_idx):
    topic_text = strip_page_numbers(pages[start_idx].extract_text() or "")
    pray_text = pages[start_idx + 1].extract_text() or ""

    lines = [l.strip() for l in topic_text.split('\n') if l.strip()]
    lines = [l for l in lines if not re.match(r'^\d+$', l.strip())]

    name_lines = []
    desc_lines = []

    for line in lines:
        alpha = re.sub(r'[^A-Za-z]', '', line)
        if alpha and alpha == alpha.upper() and len(alpha) > 1:
            name_lines.append(line)
        elif line[0:1].isupper() and line != line.upper():
            desc_lines.append(line)

    name_text = ' '.join(name_lines)
    title = ""
    subtitle = ""

    if ' - ' in name_text:
        parts = name_text.split(' - ', 1)
        title = clean_text(parts[0])
        subtitle = clean_text(parts[1]).title()
    elif ' -' in name_text:
        parts = name_text.split(' -', 1)
        title = clean_text(parts[0])
        subtitle = clean_text(parts[1].lstrip()).title()
    else:
        title = clean_text(name_text)

    desc = clean_text(' '.join(desc_lines))
    scripture_text, scripture_ref, adult_prayer, kids_prayer = extract_pray_page(pray_text)

    return [{
        "focus": "Name of God",
        "title": title,
        "subtitle": subtitle,
        "desc": desc,
        "verseText": "",
        "verseRef": "",
        "adultPrayer": adult_prayer,
        "kidsPrayer": kids_prayer
    }]

def extract_regular_section(pages, start_idx, count):
    subsections = []
    idx = start_idx

    for i in range(count):
        if idx + 1 >= len(pages):
            break

        topic_text = pages[idx].extract_text() or ""
        pray_text = pages[idx + 1].extract_text() or ""
        idx += 2

        focus, title, desc = parse_topic_page(topic_text)
        scripture_text, scripture_ref, adult_prayer, kids_prayer = extract_pray_page(pray_text)

        subsections.append({
            "focus": focus,
            "title": title,
            "subtitle": "",
            "desc": desc,
            "verseText": scripture_text,
            "verseRef": scripture_ref,
            "adultPrayer": adult_prayer,
            "kidsPrayer": kids_prayer
        })

    return subsections, idx

def extract_week(pdf_path, week_num):
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        sections = []
        idx = 5

        for sec_def in SECTIONS:
            idx += 1
            count = sec_def["subsection_count"]
            count_text = str(count) + " Prayer Point" + ("s" if count > 1 else "")

            if sec_def["id"] == "love-god":
                subsections = extract_love_god_pages(pages, idx)
                idx += 2
            else:
                subsections, idx = extract_regular_section(pages, idx, count)

            sections.append({
                "id": sec_def["id"],
                "title": sec_def["title"],
                "verse": sec_def["verse"],
                "icon": sec_def["icon"],
                "count": count_text,
                "subsections": subsections
            })

        return {"sections": sections}

def main():
    with open(WEEKS_JSON, 'r') as f:
        data = json.load(f)

    success = 0
    errors = []

    for week_num in range(9, 53):
        pdf_path = os.path.join(PDF_DIR, f"{week_num}. PrayerRoom.pdf")
        if not os.path.exists(pdf_path):
            errors.append(f"Week {week_num}: PDF not found")
            continue

        try:
            week_data = extract_week(pdf_path, week_num)
            data["weeks"][str(week_num)] = week_data
            success += 1
            print(f"Week {week_num}: OK")
        except Exception as e:
            errors.append(f"Week {week_num}: {str(e)}")
            print(f"Week {week_num}: ERROR - {e}")

    with open(WEEKS_JSON, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone: {success} weeks extracted, {len(errors)} errors")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    main()
