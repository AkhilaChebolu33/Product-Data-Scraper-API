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
            # Non-headless for debugging, switch to True when done
            browser = await p.chromium.launch(headless=False, args=['--disable-dev-shm-usage'])
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/118.0.5993.118 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()

            price = None
            image_url = None

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(5000)

                print(f"[DEBUG] Navigated to: {page.url}")

                # Wait for DOM content loaded + extra time for JS
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(7000)

                content = await page.content()
                print(f"[DEBUG] Page content length: {len(content)}")
                print(f"[DEBUG] Page snippet:\n{content[:1000]}")  # first 1000 chars

                # -------------------------
                # LOWE'S
                # -------------------------
                if "lowes.com" in domain:
                    try:
                        el = await page.query_selector('div[data-testid="product-details-price"] span')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Lowe's price:", price)
                    except Exception as e:
                        print("[DEBUG] Lowe's price selector failed:", e)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Lowe's image URL:", image_url)

                # -------------------------
                # HOME DEPOT
                # -------------------------
                elif "homedepot.com" in domain:
                    try:
                        el = await page.query_selector('span[data-automation-id="product-price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Home Depot price:", price)
                    except Exception as e:
                        print("[DEBUG] Home Depot price selector failed:", e)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Home Depot image URL:", image_url)

                # -------------------------
                # AMAZON
                # -------------------------
                elif "amazon.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[class="a-price-symbol"]', timeout=60000, state="attached")
                    await page.wait_for_selector('[class="a-price-whole"]', timeout=60000, state="attached")
                    await page.wait_for_selector('[class="a-price-decimal"]', timeout=60000, state="attached")
                    await page.wait_for_selector('[class="a-price-fraction"]', timeout=60000, state="attached")

                    ## price_symbol = await page.text_content('[class="a-price-symbol"]')
                    price_dollars = await page.text_content('[class="a-price-whole"]')
                    ## price_decimal = await page.text_content('[class="a-price-decimal"]')
                    price_cents = await page.text_content('[class="a-price-fraction"]')
                    price = f"${price_dollars.strip()}{price_cents.strip()}"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="m.media-amazon.com/images/I"]', timeout=60000, state="attached")
                    image_element = await page.query_selector('img[src*="m.media-amazon.com/images/I"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    # print(f"\n\n\nPrice: {price}")
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                    await browser.close()

                # -------------------------
                # WALMART
                # -------------------------
                elif "walmart.com" in domain:
                    try:
                        el = await page.query_selector('span[itemprop="price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Walmart primary price selector price:", price)
                    except Exception as e:
                        print("[DEBUG] Walmart primary selector failed:", e)

                    if not price:
                        el2 = await page.query_selector('span[data-automation-id="product-price"]')
                        price = await el2.inner_text() if el2 else None
                        print("[DEBUG] Walmart fallback price selector:", price)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Walmart image_url:", image_url)

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
                print(f"[ERROR] Scraping failed: {str(e)}")
                return {'error': f'Scraping failed: {str(e)}'}

    try:
        result = asyncio.run(asyncio.wait_for(run_scraper(), timeout=120))
        return jsonify(result)
    except asyncio.TimeoutError:
        print("[ERROR] Scraping timed out.")
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