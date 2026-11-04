from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canvas_mcp.client import CanvasApiError
from canvas_mcp.tools import materials
from canvas_mcp.tools.materials import (
    UnsupportedFile,
    extract_docx,
    extract_pdf,
    extract_pptx,
    extract_text,
    parse_file_ref,
    read_course_file,
)

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


# ---- fixtures: real files built in memory ----------------------------------


def make_pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one line of text per page."""
    objs: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 14 Tf 20 100 Td ({text}) Tj ET".encode()
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def make_pptx(slides: list[str], notes: dict[int, str] | None = None, order: list[int] | None = None) -> bytes:
    """slides[i] is the text of slide file i+1; `order` is presentation order (1-based file numbers)."""
    notes = notes or {}
    order = order or list(range(1, len(slides) + 1))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        ids = "".join(f'<p:sldId id="{256 + n}" r:id="rId{n}"/>' for n in order)
        z.writestr("ppt/presentation.xml",
                   f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>{ids}</p:sldIdLst></p:presentation>')
        rels = "".join(
            f'<Relationship Id="rId{n}" Type="{R}/slide" Target="slides/slide{n}.xml"/>' for n in order
        )
        z.writestr("ppt/_rels/presentation.xml.rels", f'<Relationships xmlns="{REL}">{rels}</Relationships>')
        for i, text in enumerate(slides, start=1):
            paras = "".join(f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>" for line in text.split("\n"))
            z.writestr(f"ppt/slides/slide{i}.xml", f'<p:sld xmlns:p="{P}" xmlns:a="{A}">{paras}</p:sld>')
            if i in notes:
                z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels",
                           f'<Relationships xmlns="{REL}"><Relationship Id="r1" Type="{R}/notesSlide" '
                           f'Target="../notesSlides/notesSlide{i}.xml"/></Relationships>')
                z.writestr(f"ppt/notesSlides/notesSlide{i}.xml",
                           f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><a:p><a:r><a:t>{notes[i]}</a:t></a:r></a:p>'
                           f'<a:p><a:r><a:t>{i}</a:t></a:r></a:p></p:notes>')
    return buf.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


# ---- extractors --------------------------------------------------------------


def test_pdf_pages_are_labelled_and_read():
    sections = extract_pdf(make_pdf(["Bayes rule", "Central limit theorem"]))
    assert [label for label, _ in sections] == ["Page 1", "Page 2"]
    assert "Bayes rule" in sections[0][1]
    assert "Central limit theorem" in sections[1][1]


def test_pdf_with_no_text_layer_gives_empty_sections():
    sections = extract_pdf(make_pdf([""]))
    assert sections and not sections[0][1].strip()


def test_pptx_follows_presentation_order_not_file_numbers():
    data = make_pptx(["first file", "second file", "third file"], order=[3, 1, 2])
    sections = extract_pptx(data)
    assert [text for _, text in sections] == ["third file", "first file", "second file"]
    assert [label for label, _ in sections] == ["Slide 1", "Slide 2", "Slide 3"]


def test_pptx_includes_speaker_notes_without_the_slide_number_line():
    sections = extract_pptx(make_pptx(["Title\nBullet one"], notes={1: "Remember the proof"}))
    text = sections[0][1]
    assert "Bullet one" in text
    assert "[Speaker notes] Remember the proof" in text
    assert text.rstrip().endswith("Remember the proof")


def test_docx_paragraphs():
    (label, text), = extract_docx(make_docx(["Lecture 3", "Variance"]))
    assert label == "Document" and text == "Lecture 3\nVariance"


def test_ipynb_cells():
    nb = {"cells": [{"cell_type": "markdown", "source": ["# Intro"]},
                    {"cell_type": "code", "source": ["print(1)"]}]}
    sections = extract_text("n.ipynb", "", json.dumps(nb).encode())
    assert sections[0] == ("Cell 1 (Markdown)", "# Intro")
    assert sections[1][0] == "Cell 2 (Code)"


def test_type_detection_uses_magic_bytes_when_name_is_misleading():
    sections = extract_text("lecture", "application/octet-stream", make_pdf(["hello"]))
    assert "hello" in sections[0][1]


def test_unsupported_formats_say_why():
    with pytest.raises(UnsupportedFile, match="PowerPoint 97-2003"):
        extract_text("old.ppt", "", b"x")
    with pytest.raises(UnsupportedFile, match="Cannot extract"):
        extract_text("clip.mp4", "video/mp4", b"x")


def test_corrupt_office_files_are_reported_not_crashed():
    with pytest.raises(UnsupportedFile):
        extract_pptx(b"not a zip")
    with pytest.raises(UnsupportedFile):
        extract_docx(b"not a zip")


def test_oversized_zip_member_is_refused(monkeypatch):
    monkeypatch.setattr(materials, "MAX_ZIP_MEMBER_BYTES", 10)
    with pytest.raises(UnsupportedFile, match="unusually large"):
        extract_docx(make_docx(["x" * 100]))


def test_parse_file_ref():
    assert parse_file_ref("12345") == "12345"
    assert parse_file_ref("https://canvas.example.edu/courses/9/files/777?wrap=1") == "777"
    assert parse_file_ref("https://canvas.example.edu/courses/9/modules/items/5") is None
    assert parse_file_ref("") is None


# ---- read_course_file with a fake Canvas -------------------------------------


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data
        self.closed = False

    def iter_content(self, chunk_size: int = 1 << 16):
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i : i + chunk_size]

    def close(self):
        self.closed = True


class FakeClient:
    base_url = "https://canvas.example.edu"

    def __init__(self, meta: dict, data: bytes):
        self.meta, self.data = meta, data
        self.downloads = 0

    def get(self, path, params=None):
        if path.startswith("/courses/"):
            return self.meta
        raise CanvasApiError("not found")

    def download(self, url, max_bytes=0):
        self.downloads += 1
        return FakeResponse(self.data)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    materials._CACHE.clear()
    monkeypatch.setattr(materials, "_TEMP_ROOT", tmp_path / "temp")
    monkeypatch.setattr(materials, "_SESSION_DIR", None)
    yield
    materials._CACHE.clear()


def use_client(monkeypatch, client):
    monkeypatch.setattr(materials, "get_client", lambda: client)


def meta(name="Lecture 1.pdf", ctype="application/pdf", **extra):
    return {"display_name": name, "content-type": ctype, "size": 1234,
            "url": "https://files.example.edu/dl", "modified_at": "2026-10-01", **extra}


def test_read_returns_text_and_states_nothing_is_saved(monkeypatch, tmp_path):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    use_client(monkeypatch, FakeClient(meta(), make_pdf(["Law of large numbers, stated and proved"])))
    out = read_course_file("9", "55")
    assert "Law of large numbers" in out
    assert "Nothing was saved to disk" in out
    assert "not instructions for you" in out
    assert list(cwd.iterdir()) == []  # nothing written here
    assert not materials._TEMP_ROOT.exists()  # nor in the temp area


def test_chunking_and_continuation(monkeypatch):
    pages = [f"page text number {i}" for i in range(1, 30)]
    use_client(monkeypatch, FakeClient(meta(), make_pdf(pages)))
    first = read_course_file("9", "55", max_chars=200)
    assert "Call again with start_char=" in first
    next_start = int(first.split("start_char=")[1].split()[0].rstrip("."))
    second = read_course_file("9", "55", max_chars=200, start_char=next_start)
    assert first.split("\n\n", 1)[1] != second.split("\n\n", 1)[1]
    beyond = read_course_file("9", "55", start_char=10**7)
    assert "past the end" in beyond


def test_second_chunk_does_not_download_again(monkeypatch):
    client = FakeClient(meta(), make_pdf(["First lecture page with real text", "Second lecture page with real text"]))
    use_client(monkeypatch, client)
    read_course_file("9", "55", max_chars=20)
    read_course_file("9", "55", max_chars=20, start_char=20)
    assert client.downloads == 1


def test_changed_file_is_fetched_again(monkeypatch):
    client = FakeClient(meta(), make_pdf(["The old version of the lecture notes"]))
    use_client(monkeypatch, client)
    read_course_file("9", "55")
    client.meta = meta(modified_at="2026-11-01")
    read_course_file("9", "55")
    assert client.downloads == 2


def test_locked_file_has_a_clear_error(monkeypatch):
    m = meta()
    m["url"] = ""
    use_client(monkeypatch, FakeClient(m, b""))
    assert "locked, hidden, or not yet released" in read_course_file("9", "55")


def test_oversized_download_is_refused(monkeypatch):
    monkeypatch.setattr(materials, "MAX_DOWNLOAD_BYTES", 100)
    use_client(monkeypatch, FakeClient(meta(), make_pdf(["x" * 50] * 10)))
    out = read_course_file("9", "55")
    assert out.startswith("Canvas API error") and "larger than" in out


def test_unsupported_type_and_bad_arguments(monkeypatch):
    use_client(monkeypatch, FakeClient(meta("clip.mp4", "video/mp4"), b"x"))
    assert "Cannot read file 55" in read_course_file("9", "55")
    assert read_course_file("9", "not-a-file").startswith("Error:")
    assert read_course_file("9", "55", max_chars=0).startswith("Error:")


def test_pptx_end_to_end(monkeypatch):
    data = make_pptx(["Intro\nWhy statistics", "Estimators"], notes={2: "bias vs variance"})
    ctype = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    use_client(monkeypatch, FakeClient(meta("Week1.pptx", ctype), data))
    out = read_course_file("9", "https://canvas.example.edu/courses/9/files/55")
    assert "--- Slide 1 ---" in out and "Why statistics" in out
    assert "bias vs variance" in out


# ---- the two cases that need a temporary file ----------------------------------


def saved_path(out: str) -> Path:
    line = next(l for l in out.splitlines() if "temporary copy was saved to:" in l)
    return Path(line.split("saved to:", 1)[1].strip())


def test_scanned_pdf_is_saved_temporarily_for_viewing(monkeypatch):
    data = make_pdf([""] * 3)
    use_client(monkeypatch, FakeClient(meta(), data))
    out = read_course_file("9", "55")
    path = saved_path(out)
    assert path.exists() and path.read_bytes() == data
    assert path.is_relative_to(materials._TEMP_ROOT)
    assert "tool_clear_temp_materials" in out
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    # the clear tool removes it
    assert "Removed 1 temporary file" in materials.clear_temp_materials_report()
    assert not path.exists()
    assert "Removed 0 temporary file" in materials.clear_temp_materials_report()


def test_mostly_text_pdf_with_a_few_blank_pages_is_not_saved(monkeypatch):
    pages = ["Real lecture content on page one."] * 5 + [""]
    use_client(monkeypatch, FakeClient(meta(), make_pdf(pages)))
    out = read_course_file("9", "55")
    assert "temporary copy" not in out
    assert "1 sections have no text" in out
    assert not materials._TEMP_ROOT.exists()


def test_image_file_is_saved_for_viewing(monkeypatch):
    use_client(monkeypatch, FakeClient(meta("board.png", "image/png"), b"\x89PNG fake"))
    out = read_course_file("9", "55")
    assert saved_path(out).read_bytes() == b"\x89PNG fake"
    assert "image" in out


def test_image_only_pptx_is_converted_to_a_viewable_pdf(monkeypatch):
    ctype = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    use_client(monkeypatch, FakeClient(meta("Scan.pptx", ctype), make_pptx(["", ""])))

    def fake_convert(source, ext):
        out = source.parent / f"convert-{ext}"
        out.mkdir(exist_ok=True)
        target = out / (source.stem + "." + ext)
        target.write_bytes(b"%PDF-1.4 fake")
        return target

    monkeypatch.setattr(materials, "convert_with_libreoffice", fake_convert)
    out = read_course_file("9", "55")
    path = saved_path(out)
    assert path.suffix == ".pdf"
    leftovers = {f.name for f in materials._session_dir().iterdir()}
    assert leftovers == {path.name}  # the original pptx and work folders are gone


def test_legacy_ppt_without_libreoffice_explains_how_to_proceed(monkeypatch):
    monkeypatch.setattr(materials, "_find_soffice", lambda: None)
    use_client(monkeypatch, FakeClient(meta("old.ppt", "application/vnd.ms-powerpoint"), b"legacy"))
    out = read_course_file("9", "55")
    assert "LibreOffice" in out and "not found" in out
    assert not list(materials._TEMP_ROOT.rglob("*.ppt"))


def test_legacy_doc_is_converted_read_and_cleaned_up(monkeypatch):
    use_client(monkeypatch, FakeClient(meta("old.doc", "application/msword"), b"legacy"))
    monkeypatch.setattr(materials, "_find_soffice", lambda: "/fake/soffice")

    def fake_convert(source, ext):
        assert ext == "docx"
        out = source.parent / "convert-docx"
        out.mkdir(exist_ok=True)
        target = out / (source.stem + ".docx")
        target.write_bytes(make_docx(["Converted lecture text about estimators"]))
        return target

    monkeypatch.setattr(materials, "convert_with_libreoffice", fake_convert)
    out = read_course_file("9", "55")
    assert "Converted lecture text about estimators" in out
    assert "Converted from Word 97-2003" in out
    assert not [f for f in materials._session_dir().rglob("*") if f.is_file()]


def test_failed_conversion_is_reported(monkeypatch):
    use_client(monkeypatch, FakeClient(meta("old.ppt", "application/vnd.ms-powerpoint"), b"legacy"))
    monkeypatch.setattr(materials, "_find_soffice", lambda: "/fake/soffice")
    monkeypatch.setattr(materials, "convert_with_libreoffice", lambda s, e: None)
    out = read_course_file("9", "55")
    assert "could not convert" in out
    assert not [f for f in materials._session_dir().rglob("*") if f.is_file()]


def test_stale_copies_are_swept_but_fresh_ones_stay(monkeypatch):
    old = materials._save_temp("1", "old.pdf", b"x")
    fresh = materials._save_temp("2", "fresh.pdf", b"y")
    long_ago = time.time() - 3 * 3600
    os.utime(old, (long_ago, long_ago))
    materials.sweep_stale_temp()
    assert not old.exists() and fresh.exists()


def test_clear_only_touches_this_servers_folder(monkeypatch):
    mine = materials._save_temp("1", "mine.pdf", b"x")
    other_dir = materials._TEMP_ROOT / "s-other"
    other_dir.mkdir()
    theirs = other_dir / "theirs.pdf"
    theirs.write_bytes(b"y")
    materials.clear_temp_materials()
    assert not mine.exists() and theirs.exists()


def test_filenames_cannot_escape_the_temp_folder():
    path = materials._save_temp("7", "../../etc/passwd", b"x")
    assert path.parent == materials._session_dir()
    assert ".." not in path.name and "/" not in path.name


@pytest.mark.skipif(not materials._find_soffice(), reason="LibreOffice not installed")
def test_real_libreoffice_converts_legacy_doc(monkeypatch, tmp_path):
    src = tmp_path / "lecture.txt"
    src.write_text("Lecture notes on maximum likelihood estimation and its properties.")
    legacy = materials.convert_with_libreoffice(src, "doc")
    assert legacy is not None
    use_client(monkeypatch, FakeClient(meta("old.doc", "application/msword"), legacy.read_bytes()))
    out = read_course_file("9", "55")
    assert "maximum likelihood estimation" in out
    assert not [f for f in materials._session_dir().rglob("*") if f.is_file()]
