import asyncio
import sys
import streamlit as st
from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import os
import uuid

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

@dataclass
class Business:
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)

    def dataframe(self):
        return pd.json_normalize((asdict(b) for b in self.business_list), sep="_")

    def append_unique(self, business):
        self.business_list.append(business)

    def save_to_excel(self, filename):
        self.dataframe().to_excel(filename, index=False)

def scrape_data(search_query, total=5, progress_callback=None):
    business_list = BusinessList()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(2000)

        page.locator('//input[@id="searchboxinput"]').fill(search_query)
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)

        scraped_urls = set()
        previous_count = 0

        while len(business_list.business_list) < total:
            listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
            current_count = len(listings)

            if current_count == previous_count:
                break
            previous_count = current_count

            for listing in listings:
                if len(business_list.business_list) >= total:
                    break

                url = listing.get_attribute('href')
                if url in scraped_urls:
                    continue

                try:
                    listing.click()
                    page.wait_for_timeout(4000)

                    business = Business()

                    name_xpath = '//h1[contains(@class, "DUwDvf")]'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'

                    if page.locator(name_xpath).count() > 0:
                        business.name = page.locator(name_xpath).first.inner_text()
                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).first.inner_text()
                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).first.inner_text()
                    if page.locator(phone_xpath).count() > 0:
                        business.phone_number = page.locator(phone_xpath).first.inner_text()

                    scraped_urls.add(url)
                    business_list.append_unique(business)

                    if progress_callback:
                        progress = len(business_list.business_list) / total
                        progress_callback(progress)

                except:
                    continue

            # Fast scrolling
            for _ in range(2):
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2000)

        browser.close()

    return business_list

# Streamlit UI
st.set_page_config(page_title="Google Maps Business Scraper", layout="centered")
st.title("📍 Google Maps Business Scraper")
st.markdown("Enter a business search query (e.g., **Jewellery shop in Kanpur**)")

query = st.text_input("Search Query")
total = st.slider("How many results to fetch?", 5, 100, 10)

progress_bar = st.progress(0)
progress_text = st.empty()
status_msg = st.empty()

if st.button("Scrape"):
    if query.strip() == "":
        st.warning("Please enter a search query.")
    else:
        status_msg.info("🔄 Scraping started...")
        business_list = None

        def progress_callback(progress):
            percent = int(progress * 100)
            progress_bar.progress(percent)
            progress_text.text(f"Scraping... {percent}% done")

        try:
            business_list = scrape_data(query, total, progress_callback)
            progress_bar.progress(100)
            progress_text.text("✅ Scraping completed!")
            status_msg.success("✅ Done!")

            filename = f"scraped_data_{uuid.uuid4().hex[:8]}.xlsx"
            business_list.save_to_excel(filename)

            with open(filename, "rb") as f:
                st.download_button(
                    label=f"📥 Download Excel File ({len(business_list.business_list)} results)",
                    data=f,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            os.remove(filename)

        except Exception as e:
            st.error(f"Something went wrong: {e}")
