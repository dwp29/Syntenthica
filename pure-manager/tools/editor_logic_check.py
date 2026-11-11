"""Port uji: menjalankan kasus yang sama dengan EditorTest.kt di Python.

Sandbox ini tidak punya JDK, jadi Kotlin tidak bisa dijalankan. Yang bisa adalah
memindahkan algoritme yang sama ke Python dan mengecek bahwa jawabannya sama
dengan yang diharapkan tes Kotlin. Ini bukan pengganti kompilasi -- ia menangkap
aritmetika offset yang salah, bukan salah tulis Kotlin.
"""
import sys

FAIL = []


def ck(name, got, want):
    if got != want:
        FAIL.append(f"{name}: dapat {got!r}, harusnya {want!r}")


# ------------------------------------------------------------------ buffer
class History:
    def __init__(self, limit=200):
        self.done, self.undone, self.limit = [], [], limit

    def record(self, e):
        self.undone.clear()
        last = self.done[-1] if self.done else None
        if last and _mergeable(last, e):
            self.done[-1] = dict(last, inserted=last["inserted"] + e["inserted"], caretAfter=e["caretAfter"])
        else:
            self.done.append(e)
            if len(self.done) > self.limit:
                self.done.pop(0)

    def undo(self):
        if not self.done:
            return None
        e = self.done.pop()
        self.undone.append(e)
        return e

    def redo(self):
        if not self.undone:
            return None
        e = self.undone.pop()
        self.done.append(e)
        return e


def _mergeable(a, b):
    return (a["typed"] and b["typed"] and not a["removed"] and not b["removed"]
            and b["start"] == a["start"] + len(a["inserted"])
            and "\n" not in a["inserted"] and "\n" not in b["inserted"])


class Buffer:
    def __init__(self, initial=""):
        self.text = initial
        self.h = History()

    def replace(self, s, e, ins, caret_before=None, typed=False):
        a = max(0, min(s, len(self.text)))
        b = max(a, min(e, len(self.text)))
        if a == b and not ins:
            return a
        removed = self.text[a:b]
        self.text = self.text[:a] + ins + self.text[b:]
        self.h.record(dict(start=a, removed=removed, inserted=ins,
                           caretBefore=a if caret_before is None else caret_before,
                           caretAfter=a + len(ins),
                           typed=typed and not removed and len(ins) == 1))
        return a + len(ins)

    def undo(self):
        e = self.h.undo()
        if e is None:
            return None
        self.text = self.text[:e["start"]] + e["removed"] + self.text[e["start"] + len(e["inserted"]):]
        return max(0, min(e["caretBefore"], len(self.text)))

    def redo(self):
        e = self.h.redo()
        if e is None:
            return None
        self.text = self.text[:e["start"]] + e["inserted"] + self.text[e["start"] + len(e["removed"]):]
        return max(0, min(e["caretAfter"], len(self.text)))


b = Buffer("halo"); b.replace(4, 4, " dunia", 4)
ck("typing", b.text, "halo dunia"); ck("undo caret", b.undo(), 4); ck("undo text", b.text, "halo")
b = Buffer("baris satu\nbaris dua"); b.replace(0, 11, "", 0)
ck("hapus", b.text, "baris dua"); b.undo(); ck("undo hapus", b.text, "baris satu\nbaris dua")
b = Buffer("abc"); b.replace(3, 3, "d", 3); b.undo(); ck("redo caret", b.redo(), 4); ck("redo", b.text, "abcd")
b = Buffer("abc"); b.replace(3, 3, "d", 3); b.undo(); b.replace(0, 0, "z", 0)
ck("redo dibuang", b.redo(), None); ck("teks setelah buang", b.text, "zabc")
b = Buffer("")
for i, c in enumerate("kata"):
    b.replace(i, i, c, i, typed=True)
ck("kata satu langkah", len(b.h.done), 1); b.undo(); ck("undo kata", b.text, "")
b = Buffer("a"); b.replace(1, 1, "b", 1); b.replace(2, 2, "tempel", 2)
ck("tempel langkah sendiri", len(b.h.done), 2); b.undo(); ck("undo tempel", b.text, "ab")
b = Buffer(""); b.replace(0, 0, "x", 0); b.replace(1, 1, "\n", 1)
ck("enter langkah baru", len(b.h.done), 2)
b = Buffer("abc"); ck("clamp caret", b.replace(99, 120, "!"), 4); ck("clamp text", b.text, "abc!")
b = Buffer("abc"); b.replace(1, 1, ""); ck("edit kosong", len(b.h.done), 0)


# --------------------------------------------------------------- indentasi
def line_start_of(t, caret):
    i = t.rfind("\n", 0, caret)
    return 0 if i < 0 else i + 1


def newline_insertion(t, caret, unit="  "):
    at = max(0, min(caret, len(t)))
    ls = line_start_of(t, at)
    le = ls
    while le < at and t[le] in " \t":
        le += 1
    lead = t[ls:le]
    before = t[ls:at].rstrip()
    opens = before.endswith(("{", "(", "[", ":"))
    return "\n" + lead + (unit if opens else "")


ck("indent", newline_insertion("    val x = 1", 13), "\n    ")
ck("brace", newline_insertion("    if (a) {", 12), "\n      ")
ck("polos", newline_insertion("kata", 4), "\n")
ck("awal baris", newline_insertion("    abc", 4), "\n    ")


def dedent_range(t, caret, unit="  "):
    at = max(0, min(caret, len(t)))
    ls = line_start_of(t, at)
    prefix = t[ls:at]
    if prefix and prefix.strip():
        return None
    end = ls
    while end < len(t) and t[end] in " \t":
        end += 1
    if end == ls:
        return None
    lead = t[ls:end]
    if lead.startswith("\t"):
        n = 1
    elif len(lead) <= len(unit):
        n = len(lead)
    elif lead.endswith(unit):
        n = len(unit)
    else:
        n = len(lead) % len(unit)
    return (ls, ls + n - 1)


ck("dedent", dedent_range("    ", 4), (0, 1))
ck("tengah kata", dedent_range("    abc", 6), None)
ck("tanpa indent", dedent_range("abc", 3), None)
ck("indent ganjil", dedent_range("   x", 3), (0, 1))


def indent_block(t, s, e, outdent, unit="  "):
    frm, to = min(s, e), max(s, e)
    if frm == to:
        return None
    starts = [line_start_of(t, frm)]
    i = starts[0]
    while i < to:
        if t[i] == "\n":
            starts.append(i + 1)
        i += 1
    while len(starts) > 1 and starts[-1] >= to:
        starts.pop()
    splices = []
    for st in sorted(starts, reverse=True):
        if not outdent:
            splices.append((st, "", unit))
            continue
        r = dedent_range(t[st:], 0, unit)
        if r is None:
            continue
        a = st + r[0]
        splices.append((a, t[a:st + r[1] + 1], ""))
    if not splices:
        return None

    def shift(off, inclusive):
        out = off
        for sstart, rem, ins in reversed(splices):
            if sstart < off or (inclusive and sstart == off):
                out += len(ins) - len(rem)
        return max(0, out)

    return splices, shift(frm, True), shift(to, False)


ck("tab tanpa seleksi", indent_block("abc", 1, 1, False), None)
splices, _, _ = indent_block("a\nb\nc", 0, 5, False)
out = "a\nb\nc"
for st, rem, ins in splices:
    out = out[:st] + ins + out[st + len(rem):]
ck("indent 3 baris", out, "  a\n  b\n  c")
splices, _, _ = indent_block("  a\n  b", 0, 7, True)
out = "  a\n  b"
for st, rem, ins in splices:
    out = out[:st] + ins + out[st + len(rem):]
ck("outdent 2 baris", out, "a\nb")
ck("outdent tanpa indent", indent_block("a\nb", 0, 3, True), None)
ck("baris sesudah seleksi", len(indent_block("a\nb", 0, 2, False)[0]), 1)


# ---------------------------------------------------------------- kurung
PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
BRACKETS = set("([{")


def auto_close(t, caret, typed, sel=0):
    close = PAIRS.get(typed)
    if close is None:
        return None
    if sel > 0:
        return typed + close, 1
    if typed not in BRACKETS:
        if caret > 0 and t[caret - 1].isalnum():
            return None
        if caret < len(t) and t[caret] == typed:
            return None
        return typed + close, 1
    if caret < len(t) and t[caret] == close:
        return None
    return typed + close, 1


def deletes_pair(t, caret):
    if caret <= 0 or caret >= len(t):
        return False
    close = PAIRS.get(t[caret - 1])
    return close is not None and t[caret] == close


ck("auto (", auto_close("", 0, "("), ("()", 1))
ck("auto tutup", auto_close("()", 1, ")"), None)
ck("apostrof", auto_close("dont", 4, "'"), None)
ck("kutip", auto_close("x = ", 4, '"'), ('""', 1))
ck("bungkus", auto_close("kata", 0, '"', 4), ('""', 1))
ck("backspace pasangan", deletes_pair("()", 1), True)
ck("backspace bukan", deletes_pair("(x", 1), False)
ck("backspace awal", deletes_pair("()", 0), False)


def matching_bracket(t, index, lang="kotlin"):
    if index < 0 or index >= len(t):
        return None
    c = t[index]
    is_open = c in BRACKETS
    is_close = c in PAIRS.values() and c in BRACKETS
    if not is_open and not is_close:
        return None
    target = PAIRS[c] if is_open else c
    step = 1 if is_open else -1
    skip = lang not in ("plain", "properties")
    depth = 0
    i = index + step
    while 0 <= i < len(t):
        if skip:
            jumped = skip_region(t, i, step, lang)
            if jumped != i:
                i = jumped if step > 0 else i + step
                continue
        if t[i] == c:
            depth += 1
        if t[i] == target:
            if depth == 0:
                return i
            depth -= 1
        i += step
    return None


def skip_region(t, i, step, lang):
    if step < 0:
        return i
    c = t[i]
    if c in "\"'":
        if i > 0 and t[i - 1].isalnum():
            return i
        j = i + 1
        while j < len(t) and t[j] != c and t[j] != "\n":
            j += 2 if t[j] == "\\" else 1
        return j
    if c == "/" and i + 1 < len(t):
        if t[i + 1] == "/":
            nl = t.find("\n", i)
            return len(t) - 1 if nl < 0 else nl
        if t[i + 1] == "*":
            cl = t.find("*/", i + 2)
            return len(t) - 1 if cl < 0 else cl + 1
    if c == "#" and lang in ("shell", "python"):
        nl = t.find("\n", i)
        return len(t) - 1 if nl < 0 else nl
    return i


t = "f(a, (b + c), d)"
ck("kurung bersarang", matching_bracket(t, 1), t.rindex(")"))
ck("kurung balik", matching_bracket(t, t.rindex(")")), None)
t = 'f(")", x)'
ck("kurung di string", matching_bracket(t, 1), None)
ck("kurung tak seimbang", matching_bracket("f(a", 1), None)
ck("bukan kurung", matching_bracket("abc", 1), None)
t = "f(a) // )"
ck("kurung sebelum komentar", matching_bracket(t, 1), 3)

# ----------------------------------------------------------------- cari
def find(t, needle, frm=0, case_sensitive=False, whole_word=False):
    if not needle:
        return None
    i = max(0, min(frm, len(t)))
    last = len(t) - len(needle)
    while i <= last:
        piece = t[i:i + len(needle)]
        hit = piece == needle if case_sensitive else piece.lower() == needle.lower()
        if hit:
            ok = True
            if whole_word:
                before = i == 0 or not (t[i - 1].isalnum() or t[i - 1] == "_")
                after = i + len(needle) >= len(t) or not (t[i + len(needle)].isalnum() or t[i + len(needle)] == "_")
                ok = before and after
            if ok:
                return (i, i + len(needle))
            i += 1
        else:
            i += 1
    return None


def find_all(t, needle, case_sensitive=False, whole_word=False, limit=5000):
    out, at = [], 0
    while len(out) < limit:
        m = find(t, needle, at, case_sensitive, whole_word)
        if m is None:
            break
        out.append(m)
        at = max(m[1], m[0] + 1)
    return out


def replace_all(t, needle, rep, case_sensitive=False, whole_word=False):
    ms = find_all(t, needle, case_sensitive, whole_word, limit=sys.maxsize)
    if not ms:
        return t
    out, at = [], 0
    for s, e in ms:
        out.append(t[at:s])
        out.append(rep)
        at = e
    out.append(t[at:])
    return "".join(out)


def next_index(ms, caret, forward, current=-1):
    if not ms:
        return -1
    if forward:
        after = ms[current][1] if 0 <= current < len(ms) else caret
        for i, m in enumerate(ms):
            if m[0] >= after:
                return i
        return 0
    before = ms[current][0] if 0 <= current < len(ms) else caret
    for i in range(len(ms) - 1, -1, -1):
        if ms[i][1] <= before:
            return i
    return len(ms) - 1


ck("cari case", find("Nama Berkas", "berkas"), (5, 11))
ck("cari case peka", find("Nama Berkas", "berkas", case_sensitive=True), None)
ck("kata utuh", find("berkasnya", "berkas", whole_word=True), None)
ck("kata utuh 2", find("berkas itu", "berkas", whole_word=True), (0, 6))
ck("ganti berisi jarum", replace_all("a a", "a", "a-b"), "a-b a-b")
ck("ganti case", replace_all("a A a", "a", "X"), "X X X")
ck("ganti tanpa cocok", replace_all("abc", "zz", "!"), "abc")
ms = find_all("a a a", "a")
ck("jumlah cocok", len(ms), 3)
ck("berikut bungkus", next_index(ms, 5, True, 2), 0)
ck("sebelum bungkus", next_index(ms, 0, False, 0), 2)
ck("jarum kosong", find_all("abc", ""), [])

if FAIL:
    print("GAGAL")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("SEMUA KASUS LOGIKA EDITOR COCOK")
