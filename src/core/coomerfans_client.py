import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class CoomerfansClient:
    def __init__(self):
        self.base_url = "https://coomerfans.com"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def get_posts_from_page(self, page_url):
        """Scrapes the <div class='post'> elements to find all post links."""
        try:
            response = self.session.get(page_url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            post_links = []
            
            # Find all the post containers
            posts = soup.find_all('div', class_='post')
            for post in posts:
                # Find the 'View Post' button
                a_tag = post.find('a', class_='view-post')
                if a_tag and 'href' in a_tag.attrs:
                    full_link = urljoin(self.base_url, a_tag['href'])
                    post_links.append(full_link)
                    
            return post_links
        except Exception:
            return []

    def get_media_from_post(self, post_url):
        """Scrapes the post page to find high-res images and direct mp4 links."""
        media_urls = []
        try:
            response = self.session.get(post_url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return media_urls
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Extract Images (<div class="post-body"> -> <img>)
            post_body = soup.find('div', class_='post-body')
            if post_body:
                images = post_body.find_all('img')
                for img in images:
                    if 'src' in img.attrs:
                        media_urls.append(img['src'])
                        
            # 2. Extract Videos (<div class="player"> -> <source>)
            players = soup.find_all('div', class_='player')
            for player in players:
                source = player.find('source')
                if source and 'src' in source.attrs:
                    media_urls.append(source['src'])
                    
            return media_urls
        except Exception:
            return media_urls