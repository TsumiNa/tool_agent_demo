import requests
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from tool_agent_demo import Agent, Result


class WebScrapingAgent(Agent):
    def __init__(self):
        super().__init__()
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.session = None

    @Agent.tool
    def fetch_page(self, url: str, cache: bool = True) -> str:
        """Fetch a web page with caching support"""
        if cache:
            cache_file = self.cache_dir / f"{hash(url)}.html"
            if cache_file.exists():
                return cache_file.read_text()

        response = requests.get(url)
        content = response.text
        if cache:
            cache_file.write_text(content)
        return content

    @Agent.tool
    def extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all links from HTML content"""
        time.sleep(0.2)  # Simulate processing time
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('http'):
                links.append(href)
            elif href.startswith('/'):
                links.append(f"{base_url.rstrip('/')}{href}")
        return links

    @Agent.tool
    def extract_text(self, html: str) -> str:
        """Extract main text content from HTML"""
        time.sleep(0.3)  # Simulate processing time
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip()
                  for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)

    @Agent.tool
    def analyze_text(self, text: str) -> Dict:
        """Analyze text content"""
        time.sleep(0.5)  # Simulate analysis time
        words = text.split()
        return {
            "word_count": len(words),
            "avg_word_length": sum(len(word) for word in words) / len(words),
            "paragraph_count": text.count('\n\n') + 1
        }

    @Agent.tool
    def save_results(self, data: Dict, filename: str) -> str:
        """Save analysis results to file"""
        filepath = self.cache_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return str(filepath)

    @Agent.workflow
    def analyze_website(self, url: str, max_pages: int = 3) -> Result:
        """Complex workflow to analyze a website"""
        results = {
            "pages": [],
            "total_words": 0,
            "total_links": 0,
            "avg_word_length": 0.0
        }

        # Fetch and analyze the main page first
        main_page = self.fetch_page(url)
        if main_page.is_err():
            return main_page

        # Extract links for further analysis
        links = self.extract_links(main_page.unwrap(), url)
        if links.is_err():
            return links

        # Analyze main page content
        text = self.extract_text(main_page.unwrap())
        if text.is_err():
            return text

        analysis = self.analyze_text(text.unwrap())
        if analysis.is_err():
            return analysis

        # Add main page results
        results["pages"].append({
            "url": url,
            "analysis": analysis.unwrap()
        })
        results["total_words"] += analysis.unwrap()["word_count"]
        results["total_links"] += len(links.unwrap())

        # Analyze linked pages (up to max_pages)
        for link in links.unwrap()[:max_pages-1]:
            # Fetch and analyze linked page
            page = self.fetch_page(link)
            if page.is_err():
                continue

            text = self.extract_text(page.unwrap())
            if text.is_err():
                continue

            analysis = self.analyze_text(text.unwrap())
            if analysis.is_err():
                continue

            # Add page results
            results["pages"].append({
                "url": link,
                "analysis": analysis.unwrap()
            })
            results["total_words"] += analysis.unwrap()["word_count"]

            # Extract and count links
            page_links = self.extract_links(page.unwrap(), link)
            if page_links.is_ok():
                results["total_links"] += len(page_links.unwrap())

        # Calculate average word length across all pages
        total_pages = len(results["pages"])
        if total_pages > 0:
            avg_lengths = [page["analysis"]["avg_word_length"]
                           for page in results["pages"]]
            results["avg_word_length"] = sum(avg_lengths) / total_pages

        # Save final results
        return self.save_results(results, "website_analysis.json")

    @Agent.workflow
    def parallel_site_analysis(self, urls: List[str]) -> Result:
        """Analyze multiple websites in parallel"""
        results = {}

        # Create tasks for each URL
        tasks = []
        for url in urls:
            for result in self.analyze_website(url, max_pages=2):
                if result.is_err():
                    results[url] = {"error": str(result.error)}
                else:
                    tasks.append(result)

        # Wait for all tasks to complete
        if tasks:
            completed = [task.unwrap() for task in tasks]
            for url, result in zip(urls, completed):
                if isinstance(result, Exception):
                    results[url] = {"error": str(result)}
                else:
                    results[url] = result

        # Save combined results
        return self.save_results(results, "parallel_analysis.json")


def main():
    # Create the agent
    agent = WebScrapingAgent()

    print("=== Single Website Analysis ===")
    print("\nAnalyzing example.com...")

    # Analyze a single website
    start_time = time.time()
    for result in agent.analyze_website("http://example.com"):
        if result.is_err():
            print(f"Error: {result.error}")
            break
        final_result = result

    if 'final_result' in locals() and final_result.is_ok():
        print(f"Analysis completed in {time.time() - start_time:.2f} seconds")
        with open(final_result.unwrap()) as f:
            analysis = json.load(f)
            print("\nResults:")
            print(f"Total pages analyzed: {len(analysis['pages'])}")
            print(f"Total words: {analysis['total_words']}")
            print(f"Total links: {analysis['total_links']}")
            print(f"Average word length: {analysis['avg_word_length']:.2f}")

    print("\n=== Parallel Website Analysis ===")
    urls = [
        "http://example.com",
        "http://example.org",
        "http://example.net"
    ]
    print(f"\nAnalyzing {len(urls)} websites in parallel...")

    start_time = time.time()
    for result in agent.parallel_site_analysis(urls):
        if result.is_err():
            print(f"Error: {result.error}")
            break
        final_result = result

    if 'final_result' in locals() and final_result.is_ok():
        print(f"Parallel analysis completed in {
              time.time() - start_time:.2f} seconds")
        with open(final_result.unwrap()) as f:
            results = json.load(f)
            print("\nResults by website:")
            for url, data in results.items():
                if "error" in data:
                    print(f"\n{url}: Error - {data['error']}")
                else:
                    print(f"\n{url}:")
                    print(f"Analysis saved to: {data}")

    # Cleanup
    if agent.session:
        agent.session.close()


if __name__ == "__main__":
    main()
