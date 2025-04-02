import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import csv
import datetime
import re
import sys  # Added for command-line arguments

def is_subdomain_of(url_netloc, main_domain):
    """Check if the URL belongs to the main domain or its subdomains."""
    main_parts = main_domain.split('.')
    url_parts = url_netloc.split('.')
    return url_parts[-len(main_parts):] == main_parts

def normalize_text(text):
    """Normalize text by removing special characters and converting to lowercase."""
    return re.sub(r'[^\w\s-]', '', text.lower()).strip()

def contains_keyword(text, keywords):
    """Check if any keyword exists in the text (case-insensitive)."""
    text = normalize_text(text)
    normalized_keywords = [re.sub(r'[\s-]', '', keyword.lower()) for keyword in keywords]
    normalized_text = re.sub(r'[\s-]', '', text)
    return any(re.search(rf'{re.escape(keyword)}', normalized_text) for keyword in normalized_keywords)

def process_url(url, main_domain, visited, results):
    """Process a URL to check for keywords in content, banners, and external links."""
    if url in visited:
        return []
    visited.add(url)
    print(f"\nCrawling: {url}")

    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    if 'text/html' not in response.headers.get('Content-Type', ''):
        return []

    final_url = response.url
    parsed_url = urlparse(final_url)
    
    if not is_subdomain_of(parsed_url.netloc, main_domain):
        print(f"Skipping non-subdomain: {final_url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    keywords = ["gowithguide", "go with guide", "go-with-guide", "87121"]

    def check_banner(element):
        banner_text = element.get_text(separator=' ', strip=True)
        if contains_keyword(banner_text, keywords):
            print(f"Keyword found in banner text: {final_url}")
            results.append((final_url, "Keyword in banner text", str(element)[:100]))
            return True

        for img in element.find_all('img'):
            alt_text = img.get('alt', '')
            if contains_keyword(alt_text, keywords):
                print(f"Keyword found in banner image alt: {final_url}")
                results.append((final_url, "Keyword in banner image alt", str(img)[:100]))
                return True

        style = element.get('style', '')
        if 'background-image' in style and contains_keyword(style, keywords):
            print(f"Keyword found in banner background: {final_url}")
            results.append((final_url, "Keyword in banner background", str(element)[:100]))
            return True

        return False

    banner_containers = soup.find_all(['div', 'section', 'header', 'footer', 'aside', 'article', 'nav'])
    for container in banner_containers:
        classes = container.get('class', [])
        banner_terms = ['banner', 'promo', 'cta', 'ad', 'widget', 'offer']
        is_banner = any(term in ' '.join(classes).lower() for term in banner_terms)
        
        if is_banner or check_banner(container):
            continue
        
        for child in container.find_all(True):
            check_banner(child)

    content_sections = [
        soup.find('main'), soup.find('article'), soup.find('div', class_='content')
    ]
    for section in filter(None, content_sections):
        section_text = section.get_text(separator=' ', strip=True)
        if contains_keyword(section_text, keywords):
            print(f"Keyword found in main content: {final_url}")
            results.append((final_url, "Keyword in main content", ""))

    for element in soup.find_all(['a', 'link', 'area', 'base']):
        href = element.get('href')
        if href:
            absolute_url = urljoin(final_url, href)
            parsed_link = urlparse(absolute_url)
            
            link_text = element.get_text(strip=True)
            if contains_keyword(link_text, keywords) or contains_keyword(absolute_url, keywords):
                print(f"Keyword found in link: {absolute_url}")
                results.append((final_url, "Keyword in link", absolute_url))

    extracted_links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href:
            absolute_url = urljoin(final_url, href)
            parsed_link = urlparse(absolute_url)
            
            if is_subdomain_of(parsed_link.netloc, main_domain):
                if absolute_url not in visited:
                    extracted_links.append(absolute_url)
                    print(f"Added to queue: {absolute_url}")

    return extracted_links

def save_to_csv(results, filename):
    """Save results to a CSV file."""
    if not results:
        return
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Source URL", "Match Type", "Match Context"])
        for entry in results:
            writer.writerow(entry)
    print(f"Results saved to {filename}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <url>")
        sys.exit(1)
    
    initial_url = sys.argv[1].strip()
    if not initial_url.startswith(('http://', 'https://')):
        initial_url = f'https://{initial_url}'
    
    parsed_initial = urlparse(initial_url)
    main_domain = parsed_initial.netloc

    queue = deque([initial_url])
    visited = set()
    results = []

    while queue:
        url = queue.popleft()
        new_links = process_url(url, main_domain, visited, results)
        for link in new_links:
            if link not in visited:
                queue.append(link)

    if results:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"banner_results_{timestamp}.csv"
        save_to_csv(results, filename)
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()
