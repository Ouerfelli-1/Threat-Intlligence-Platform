from dataclasses import dataclass


@dataclass
class SeedFeed:
    name: str
    url: str
    reliability: float


DEFAULT_FEEDS: list[SeedFeed] = [
    SeedFeed("hackernews", "https://feeds.feedburner.com/TheHackersNews", 0.75),
    SeedFeed("malwarebytes", "https://www.malwarebytes.com/blog/feed", 0.85),
    SeedFeed("tenable", "https://www.tenable.com/blog/feed", 0.85),
    SeedFeed("recordedfuture", "https://www.recordedfuture.com/feed", 0.85),
    SeedFeed("stepsecurity", "https://www.stepsecurity.io/blog/rss.xml", 0.75),
    SeedFeed("cisa-advisories", "https://www.cisa.gov/cybersecurity-advisories/feed", 0.95),
    SeedFeed("cisa-ics", "https://www.cisa.gov/ics-advisories/feed", 0.95),
]
