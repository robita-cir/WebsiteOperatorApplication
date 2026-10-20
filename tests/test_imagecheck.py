"""Reading a PNG's size, a PDF's header and a file's size without an image library."""

import struct

from site_agent.imagecheck import file_size, is_pdf, is_png, png_size


def make_png(width: int, height: int) -> bytes:
    """Only the signature and the IHDR chunk: all the size check reads."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + header + b"\x00\x00\x00\x00"


def test_png_size_is_read_from_the_header(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(make_png(1200, 630))
    assert is_png(path)
    assert png_size(path) == (1200, 630)


def test_a_file_that_is_not_a_png_has_no_size(tmp_path):
    path = tmp_path / "a.png"
    path.write_text("not really a picture", encoding="utf-8")
    assert not is_png(path)
    assert png_size(path) is None


def test_a_truncated_png_has_no_size(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(make_png(10, 10)[:15])
    assert png_size(path) is None


def test_a_missing_file_is_handled(tmp_path):
    missing = tmp_path / "missing"
    assert png_size(missing) is None
    assert not is_png(missing)
    assert not is_pdf(missing)
    assert file_size(missing) is None


def test_pdf_header(tmp_path):
    good, bad = tmp_path / "good.pdf", tmp_path / "bad.pdf"
    good.write_bytes(b"%PDF-1.7\n")
    bad.write_bytes(b"<html>")
    assert is_pdf(good)
    assert not is_pdf(bad)


def test_file_size(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"12345")
    assert file_size(path) == 5
