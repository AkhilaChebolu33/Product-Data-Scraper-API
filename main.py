from flask import Flask, request, jsonify
from playwright.async_api import async_playwright
import asyncio
import os
import threading
import time
import requests
import traceback
from urllib.parse import urlparse

app = Flask(__name__)

def get_retailer_domain(url):
    return urlparse(url).netloc.lower()

BRIGHTDATA_USERNAME = os.getenv("BRIGHTDATA_USERNAME")
BRIGHTDATA_PASSWORD = os.getenv("BRIGHTDATA_PASSWORD")
BRIGHTDATA_HOST = os.getenv("BRIGHTDATA_HOST", "zproxy.lum-superproxy.io")
BRIGHTDATA_PORT = os.getenv("BRIGHTDATA_PORT", "22225")

proxy_url = f"http://{BRIGHTDATA_USERNAME}:{BRIGHTDATA_PASSWORD}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}"

@app.route('/scrape-product', methods=['POST'])
def scrape_product():
    data = request.get_json()
    url = data.get('url')
    browser_type = data.get('browser', 'chromium')  # Default to Chromium

    if not url:
        return jsonify({'error': 'Missing product URL'}), 400

    async def run_scraper():
        domain = get_retailer_domain(url)
        async with async_playwright() as p:
            # Choose browser dynamically
            if browser_type == 'webkit':
                browser = await p.webkit.launch(headless=True, args=['--disable-dev-shm-usage', '--no-sandbox', f'--proxy-server={proxy_url}'])
            elif browser_type == 'firefox':
                browser = await p.firefox.launch(headless=True, args=['--disable-dev-shm-usage'])
            else:
                browser = await p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])

            context = await browser.new_context(ignore_https_errors=True, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
            viewport={"width": 1280, "height": 800})
            page = await context.new_page()

            price = None
            image_src = None

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(2000)

                # -------------------------
                # LOWE'S
                # -------------------------
                if "lowes.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[data-automation-id="product-price"]', timeout=15000, state="attached")
                    price_dollars = await page.text_content('[data-automation-id="product-price"]')
                    price = price_dollars.strip() if price_dollars else "Price not found"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="lowes.com/product/"]', timeout=15000, state="attached")
                    image_element = await page.query_selector('img[src*="lowes.com/product/"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    print(f"Main Product Image URL: {image_src}\n\n\n")
                # -------------------------
                # HOME DEPOT
                # -------------------------
                elif "homedepot.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[class="sui-font-display sui-leading-none sui-text-3xl"]', timeout=15000, state="attached")
                    await page.wait_for_selector('[class="sui-font-display sui-leading-none sui-px-[2px] sui-text-9xl sui--translate-y-[0.5rem]"]', timeout=15000, state="attached")

                    price_parts = await page.query_selector_all('[class="sui-font-display sui-leading-none sui-text-3xl"]')
                    dollar_sign = await price_parts[0].text_content()
                    cents = await price_parts[1].text_content()
                    integer_part = await page.text_content('[class="sui-font-display sui-leading-none sui-px-[2px] sui-text-9xl sui--translate-y-[0.5rem]"]')
                    price = f"{dollar_sign}{integer_part}.{cents}"

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="images.thdstatic.com"]', timeout=15000, state="attached")
                    image_element = await page.query_selector('img[src*="images.thdstatic.com"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    print(f"\n\n\nPrice: {price}")
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                    

                # -------------------------
                # AMAZON
                # -------------------------
                elif "amazon.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[class="a-price-symbol"]', timeout=15000, state="attached")
                    await page.wait_for_selector('[class="a-price-whole"]', timeout=15000, state="attached")
                    await page.wait_for_selector('[class="a-price-decimal"]', timeout=15000, state="attached")
                    await page.wait_for_selector('[class="a-price-fraction"]', timeout=15000, state="attached")

                    ## price_symbol = await page.text_content('[class="a-price-symbol"]')
                    price_dollars = await page.text_content('[class="a-price-whole"]')
                    ## price_decimal = await page.text_content('[class="a-price-decimal"]')
                    price_cents = await page.text_content('[class="a-price-fraction"]')
                    price = f"${price_dollars.strip()}{price_cents.strip()}"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    # await page.wait_for_selector('img[src*="m.media-amazon.com/images/I"]', timeout=60000, state="attached")
                    # image_element = await page.query_selector('img[src*="m.media-amazon.com/images/I"]')
                    

                    await page.wait_for_selector('img#landingImage', timeout=15000, state="attached")
                    image_element = await page.query_selector('img#landingImage')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    # print(f"\n\n\nPrice: {price}")
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                    

                # -------------------------
                # WALMART
                # -------------------------
                elif "walmart.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[itemprop="price"]', timeout=1200000, state="attached")
                    # await page.wait_for_selector('[class="a-price-whole"]', timeout=60000, state="attached")
                    # await page.wait_for_selector('[class="a-price-decimal"]', timeout=60000, state="attached")
                    # await page.wait_for_selector('[class="a-price-fraction"]', timeout=60000, state="attached")

                    ## price_symbol = await page.text_content('[class="a-price-symbol"]')
                    price_dollars = await page.text_content('[itemprop="price"]')
                    ## price_decimal = await page.text_content('[class="a-price-decimal"]')
                    # price_cents = await page.text_content('[class="a-price-fraction"]')
                    price = f"{price_dollars.strip()}"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="i5.walmartimages.com/seo/"]', timeout=1200000, state="attached")
                    image_element = await page.query_selector('img[src*="i5.walmartimages.com/seo/"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    # print(f"\n\n\nPrice: {price}")
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                    

                # ----------------------------
                # Menards
                # ----------------------------
                elif "menards.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[class="price-big-val float-left"]', timeout=15000, state="attached")
                    await page.wait_for_selector('[class="cents-val float-left"]', timeout=15000, state="attached")

                    
                    price_dollars = await page.text_content('[class="price-big-val float-left"]')
                    price_cents = await page.text_content('[class="cents-val float-left"]')
                    price = f"${price_dollars.strip()}.{price_cents.strip()}"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="cdn.menardc.com/main/items/media/"]', timeout=15000, state="attached")
                    image_element = await page.query_selector('img[src*="cdn.menardc.com/main/items/media/"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                    


                # ----------------------------
                # Harbor Freight
                # ----------------------------
                elif "harborfreight.com" in domain:
                    await page.wait_for_load_state('networkidle')
                    try:
                        price_element = await page.query_selector('span[aria-label]')
                        price = await price_element.get_attribute('aria-label') if price_element else "Price not found"

                        await page.wait_for_selector('img[src*="www.harborfreight.com/media/catalog/product/"]', timeout=60000)
                        img_locator = page.locator('img[src*="www.harborfreight.com/media/catalog/product/"]')
                        await img_locator.wait_for(timeout=60000)
                        image_src = await img_locator.get_attribute('src')
                    except:
                        og_img = await page.query_selector('meta[property="og:image"]')
                        image_src = await og_img.get_attribute('content') if og_img else "Image not found"

                    

                # ----------------------------
                # Target
                # ----------------------------
                elif "target.com" in domain:
                    await page.wait_for_selector('[class="sc-44e8b7a0-1 LjEZN"]', timeout=15000)
                    price_dollars = await page.text_content('[class="sc-44e8b7a0-1 LjEZN"]')
                    price = price_dollars.strip() if price_dollars else "Price not found"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="target.scene7.com/is/image/Target/"]', timeout=15000)
                    image_element = await page.query_selector('img[src*="target.scene7.com/is/image/Target/"]')
                    image_src = await image_element.get_attribute('src')        
                    # --- Output Results ---
                    print(f"Main Product Image URL: {image_src}\n\n\n")
                    
                    
                # -------------------------
                # Tractor Supply Co.
                # -------------------------
                elif "tractorsupply.com" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[data-testid="product-price"]', timeout=15000, state="attached")
                    price_dollars = await page.text_content('[data-testid="product-price"]')
                    price = price_dollars.strip() if price_dollars else "Price not found"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="tractorsupply.com/is/image/TractorSupply/"]', timeout=15000, state="attached")
                    image_element = await page.query_selector('img[src*="tractorsupply.com/is/image/TractorSupply/"]')
                    image_src = await image_element.get_attribute('src')

                    # --- Output Results ---
                    print(f"Main Product Image URL: {image_src}\n\n\n")

                   
                
                # --------------------------
                # Canadiantire
                # --------------------------
                elif "canadiantire.ca" in domain:
                    # --- Extract Price ---
                    await page.wait_for_selector('[class="price__value"]', timeout=15000, state="attached")
                    price_dollars = await page.text_content('[class="price__value"]')
                    price = price_dollars.strip() if price_dollars else "Price not found"
                    print(f"\n\n\nPrice: {price}")

                    # --- Extract Main Product Image URL ---
                    await page.wait_for_selector('img[src*="canadiantire.ca"]', timeout=15000, state="attached")
                    image_element = await page.query_selector('img[src*="canadiantire.ca"]')
                    image_src = await image_element.get_attribute('src')
                    

                    # --- Output Results ---
                    print(f"Main Product Image URL: {image_src}\n\n\n")
                # ---------------------------
                # Fallbacks
                # ---------------------------
                if not image_src:
                    og_img = await page.query_selector('meta[property="og:image"]')
                    image_src = await og_img.get_attribute('content') if og_img else None

                if not price:
                    meta_price = await page.query_selector('meta[itemprop="price"]')
                    price = await meta_price.get_attribute('content') if meta_price else None

                return {
                    'image_src': image_src or 'Not found',
                    'price': price.strip() if price else 'Not found'
                }

            except Exception as e:
                print(f"[ERROR] Scraping failed: {str(e)}")
                return {'error': f'Scraping failed: {str(e)}'}

            finally:
                await browser.close()

    try:
        result = asyncio.run(run_scraper())  # Cleaner than creating new loops
        return jsonify(result)
    except asyncio.TimeoutError:
        print("[ERROR] Scraping timed out.")
        return jsonify({'error': 'Scraping timed out'}), 504
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return "Service is running"

def keep_alive():
    def ping():
        while True:
            try:
                requests.get("https://product-data-scraper-endpoint.onrender.com")
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