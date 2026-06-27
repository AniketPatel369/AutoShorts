"""
Auto Shorts — Module: Trend Crawler

Extracts video tags, hashtags, and categories from metadata as trends 
and saves them to analysis/trends.json.

Input:  downloads/metadata.json
Output: analysis/trends.json
"""
import logging
import re
from pathlib import Path

from auto_shorts.utils.file_utils import read_json, write_json

logger = logging.getLogger(__name__)


def crawl_trends(project_dir: Path) -> str:
    """
    Extract tags, categories, and description keywords from metadata.json
    and save them to analysis/trends.json.
    """
    analysis_dir = project_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    trends_path = analysis_dir / "trends.json"
    
    if trends_path.exists():
        logger.info("Trends already crawled, skipping")
        return str(trends_path)

    metadata_path = project_dir / "downloads" / "metadata.json"
    if not metadata_path.exists():
        logger.warning("No metadata.json found to extract trends from. Saving empty trends.")
        write_json(trends_path, {})
        return str(trends_path)

    metadata = read_json(metadata_path)
    
    title = metadata.get("title", "")
    description = metadata.get("description", "")
    tags = metadata.get("tags", [])
    categories = metadata.get("categories", [])

    # Extract hashtags from description
    hashtags = re.findall(r"#\w+", description)
    # Remove duplicates and normalize to lowercase
    hashtags = list(set([h.lower() for h in hashtags]))

    # Simple keyword extraction from title (words longer than 4 chars)
    title_keywords = [w.strip(".,!?\"'()").lower() for w in title.split()]
    title_keywords = [w for w in title_keywords if len(w) > 4 and w.isalnum()]
    title_keywords = list(set(title_keywords))

    trends_data = {
        "title": title,
        "categories": categories,
        "tags": tags,
        "hashtags": hashtags,
        "keywords": title_keywords,
        "summary": f"Video titled '{title}' categorized as {', '.join(categories)} with tags: {', '.join(tags[:10])}."
    }

    write_json(trends_path, trends_data)
    logger.info(f"Saved trends analysis to {trends_path}")
    
    return str(trends_path)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m auto_shorts.modules.trend_crawler <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    out_path = crawl_trends(project_dir)
    print(f"Done. Output at: {out_path}")
