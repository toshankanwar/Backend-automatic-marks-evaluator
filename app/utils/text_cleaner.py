import re

def clean_text(txt: str) -> str:
    txt = txt.lower()
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def tokenize(txt: str) -> list[str]:
    txt = clean_text(txt)
    return re.findall(r"[a-z0-9]+", txt)