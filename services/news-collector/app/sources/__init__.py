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
    # The Record is Recorded Future's news arm (daily cybersecurity reporting).
    # https://www.recordedfuture.com/feed is the corporate blog and posts once every few days,
    # so we keep this pointed at therecord.media for current intel.
    SeedFeed("recordedfuture", "https://therecord.media/feed/", 0.85),
    SeedFeed("stepsecurity", "https://www.stepsecurity.io/blog/rss.xml", 0.75),
    SeedFeed("cisa-advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml", 0.95),
    SeedFeed("cisa-ics", "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml", 0.95),
]
