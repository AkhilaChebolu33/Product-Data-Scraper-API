from flask import Flask, request, jsonify
from playwright.async_api import async_playwright
import asyncio
import os
import threading
import time
import requests
from urllib.parse import urlparse

app = Flask(__name__)

def get_retailer_domain(url):
    return urlparse(url).netloc.lower()

@app.route('/scrape-product', methods=['POST'])
def scrape_product():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'Missing product URL'}), 400

    async def run_scraper():
        domain = get_retailer_domain(url)
        async with async_playwright() as p:
            ## browser = await p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])

            browser = await p.chromium.launch(
                headless=True, 
                proxy={
                    "server": "http://your-proxy-server:port",  # e.g., "http://proxy.example.com:8080"
                    "username": "achebolu@na.chervongroup.com",                # optional
                    "password": "HelloWorld123"                 # optional
                },
                args=['--disable-dev-shm-usage']
            )

            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()

            price = None
            image_url = None

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(4000)

                # -------------------------
                # LOWE'S
                # -------------------------
                if "lowes.com" in domain:
                    try:
                        await page.wait_for_selector('[data-testid="product-price"]', timeout=10000)
                        el = await page.query_selector('[data-testid="product-price"]')
                        price = await el.inner_text() if el else None
                        if price:
                            price = price.strip()
                    except:
                        pass

                    if not price:
                        # fallback
                        dollar_span = await page.query_selector('span.item-price-dollar')
                        cent_div = await page.query_selector('div.item-price-cent')
                        dollar = await dollar_span.inner_text() if dollar_span else ''
                        cent = await cent_div.inner_text() if cent_div else ''
                        if dollar:
                            price = f"${dollar}{cent}"

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None

                # -------------------------
                # HOME DEPOT
                # -------------------------
                elif "homedepot.com" in domain:
                    try:
                        await page.wait_for_selector('.price-format__large-price', timeout=10000)
                        el = await page.query_selector('.price-format__large-price')
                        price = await el.inner_text() if el else None
                    except:
                        pass

                    if not price:
                        el = await page.query_selector('[itemprop="price"]')
                        if el:
                            price = await el.get_attribute('content')

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None

                # -------------------------
                # AMAZON
                # -------------------------
                elif "amazon.com" in domain:
                    try:
                        await page.wait_for_selector('#corePriceDisplay_desktop_feature_div', timeout=10000)
                        el = await page.query_selector('#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen')
                        price = await el.inner_text() if el else None
                    except:
                        pass

                    if not price:
                        el = await page.query_selector('#priceblock_ourprice, #priceblock_dealprice')
                        price = await el.inner_text() if el else None

                    img = await page.query_selector('#landingImage')
                    image_url = await img.get_attribute('src') if img else None

                # -------------------------
                # WALMART
                # -------------------------
                elif "walmart.com" in domain:
                    try:
                        await page.wait_for_selector('span[itemprop="price"]', timeout=10000)
                        el = await page.query_selector('span[itemprop="price"]')
                        price = await el.inner_text() if el else None
                    except:
                        pass

                    if not price:
                        el = await page.query_selector('[data-automation-id="product-price"]')
                        price = await el.inner_text() if el else None

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None

                # -------------------------
                # FALLBACK — OG IMAGE / META PRICE
                # -------------------------
                if not image_url:
                    og_img = await page.query_selector('meta[property="og:image"]')
                    image_url = await og_img.get_attribute('content') if og_img else None

                if not price:
                    meta_price = await page.query_selector('meta[itemprop="price"]')
                    price = await meta_price.get_attribute('content') if meta_price else None

                await browser.close()
                return {
                    'image_url': image_url or 'Not found',
                    'price': price.strip() if price else 'Not found'
                }

            except Exception as e:
                await browser.close()
                return {'error': f'Scraping failed: {str(e)}'}

    try:
        result = asyncio.run(asyncio.wait_for(run_scraper(), timeout=90))
        return jsonify(result)
    except asyncio.TimeoutError:
        return jsonify({'error': 'Scraping timed out'}), 504

@app.route('/')
def home():
    return "Service is running"

def keep_alive():
    def ping():
        while True:
            try:
                requests.get("https://your-app-url.onrender.com")
                print("[INFO] Keep-alive ping successful")
            except Exception as e:
                print(f"[WARNING] Keep-alive ping failed: {e}")
            time.sleep(30)

    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()

keep_alive()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
