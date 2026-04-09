"""
ingest_agent.py
---------------
Busca notícias sobre Trump nas fontes configuradas, normaliza o formato
e persiste na tabela raw_articles do Supabase com status='pending'.

Fluxo:
  1. Lê config/sources.yml para queries e fontes ativas
  2. Busca em paralelo: NewsAPI, GDELT, Guardian, RSS
  3. Filtra por relevância (sem IA — regex + keywords)
  4. Dedup por URL contra o banco (SELECT em batch antes de INSERT)
  5. Insere novos artigos com status='pending'
  6. Imprime relatório

Uso:
  python agents/ingest_agent.py
  python agents/ingest_agent.py --lookback-hours 48
  python agents/ingest_agent.py --dry-run
  python agents/ingest_agent.py --source gdelt
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import feedparser
import httpx
import yaml
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

REQUIRED_ENV = ["SUPABASE_URL", "SUPABASE_KEY"]
OPTIONAL_ENV = ["NEWSAPI_KEY", "GUARDIAN_API_KEY"]

RELEVANCE_TERMS = [
    "trump", "white house", "executive order", "president trump",
    "mar-a-lago", "truth social", "trump administration",
    # pt-BR (G1 e outras fontes lusófonas)
    "casa branca", "governo trump", "ordem executiva", "presidente trump", "presidente dos estados unidos"
]

HIGH_PRIORITY_TERMS = [
    "unprecedented", "first time", "never before", "reversal", "reversed",
    "fires", "fired", "dismissed", "emergency", "tariff", "pardon",
    "invoke", "invokes", "suspend", "overturns", "defies", "blocks",
    "sued", "indicted", "arrested", "admits",
]


@dataclass
class RawArticle:
    url: str
    title: str
    body: str
    source_name: str
    source_tier: int
    published_at: datetime
    raw_query: str
    priority: bool = False

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()[:16]

    def to_db_row(self) -> dict:
        return {
            "url": self.url,
            "url_hash": self.url_hash,
            "title": self.title,
            "body": self.body[:2000],
            "source_name": self.source_name,
            "source_tier": self.source_tier,
            "published_at": self.published_at.isoformat(),
            "status": "pending",
            "priority": self.priority,
            "raw_query": self.raw_query,
        }


@dataclass
class IngestReport:
    source_counts: dict = field(default_factory=dict)
    raw_fetched: int = 0
    after_relevance_filter: int = 0
    already_in_db: int = 0
    inserted: int = 0
    errors: list[str] = field(default_factory=list)

    def add_source(self, name: str, count: int):
        self.source_counts[name] = count
        self.raw_fetched += count

    def print(self):
        print("\n" + "─" * 55)
        print("✅  Ingestão concluída")
        print("─" * 55)
        for src, n in self.source_counts.items():
            print(f"   {src:<20} {n:>4} artigos brutos")
        print(f"\n   Total bruto:           {self.raw_fetched:>4}")
        print(f"   Após filtro relevância: {self.after_relevance_filter:>4}")
        print(f"   Já no banco (dedup):   {self.already_in_db:>4}")
        print(f"   ✨ Inseridos (pending): {self.inserted:>4}")
        if self.errors:
            print(f"\n   ⚠️  Erros ({len(self.errors)}):")
            for e in self.errors:
                print(f"      • {e}")
        print(f"\n   Próximo passo: classify_agent.py")
        print("─" * 55 + "\n")


def load_config(path: str = "config/sources.yml") -> dict:
    if not os.path.exists(path):
        log.error(f"Config não encontrada: {path}")
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def check_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        sys.exit(1)
    for k in OPTIONAL_ENV:
        if not os.getenv(k):
            log.warning(f"{k} não definida — fonte correspondente será pulada.")


def is_relevant(title: str) -> bool:
    t = title.lower()
    return any(term in t for term in RELEVANCE_TERMS)


def is_high_priority(title: str) -> bool:
    t = title.lower()
    return any(term in t for term in HIGH_PRIORITY_TERMS)


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y%m%d%H%M%S",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def gdelt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


async def fetch_newsapi(
    client: httpx.AsyncClient,
    queries: list[str],
    since: datetime,
    api_key: str,
) -> list[RawArticle]:
    if not api_key:
        return []
    combined_query = " OR ".join(f'"{q}"' for q in queries[:5])
    params = {
        "q": combined_query,
        "from": since.strftime("%Y-%m-%dT%H:%M:%S"),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 100,
        "apiKey": api_key,
    }
    try:
        r = await client.get("https://newsapi.org/v2/everything", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            log.warning("NewsAPI: rate limit atingido. Pulando.")
        else:
            log.warning(f"NewsAPI: erro HTTP {e.response.status_code}")
        return []
    except Exception as e:
        log.warning(f"NewsAPI: falha — {e}")
        return []

    articles = []
    for item in data.get("articles", []):
        url = item.get("url", "")
        title = item.get("title", "") or ""
        if not url or not title or url == "[Removed]":
            continue
        articles.append(RawArticle(
            url=url,
            title=title,
            body=(item.get("description") or "") + " " + (item.get("content") or ""),
            source_name=item.get("source", {}).get("name", "NewsAPI"),
            source_tier=2,
            published_at=parse_datetime(item.get("publishedAt")),
            raw_query=combined_query,
            priority=is_high_priority(title),
        ))
    log.info(f"NewsAPI: {len(articles)} artigos")
    return articles


async def fetch_gdelt(
    client: httpx.AsyncClient,
    queries: list[str],
    since: datetime,
) -> list[RawArticle]:
    articles = []
    for query in queries:
        params = {
            "query": f"{query} sourcelang:english",
            "mode": "artlist",
            "maxrecords": 250,
            "format": "json",
            "startdatetime": gdelt_datetime(since),
            "sort": "DateDesc",
        }
        try:
            r = await client.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException:
            log.warning(f"GDELT: timeout para '{query}'. Pulando.")
            continue
        except Exception as e:
            log.warning(f"GDELT: erro para '{query}' — {e}")
            continue

        for item in data.get("articles", []):
            url = item.get("url", "")
            title = item.get("title", "") or ""
            if not url or not title:
                continue
            articles.append(RawArticle(
                url=url,
                title=title,
                body=item.get("seendate", ""),
                source_name=item.get("domain", "GDELT"),
                source_tier=2,
                published_at=parse_datetime(item.get("seendate")),
                raw_query=query,
                priority=is_high_priority(title),
            ))
        await asyncio.sleep(0.5)

    log.info(f"GDELT: {len(articles)} artigos")
    return articles


async def fetch_guardian(
    client: httpx.AsyncClient,
    queries: list[str],
    since: datetime,
    api_key: str,
) -> list[RawArticle]:
    if not api_key:
        return []
    articles = []
    since_date = since.strftime("%Y-%m-%d")
    for query in queries[:4]:
        params = {
            "q": query,
            "from-date": since_date,
            "order-by": "newest",
            "show-fields": "headline,bodyText,shortUrl",
            "page-size": 50,
            "api-key": api_key,
        }
        try:
            r = await client.get(
                "https://content.guardianapis.com/search",
                params=params,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.warning("Guardian API: chave inválida. Pulando.")
                return articles
            log.warning(f"Guardian API: erro {e.response.status_code}")
            continue
        except Exception as e:
            log.warning(f"Guardian API: falha — {e}")
            continue

        for item in data.get("response", {}).get("results", []):
            url = item.get("webUrl", "")
            fields = item.get("fields", {})
            title = fields.get("headline") or item.get("webTitle", "")
            if not url or not title:
                continue
            articles.append(RawArticle(
                url=url,
                title=title,
                body=(fields.get("bodyText") or "")[:2000],
                source_name="The Guardian",
                source_tier=2,
                published_at=parse_datetime(item.get("webPublicationDate")),
                raw_query=query,
                priority=is_high_priority(title),
            ))

    log.info(f"Guardian: {len(articles)} artigos")
    return articles


async def fetch_rss(
    client: httpx.AsyncClient,
    feeds: list[dict],
    since: datetime,
) -> list[RawArticle]:
    articles = []
    for feed_config in feeds:
        url = feed_config["url"]
        name = feed_config["name"]
        tier = feed_config.get("tier", 1)
        try:
            r = await client.get(url, timeout=15, follow_redirects=True)
            r.raise_for_status()
            feed = feedparser.parse(r.text)
        except Exception as e:
            log.warning(f"RSS [{name}]: erro — {e}")
            continue

        for entry in feed.entries:
            title = entry.get("title", "") or ""
            link = entry.get("link", "") or ""
            summary = entry.get("summary", "") or ""
            if not link or not title:
                continue
            published_raw = entry.get("published") or entry.get("updated")
            published = parse_datetime(published_raw)
            if published < since:
                continue
            if not is_relevant(title):
                continue
            articles.append(RawArticle(
                url=link,
                title=title,
                body=summary[:2000],
                source_name=name,
                source_tier=tier,
                published_at=published,
                raw_query="rss",
                priority=is_high_priority(title),
            ))

    log.info(f"RSS: {len(articles)} artigos relevantes")
    return articles


def dedup_against_db(
    articles: list[RawArticle],
    supabase: Client,
) -> tuple[list[RawArticle], int]:
    if not articles:
        return [], 0
    url_to_article = {a.url: a for a in articles}
    all_urls = list(url_to_article.keys())
    existing_urls: set[str] = set()

    batch_size = 500
    for i in range(0, len(all_urls), batch_size):
        batch = all_urls[i : i + batch_size]
        try:
            result = (
                supabase.table("raw_articles")
                .select("url")
                .in_("url", batch)
                .execute()
            )
            for row in result.data:
                existing_urls.add(row["url"])
        except Exception as e:
            log.warning(f"Erro ao checar duplicatas: {e}")

    new_articles = [a for a in articles if a.url not in existing_urls]
    duplicates = len(articles) - len(new_articles)
    return new_articles, duplicates


def insert_articles(
    articles: list[RawArticle],
    supabase: Client,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    if not articles or dry_run:
        if dry_run:
            log.info(f"[DRY RUN] Seriam inseridos: {len(articles)} artigos")
        return 0, []

    rows = [a.to_db_row() for a in articles]
    errors = []
    inserted = 0

    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            result = (
                supabase.table("raw_articles")
                .upsert(batch, on_conflict="url", ignore_duplicates=True)
                .execute()
            )
            inserted += len(result.data)
        except Exception as e:
            err = f"Erro ao inserir batch {i//batch_size + 1}: {e}"
            log.error(err)
            errors.append(err)

    return inserted, errors


async def run(
    lookback_hours: int = 4,
    dry_run: bool = False,
    source_filter: Optional[str] = None,
):
    check_env()
    config = load_config()

    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    log.info(f"Buscando artigos desde {since.strftime('%Y-%m-%d %H:%M')} UTC")

    queries_primary = config.get("queries", {}).get("primary", [])
    all_articles: list[RawArticle] = []
    report = IngestReport()

    async with httpx.AsyncClient(
        headers={"User-Agent": "TrumpTracker/1.0 (news aggregator)"},
        follow_redirects=True,
    ) as client:
        tasks = {}

        if not source_filter or source_filter == "newsapi":
            if os.getenv("NEWSAPI_KEY"):
                tasks["newsapi"] = fetch_newsapi(
                    client, queries_primary, since, os.environ["NEWSAPI_KEY"]
                )
        if not source_filter or source_filter == "gdelt":
            tasks["gdelt"] = fetch_gdelt(client, queries_primary, since)
        if not source_filter or source_filter == "guardian":
            if os.getenv("GUARDIAN_API_KEY"):
                tasks["guardian"] = fetch_guardian(
                    client, queries_primary, since, os.environ["GUARDIAN_API_KEY"]
                )
        if not source_filter or source_filter == "rss":
            rss_feeds = config.get("rss_feeds", [])
            if rss_feeds:
                tasks["rss"] = fetch_rss(client, rss_feeds, since)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                log.error(f"Fonte '{name}' falhou: {result}")
                report.errors.append(f"{name}: {result}")
                report.add_source(name, 0)
            else:
                report.add_source(name, len(result))
                all_articles.extend(result)

    relevant = [a for a in all_articles if is_relevant(a.title)]
    report.after_relevance_filter = len(relevant)

    new_articles, already_in_db = dedup_against_db(relevant, supabase)
    report.already_in_db = already_in_db

    new_articles.sort(key=lambda a: (not a.priority, -a.published_at.timestamp()))

    inserted, errors = insert_articles(new_articles, supabase, dry_run=dry_run)
    report.inserted = inserted
    report.errors.extend(errors)
    report.print()
    return report


def main():
    parser = argparse.ArgumentParser(description="Trump Tracker — Ingest Agent")
    parser.add_argument("--lookback-hours", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--source",
        choices=["newsapi", "gdelt", "guardian", "rss"],
        default=None,
    )
    args = parser.parse_args()
    asyncio.run(run(
        lookback_hours=args.lookback_hours,
        dry_run=args.dry_run,
        source_filter=args.source,
    ))


if __name__ == "__main__":
    main()