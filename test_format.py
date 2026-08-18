import sys

sys.stdout.reconfigure(encoding="utf-8")

from dictation_format import format_transcript

CASES = [
    ("привет как дела", "привет как дела"),
    ("привет как дела точка", "привет как дела."),
    ("привет запятая как дела вопросительный знак", "привет, как дела?"),
    ("мир точка", "мир."),
    ("новая строка текст", "\nтекст"),
    ("привет мир удали последнее слово", "привет"),
    ("большая буква привет", "Привет"),
    ("hello comma world exclamation mark", "hello, world!"),
    ("большая буква привет точка", "Привет."),
]


def main():
    failed = 0
    for raw, expected in CASES:
        got = format_transcript(raw)
        ok = got == expected
        print(("PASS" if ok else "FAIL"), repr(raw), "->", repr(got), "" if ok else ("expected " + repr(expected)))
        if not ok:
            failed += 1
    print("total: %d, failed: %d" % (len(CASES), failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()