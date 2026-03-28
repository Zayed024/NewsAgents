from src.tools.corpus.dedup import canonicalize_url, is_near_duplicate
from src.tools.corpus.queue import CrawlQueue
from src.tools.corpus.discovery import extract_urls_from_html, extract_urls_from_sitemap_xml
from src.tools.corpus.store import ArticleCorpusStore


def test_canonicalize_url_removes_tracking_params():
    url = "https://www.economictimes.com/news/economy/article?utm_source=x&fbclid=abc&id=1"
    got = canonicalize_url(url)
    assert got == "https://economictimes.com/news/economy/article?id=1"


def test_near_duplicate_detection():
    a = "Budget raised capital expenditure to support growth and infrastructure buildout."
    b = "Budget raised capital expenditure to support growth and infrastructure buildout across sectors."
    assert is_near_duplicate(a, b)


def test_crawl_queue_domain_and_depth_constraints():
    q = CrawlQueue(allowed_domains={"economictimes.com"}, max_depth=1, max_items=5)
    assert q.enqueue("https://economictimes.com/news/economy", depth=0)
    assert not q.enqueue("https://example.com/news", depth=0)
    assert not q.enqueue("https://economictimes.com/markets", depth=2)
    assert len(q) == 1


def test_extract_urls_from_html_and_sitemap():
    html = '<a href="/news/economy/article1">x</a><a href="https://economictimes.com/markets/abc">y</a>'
    out = extract_urls_from_html(html, "https://economictimes.com", {"economictimes.com"})
    assert any("/news/economy/article1" in u for u in out)

    xml = """
    <urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
      <url><loc>https://economictimes.com/news/economy/article1</loc></url>
      <url><loc>https://example.com/x</loc></url>
    </urlset>
    """
    out_xml = extract_urls_from_sitemap_xml(xml, {"economictimes.com"})
    assert out_xml == ["https://economictimes.com/news/economy/article1"]


def test_store_versioning_on_content_change(tmp_path):
    path = tmp_path / "articles.jsonl"
    store = ArticleCorpusStore(store_path=str(path))

    doc_v1 = {
        "id": "et-1",
        "title": "Sample",
        "published_at": "2026-01-01T00:00:00+00:00",
        "category": "general",
        "content": "initial content",
        "author": "A",
        "tags": ["tag1"],
        "url": "https://economictimes.com/news/a",
        "source": "economictimes",
    }

    doc_v2 = {**doc_v1, "content": "updated content with new facts"}

    inserted_1 = store.upsert_articles([doc_v1])
    inserted_2 = store.upsert_articles([doc_v2])

    assert inserted_1 == 1
    assert inserted_2 == 0

    docs = store._read_docs()
    assert len(docs) == 1
    assert int(docs[0]["version"]) == 2
    assert docs[0]["previous_doc_uid"]
