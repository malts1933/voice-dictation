PUNCT = [
    (["запятая", "comma"], ", "),
    (["точка", "period", "full stop"], ". "),
    (["точка с запятой", "semicolon"], "; "),
    (["двоеточие", "colon"], ": "),
    (["вопросительный знак", "question mark"], "? "),
    (["восклицательный знак", "exclamation mark"], "! "),
    (["многоточие", "ellipsis"], "... "),
    (["тире", "dash"], " — "),
    (["дефис", "hyphen"], "-"),
    (["новая строка", "new line"], "\n"),
    (["новый абзац", "new paragraph"], "\n\n"),
    (["открыть кавычки", "open quotes"], '"'),
    (["закрыть кавычки", "close quotes"], '"'),
    (["открыть скобку", "open parenthesis"], "("),
    (["закрыть скобку", "close parenthesis"], ")"),
]
DELETE_WORD = ["удали последнее слово", "delete last word"]
DELETE_SENTENCE = ["удали последнее предложение", "delete last sentence"]
CAPITALIZE = ["большая буква", "с большой буквы", "capitalize"]


def match_at(tokens, i, phrase):
    parts = phrase.split()
    if i + len(parts) > len(tokens):
        return False
    return all(tokens[i + k].lower() == parts[k] for k in range(len(parts)))


def format_line(tokens):
    out = ""
    cap_next = False
    i = 0
    while i < len(tokens):
        handled = False
        for phrases, insert in PUNCT:
            if any(match_at(tokens, i, p) for p in phrases):
                if insert[:1] in ",.;:!?…":
                    out = out.rstrip()
                out += insert
                i += len(phrases[0].split())
                handled = True
                break
        if handled:
            continue
        if any(match_at(tokens, i, p) for p in DELETE_WORD):
            out = out.rstrip()
            idx = out.rfind(" ")
            out = out[: idx + 1] if idx != -1 else ""
            i += len(DELETE_WORD[0].split())
            continue
        if any(match_at(tokens, i, p) for p in DELETE_SENTENCE):
            out = out.rstrip()
            idx = out.rfind("\n")
            out = out[: idx + 1] if idx != -1 else ""
            i += len(DELETE_SENTENCE[0].split())
            continue
        if any(match_at(tokens, i, p) for p in CAPITALIZE):
            cap_next = True
            i += len(CAPITALIZE[0].split())
            continue
        word = tokens[i]
        if cap_next:
            word = word[:1].upper() + word[1:]
            cap_next = False
        out += word + " "
        i += 1
    return out.rstrip()


def split_sentences(text):
    import re
    parts = re.split(r"(?<=[.!?…])\s+", text)
    result = "\n".join(p.strip(" \t") for p in parts if p.strip(" \t"))
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result


def format_transcript(raw):
    result = []
    for line in raw.split("\n"):
        result.append(format_line(line.split()))
    return split_sentences("\n".join(result))