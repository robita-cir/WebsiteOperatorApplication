"""The date, file and homepage checks. They only report, so each test reads a warning list."""

import datetime as dt

from test_imagecheck import make_png

from site_agent import checks
from site_agent.config import SiteSettings
from site_agent.repository import Repository
from site_agent.site import Site

TODAY = dt.date(2026, 10, 20)


def open_site(site_dir):
    site = Site(SiteSettings(root=site_dir))
    return site, Repository(site)


def write(site_dir, rel, text):
    path = site_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_an_event_that_ended_is_warned(site_dir):
    site, repo = open_site(site_dir)
    warnings = checks.date_warnings(repo, TODAY)
    assert "The event Robot Learning Workshop ended on 12 March 2026. Archive it or update it." in warnings
    assert "The event Seminar on Assistive Robots ended on 6 May 2026. Archive it or update it." in warnings


def test_the_last_day_decides_when_an_event_ended(site_dir):
    site, repo = open_site(site_dir)
    # The workshop runs 10 to 12 March: still on during its last day, over the day after.
    assert not any("Robot Learning Workshop" in w for w in checks.date_warnings(repo, dt.date(2026, 3, 12)))
    assert any("Robot Learning Workshop" in w for w in checks.date_warnings(repo, dt.date(2026, 3, 13)))


def test_a_sample_event_is_not_reported_as_ended(site_dir):
    site, repo = open_site(site_dir)
    assert not any("Event 3" in w for w in checks.date_warnings(repo, TODAY))


def test_old_news_that_sounds_upcoming_is_warned(site_dir):
    site, repo = open_site(site_dir)
    warnings = checks.date_warnings(repo, TODAY)
    assert "News Next up says it is coming up, but is dated 20 February 2026. Check the wording." in warnings


def test_recent_news_that_sounds_upcoming_is_not_warned(site_dir):
    site, repo = open_site(site_dir)
    # 60 days after 20 February is 21 April: not yet more than 60 days old.
    assert not any("News Next up" in w for w in checks.date_warnings(repo, dt.date(2026, 4, 21)))
    assert any("News Next up" in w for w in checks.date_warnings(repo, dt.date(2026, 4, 22)))


def test_old_news_without_future_wording_is_not_warned(site_dir):
    site, repo = open_site(site_dir)
    assert not any("Announcement 1" in w for w in checks.date_warnings(repo, dt.date(2027, 1, 1)))


def test_future_wording_in_the_text_under_the_top_block_counts(site_dir):
    write(
        site_dir,
        "src/content/news/lab-party.md",
        '---\ntitle: "Lab party"\nkind: "news"\ndate: 2026-01-10\nsummary: "A party."\n---\n\nIt will take place soon.',
    )
    site, repo = open_site(site_dir)
    assert any("News Lab party says it is coming up" in w for w in checks.date_warnings(repo, TODAY))


def test_a_homepage_line_with_the_wrong_date_is_warned(site_dir):
    page = site_dir / "src/pages/index.astro"
    page.write_text(page.read_text(encoding="utf-8").replace("10 March 2026", "11 March 2026"), encoding="utf-8")
    site, repo = open_site(site_dir)
    warnings = checks.homepage_warnings(site, repo)
    assert (
        "src/pages/index.astro line 6 names the event Robot Learning Workshop but gives a different date "
        "from the event's date 10 March 2026 to 12 March 2026." in warnings
    )


def test_the_month_first_style_is_also_read(site_dir):
    write(site_dir, "src/pages/news.astro", "<p>The Robot Learning Workshop is on March 14, 2026.</p>\n")
    site, repo = open_site(site_dir)
    found = checks.homepage_warnings(site, repo)
    assert any(w.startswith("src/pages/news.astro line 1 names the event") for w in found)


def test_a_wrong_date_in_a_news_file_is_warned(site_dir):
    path = site_dir / "src/content/news/next-up.md"
    path.write_text(path.read_text(encoding="utf-8").replace("10 March 2026", "15 March 2026"), encoding="utf-8")
    site, repo = open_site(site_dir)
    assert any(w.startswith("src/content/news/next-up.md line 8") for w in checks.homepage_warnings(site, repo))


def test_the_unchanged_fixture_gives_no_homepage_warning_for_event_1(site_dir):
    site, repo = open_site(site_dir)
    assert not any("Robot Learning Workshop" in w for w in checks.homepage_warnings(site, repo))


def test_the_last_day_written_on_the_line_is_accepted(site_dir):
    write(site_dir, "src/pages/news.astro", "<p>Robot Learning Workshop ends on 12 March 2026.</p>\n")
    site, repo = open_site(site_dir)
    assert not any("news.astro" in w for w in checks.homepage_warnings(site, repo))


def test_a_line_with_a_longer_event_name_is_not_matched(site_dir):
    write(site_dir, "src/pages/news.astro", "<p>The Robot Learning Workshops series started on 1 January 2020.</p>\n")
    site, repo = open_site(site_dir)
    assert not any("news.astro" in w for w in checks.homepage_warnings(site, repo))


def test_a_line_that_names_the_event_without_a_date_is_fine(site_dir):
    write(site_dir, "src/pages/news.astro", "<p>Join the Robot Learning Workshop.</p>\n")
    site, repo = open_site(site_dir)
    assert not any("news.astro" in w for w in checks.homepage_warnings(site, repo))


def test_the_fixture_has_no_file_warnings(site_dir):
    site, repo = open_site(site_dir)
    assert checks.file_warnings(site, repo) == []


def test_a_social_image_of_the_wrong_size_is_warned(site_dir):
    (site_dir / "public/og-default.png").write_bytes(make_png(800, 400))
    site, repo = open_site(site_dir)
    assert (
        "public/og-default.png is 800 by 400 pixels. The sharing image must be 1200 by 630 pixels."
        in checks.file_warnings(site, repo)
    )


def test_a_social_image_of_the_right_size_is_not_warned(site_dir):
    (site_dir / "public/og-default.png").write_bytes(make_png(1200, 630))
    site, repo = open_site(site_dir)
    assert checks.file_warnings(site, repo) == []


def test_a_social_image_that_is_not_a_png_is_left_to_the_launch_check(site_dir):
    (site_dir / "public/og-default.png").write_text("not really a picture", encoding="utf-8")
    site, repo = open_site(site_dir)
    assert checks.file_warnings(site, repo) == []


def person_with_photo(site_dir, photo):
    write(
        site_dir,
        "src/content/people/pat-lee.md",
        f'---\nname: "Pat Lee"\ngroup: "faculty"\nphoto: "{photo}"\n---\n',
    )


def test_a_missing_photo_is_warned(site_dir):
    person_with_photo(site_dir, "/people/pat-lee.jpg")
    site, repo = open_site(site_dir)
    expected = "The photo for Pat Lee (/people/pat-lee.jpg) is not in the website's public folder."
    assert expected in checks.file_warnings(site, repo)


def test_a_photo_with_the_wrong_ending_is_warned(site_dir):
    person_with_photo(site_dir, "/people/pat-lee.gif")
    (site_dir / "public/people").mkdir(parents=True, exist_ok=True)
    (site_dir / "public/people/pat-lee.gif").write_bytes(b"GIF89a")
    site, repo = open_site(site_dir)
    assert any("must be a .jpg, .jpeg, .png or .webp file" in w for w in checks.file_warnings(site, repo))


def test_a_photo_with_a_good_ending_is_not_warned(site_dir):
    (site_dir / "public/people").mkdir(parents=True, exist_ok=True)
    for name in ("a.jpg", "b.JPEG", "c.png", "d.webp"):
        (site_dir / "public/people" / name).write_bytes(b"x")
        person_with_photo(site_dir, f"/people/{name}")
        site, repo = open_site(site_dir)
        assert checks.file_warnings(site, repo) == [], name


def test_a_photo_path_that_leaves_the_public_folder_is_warned(site_dir):
    person_with_photo(site_dir, "/people/../../secret.jpg")
    site, repo = open_site(site_dir)
    assert any("Pat Lee" in w for w in checks.file_warnings(site, repo))


def test_a_missing_pdf_is_warned(site_dir):
    (site_dir / "public/documents/annual-report.pdf").unlink()
    site, repo = open_site(site_dir)
    assert any("The PDF for Annual report 2025" in w for w in checks.file_warnings(site, repo))


def test_a_pdf_without_the_pdf_header_is_warned(site_dir):
    (site_dir / "public/documents/annual-report.pdf").write_bytes(b"<html>oops</html>")
    site, repo = open_site(site_dir)
    assert any("is not a real PDF" in w for w in checks.file_warnings(site, repo))


def test_a_file_over_20_mb_is_warned(site_dir):
    big = site_dir / "public/big.bin"
    with big.open("wb") as handle:
        handle.truncate(21 * 1024 * 1024)  # a sparse file: no real disk is used
    site, repo = open_site(site_dir)
    assert any(w.startswith("public/big.bin is 21 MB") for w in checks.file_warnings(site, repo))


def test_all_warnings_joins_every_check(site_dir):
    site, repo = open_site(site_dir)
    warnings = checks.all_warnings(site, repo, TODAY)
    assert any("ended on" in w for w in warnings)
    assert not any("different date" in w for w in warnings)
