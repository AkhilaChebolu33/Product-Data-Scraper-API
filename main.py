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
    return urlparse(url).path.lower()

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
        print("Domain:", domain)
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

            specs = None

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(2000)

                # -------------------------
                # SKIL
                # -------------------------
                if "skil" or "SKIL" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="sk-pdp-specifications__col-container-right"]', timeout=1200000, state="attached")
                                        
                    specs = await page.text_content('[class="sk-pdp-specifications__col-container-right"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")


                # -------------------------
                # RYOBI
                # -------------------------
                elif "ryobi" or "RYOBI" in domain:
                    # Scroll and click Specifications button
                    specs_button = page.locator('button:has-text("Specifications")')
                    await specs_button.scroll_into_view_if_needed()
                    await specs_button.click(force=True)

                    # Wait for the specs list to appear
                    await page.wait_for_selector('dl.specs-table__list', timeout=30000)

                    # Locate all spec items
                    rows = page.locator('div.specs-table__item')
                    count = await rows.count()
                    print(f"Found {count} specification rows.")

                    specs = {}
                    for i in range(count):
                        label = await rows.nth(i).locator('dt.specs-table__term').text_content()
                        value = await rows.nth(i).locator('dd.specs-table__def').text_content()
                        specs[label.strip()] = value.strip()

                    print("\nSPECIFICATIONS:\n")
                    for key, val in specs.items():
                        print(f"{key}: {val}")


                    

                # -------------------------
                # CRAFTSMAN
                # -------------------------
                elif "craftsman" or "CRAFTSMAN" in domain:
                    # Wait for the container to be attached
                    await page.wait_for_selector('.container.w-full.bg-color-brand-surface-primary', timeout=1200000, state="attached")

                    # Get the third <div> inside the container
                    specs_div = page.locator('.container.w-full.bg-color-brand-surface-primary >> div:nth-of-type(3)')

                    # Click the Specifications button to expand the section
                    await page.click('button:has-text("Specifications")')


                    # Wait for the expanded accordion content to be visible
                    await page.wait_for_selector('[data-state="open"] >> div.flex.flex-col.gap-4.items-start', timeout=5000)

                    # Target the rows inside the expanded specifications section
                    rows = page.locator('[data-state="open"] >> div.flex.flex-col.gap-4.items-start >> div.flex.w-full.flex-col >> div.flex.justify-between.px-3.py-4')

                    # Count the number of rows
                    count = await rows.count()
                    print(f"Found {count} specification rows.")

                    # Extract label-value pairs
                    specs = {}

                    for i in range(count):
                        row = rows.nth(i)
                        label = await row.locator('div.prose-label-medium-sm').text_content()
                        value = await row.locator('div.prose-label-bold-sm').text_content()
                        specs[label.strip()] = value.strip()

                    # Print the results
                    print("\n\n\nSPECIFICATIONS:\n")
                    for key, val in specs.items():
                        print(f"{key}: {val}")
                    print("\n\n\n")
                    

                # -------------------------
                # WORX
                # -------------------------
                elif "worx" or "WORX" in domain:
                    # --- Extract Specs ---
                    # Click the Technical Specs accordion
                    await page.click('a.switch:has-text("Technical Specs")')

                    # Wait for the expanded section to be visible
                    await page.wait_for_selector('#VK54JDL.ui-accordion-content-active', timeout=5000)

                    # Locate all spec rows inside Technical Specs
                    rows = page.locator('#VK54JDL [data-content-type="spec_row"]')
                    count = await rows.count()
                    print(f"Found {count} specification rows.")

                    specs = {}
                    for i in range(count):
                        row = rows.nth(i)
                        label = await row.locator('div.spec-label').text_content()
                        value = await row.locator('div.spec-value').text_content()
                        specs[label.strip()] = value.strip()

                    # Print results
                    print("\nTECHNICAL SPECS:\n")
                    for key, val in specs.items():
                        print(f"{key}: {val}")
                
                # ----------------------------
                # KOBALT
                # ----------------------------
                elif "kobalt" in domain:
                    # --- Extract Specs ---
                    print(f"specs")

                # ----------------------------
                # MASTERFORCE
                # ----------------------------
                elif "Masterforce" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="card-body row m-0 w-100 justify-content-center col-12"]', timeout=1200000, state="attached")
                     
                    specs = await page.text_content('[class="card-body row m-0 w-100 justify-content-center col-12"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                    


                # ----------------------------
                # HYPERTOUGH
                # ----------------------------
                elif "hyper-tough" or "Hyper-Tough" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="nt1"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="nt1"]')

                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")

                    

                # ----------------------------
                # BAUER
                # ----------------------------
                elif "Bauer" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[id="SpecificationsContent"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[id="SpecificationsContent"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                    
                # -------------------------
                # HERCULES
                # -------------------------
                elif "hercules" or "Hercules" in domain:
                    await page.wait_for_selector('[id="SpecificationsContent"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[id="SpecificationsContent"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # -------------------------
                # RIGID
                # -------------------------
                elif "rigid" or "RIGID" in domain:
                    await page.wait_for_selector('[class="specifications-table"]', timeout=1200000, state="attached")
    

                    specs = await page.text_content('[class="specifications-table"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")

                # -------------------------
                # BLACKDECKER
                # -------------------------
                elif "BLACK-DECKER" or "black-decker" in domain:
                    await page.wait_for_selector('[class="mb-[10px]"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="mb-[10px]"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                   
                
                # --------------------------
                # MILWAUKEE
                # --------------------------
                elif "milwaukee" or "Milwaukee" in domain:

                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="specs-container text-14 leading-tight font-helvetica55 text-gray-900 w-[480px]"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="specs-container text-14 leading-tight font-helvetica55 text-gray-900 w-[480px]"]')
                    ## price_decimal = await page.text_content('[class="a-price-decimal"]')
                    # price_cents = await page.text_content('[class="a-price-fraction"]')
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")

                # --------------------------
                # MAKITA
                # --------------------------
                elif "makita" or "Makita" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="detail-specs js-columns"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="detail-specs js-columns"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # DEWALT
                # --------------------------
                elif "dewalt" or "DEWALT" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="coh-container coh-style-specifications"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="coh-container coh-style-specifications"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # METABO
                # --------------------------
                elif "metabo" or "Metabo" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[id="attributes"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[id="attributes"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # BOSCH
                # --------------------------
                elif "bosch" or "Bosch" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="table__body"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="table__body"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")

                # --------------------------
                # DREMEL
                # --------------------------
                elif "dremel" or "Dremel" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="TechnicalSpecification_tablesWrapper__zVSHu"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="TechnicalSpecification_tablesWrapper__zVSHu"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # GREENWORKS
                # --------------------------
                elif "greenworks" or "Greenworks" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="specifications"]', timeout=1200000, state="attached")
                    await page.wait_for_selector('[class="additional-specs"]', timeout=1200000, state="attached") 

                    ## price_symbol = await page.text_content('[class="a-price-symbol"]')
                    specs_1 = await page.text_content('[class="specifications"]')
                    specs_2 = await page.text_content('[class="additional-specs"]')

                    specifications = f"{specs_1.strip()}\n\n\n{specs_2.strip()}"
                    print(f"\n\n\SPECIFICATIONS: {specifications}\n\n\n")
                
                # --------------------------
                # KREG
                # --------------------------
                elif "kreg" or "Kreg" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="grid md:grid-cols-2 gap-4 md:gap-6"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="grid md:grid-cols-2 gap-4 md:gap-6"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # MASTERCRAFT
                # --------------------------
                elif "mastercraft" or "Mastercraft" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="flex flex-col gap-4 items-start pb-6 sm:pb-8 text-color-brand-text-secondary prose-body-medium-sm xl:prose-body-medium-md prose-ol:pl-5 prose-ul:pl-5 prose-ul:list-disc prose-ol:list-decimal [&_::marker]:text-color-brand-text-secondary [&_p_a]:underline !prose-body-medium-sm"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="flex flex-col gap-4 items-start pb-6 sm:pb-8 text-color-brand-text-secondary prose-body-medium-sm xl:prose-body-medium-md prose-ol:pl-5 prose-ul:pl-5 prose-ul:list-disc prose-ol:list-decimal [&_::marker]:text-color-brand-text-secondary [&_p_a]:underline !prose-body-medium-sm"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # HILTI
                # --------------------------
                elif "hilti" or "Hilti" in domain:
                    # --- Extract Specs ---
                    await page.wait_for_selector('[class="px-1 mb-2"]', timeout=1200000, state="attached")
    
                    specs = await page.text_content('[class="px-1 mb-2"]')
                    
                    specifications = f"{specs.strip()}"
                    print(f"\n\n\nPrice: {specifications}\n\n\n")
                
                # --------------------------
                # HART
                # --------------------------
                elif "hart" or "Hart" in domain:
                    # --- Extract Specs ---
                    specs_tab = page.locator('button:has-text("Specifications")')
                    await specs_tab.click(force=True)

                    # Extract specifications text
                    specs = await page.locator('.specs-table__list').text_content()
                    specifications = specs.strip() if specs else "No specs found"
                    print(f"\nSpecifications:\n{specifications}\n")


                # ---------------------------
                # Fallbacks
                # ---------------------------
            
                


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