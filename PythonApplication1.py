import os
import requests
from bs4 import BeautifulSoup
import re
from io import BytesIO
from zipfile import ZipFile
from tqdm import tqdm
from datetime import datetime
from urllib.parse import urljoin, quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import random

# Base directory for manga storage
base_dir = r"Please enter full path folder where you wnant your manga chapters to be saved!"

# Set up headers to mimic a real browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36",
    "Referer": "",
}

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def clean_title_for_search(title):
    return re.sub(r"[^\w\s]", "", title).strip().replace(" ", "+")

def log_error(manga_dir, error_message):
    error_log_path = os.path.join(manga_dir, "error_log.txt")
    with open(error_log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now().isoformat()} - {error_message}\n")
    print(f"Error logged to {error_log_path}")

def save_html_as_txt(manga_dir, html_content):
    html_file_path = os.path.join(manga_dir, "page_content.txt")
    with open(html_file_path, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)
    return html_file_path

def save_url(manga_dir, url):
    url_file_path = os.path.join(manga_dir, "url.txt")
    with open(url_file_path, "w", encoding="utf-8") as url_file:
        url_file.write(url)
    print(f"URL saved to {url_file_path}")

# Improved Selenium setup to mimic human-like interaction
def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")  # Simulate a maximized window
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass Selenium automation detection
    chrome_options.add_argument("--disable-extensions")  # Disable extensions
    chrome_options.add_argument("--disable-gpu")  # Disable GPU for better compatibility
    chrome_options.add_argument("--incognito")  # Use incognito mode to prevent tracking
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    # Start Chrome with the necessary options
    chrome_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    # Set a custom user-agent to mimic a real browser
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/104.0.5112.102 Safari/537.36"
    })

    return driver

# Function to add random delays and scroll to mimic human behavior
def human_like_interaction(driver):
    time.sleep(random.uniform(2, 5))  # Random delay between 2-5 seconds
    
    # Simulate scrolling
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1, 3))
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(2, 5))

# Improved image download process
def download_image(img_url, save_dir, save_name, max_retries=3):
    save_path = os.path.join(save_dir, save_name)
    retries = 0

    while retries < max_retries:
        try:
            # Open a session for better control over cookies and headers
            session = requests.Session()
            session.headers.update(headers)
            
            # Stream the image in chunks
            with session.get(img_url, stream=True, timeout=10) as img_response:
                img_response.raise_for_status()

                # Save the image in chunks
                with open(save_path, 'wb') as img_file:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        if chunk:
                            img_file.write(chunk)
            
            print(f"Image downloaded and saved to {save_path}")
            return True
        
        except requests.exceptions.RequestException as e:
            retries += 1
            log_error(save_dir, f"Attempt {retries} failed to download image {img_url}. Error: {e}")
            time.sleep(2)
    
    log_error(save_dir, f"Failed to download image {img_url} after {max_retries} attempts.")
    return False

def search_mangadex_and_download_cover_selenium(manga_title, manga_dir):
    try:
        driver = init_selenium()
        cleaned_title = clean_title_for_search(manga_title)
        search_url = f"https://mangadex.org/search?q={cleaned_title}"
        print(f"Searching for {manga_title} on MangaDex using Selenium: {search_url}")
        
        driver.get(search_url)
        human_like_interaction(driver)  # Simulate human behavior on the page

        # Find the first manga card that has an image and extract the cover image URL
        first_manga_card = driver.find_element(By.CSS_SELECTOR, 'div.grid.gap-2 img.rounded.shadow-md')
        if not first_manga_card:
            log_error(manga_dir, f"No results found on MangaDex for {manga_title}.")
            return False

        cover_img_url = first_manga_card.get_attribute('src')
        print(f"Found cover image via Selenium: {cover_img_url}")
        
        # Use Selenium's driver to download the image to simulate a "human-like" download process
        driver.get(cover_img_url)
        time.sleep(2)  # Wait for image to load fully
        save_path = os.path.join(manga_dir, "cover.jpg")

        with open(save_path, "wb") as file:
            file.write(driver.find_element(By.TAG_NAME, "img").screenshot_as_png)

        print(f"Image downloaded using Selenium and saved to {save_path}")
        return True

    except Exception as e:
        log_error(manga_dir, f"Error searching or downloading cover using Selenium: {e}")
        return False

    finally:
        driver.quit()

def extract_and_download_cover(manga_dir, html_file_path, base_url, manga_title):
    success = search_mangadex_and_download_cover_selenium(manga_title, manga_dir)  # Use Selenium-based search
    if success:
        return

    print("Falling back to original method to download cover image.")
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    cover_img_tag = soup.select_one('div.panel-story-info div.story-info-left img.img-loading')
    
    if not cover_img_tag or not cover_img_tag.get('src'):
        log_error(manga_dir, "Cover image tag not found or missing 'src' attribute.")
        return

    cover_img_url = urljoin(base_url, cover_img_tag['src'])
    download_image(cover_img_url, manga_dir, "cover.jpg")

def download_manga(url, manga_title=None):
    headers['Referer'] = url
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html_content = response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the manga page. Error: {e}")
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    if not manga_title:
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Processing Manga: {manga_title}")
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)
    os.makedirs(manga_dir, exist_ok=True)
    
    save_url(manga_dir, url)
    html_file_path = save_html_as_txt(manga_dir, html_content)
    print(f"HTML content saved to {html_file_path}")

    extract_and_download_cover(manga_dir, html_file_path, url, manga_title)

    # Process and download chapters
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")

        chapter_response = requests.get(chapter_url, headers=headers)
        chapter_response.raise_for_status()
        chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

        image_container = chapter_soup.find('div', class_='container-chapter-reader')
        
        if image_container:
            image_tags = image_container.find_all('img', class_=['reader-content', 'img-content'])
            
            if not image_tags:
                print(f"No images found in chapter: {chapter_title}. Skipping...")
                continue
            
            print(f"Found {len(image_tags)} images in chapter: {chapter_title}")

            # Estimate download size
            chapter_size = 0
            for img_tag in image_tags:
                img_url = img_tag['src']
                img_head = requests.head(img_url, headers=headers)
                if 'Content-Length' in img_head.headers:
                    size = int(img_head.headers['Content-Length'])
                    chapter_size += size

            total_download_size += chapter_size

            print(f"Estimated size for {chapter_title}: {chapter_size / (1024 * 1024):.2f} MB")

            with BytesIO() as img_data:
                with ZipFile(img_data, 'w') as cbz_file:
                    progress = tqdm(total=chapter_size, desc=f"Downloading {chapter_title}", unit="B", unit_scale=True)
                    for i, img_tag in enumerate(image_tags):
                        img_url = img_tag['src']
                        img_response = requests.get(img_url, headers=headers)
                        if img_response.status_code == 200:
                            img_name = f"{i+1:03}.jpg"
                            cbz_file.writestr(img_name, img_response.content)
                            progress.update(len(img_response.content))
                        else:
                            print(f"Failed to download image {img_url}")
                    progress.close()

                # Extract chapter number using regex
                match = re.search(r'Chapter (\d+(\.\d+)?)', chapter_title)
                if match:
                    chapter_number = match.group(1)
                    if '.' in chapter_number:
                        chapter_number = chapter_number.replace('.', 'p')
                    else:
                        chapter_number = f"{int(chapter_number):02}"

                    cbz_filename = f"{manga_title} Chapter {chapter_number}.cbz"
                    cbz_path = os.path.join(manga_dir, cbz_filename)

                    with open(cbz_path, 'wb') as file:
                        file.write(img_data.getvalue())
                    
                    with open(log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"{chapter_url}\t{chapter_title}\t{datetime.now().isoformat()}\n")
                else:
                    print(f"Failed to extract chapter number from title '{chapter_title}'. Skipping...")
        else:
            print(f"Could not find image container for chapter: {chapter_title}. Skipping...")

    print(f"Total estimated download size: {total_download_size / (1024 * 1024):.2f} MB")
    update_combined_log()

# Function to update the combined log for all mangas
def update_combined_log():
    combined_log_path = os.path.join(base_dir, "combined_download_log.txt")

    with open(combined_log_path, "w", encoding="utf-8") as combined_log:
        combined_log.write(f"{'Manga Title':<30} {'Total Chapters':<15} {'Last Updated':<25}\n")
        combined_log.write("="*70 + "\n")
        
        for manga_folder in os.listdir(base_dir):
            manga_path = os.path.join(base_dir, manga_folder)
            if os.path.isdir(manga_path):
                log_file = os.path.join(manga_path, "download_log.txt")
                
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as individual_log:
                        chapters = individual_log.readlines()
                        if chapters:
                            last_updated = chapters[-1].strip().split("\t")[-1]
                            combined_log.write(f"{manga_folder:<30} {len(chapters):<15} {last_updated:<25}\n")

# Function to list all available manga folders
def list_manga_folders():
    manga_folders = [folder for folder in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, folder))]
    print("Available Manga Titles:")
    for index, folder in enumerate(manga_folders, 1):
        print(f"{index}. {folder}")
    return manga_folders

# Function to select and update specific manga folders
def select_and_update_folders():
    manga_folders = list_manga_folders()
    print("Enter 'all' to update all folders.")
    selected_numbers = input("Enter the numbers of the manga folders to update (comma-separated): ").split(',')
    
    if 'all' in selected_numbers:
        selected_numbers = range(1, len(manga_folders) + 1)
    else:
        selected_numbers = [int(num.strip()) for num in selected_numbers]

    for num in selected_numbers:
        if 1 <= num <= len(manga_folders):
            manga_folder = manga_folders[num-1]
            manga_folder_path = os.path.join(base_dir, manga_folder)
            url_file_path = os.path.join(manga_folder_path, "url.txt")

            if os.path.exists(url_file_path):
                with open(url_file_path, "r", encoding="utf-8") as url_file:
                    manga_page_url = url_file.read().strip()
                print(f"Updating folder: {manga_folder}")
                update_manga(manga_page_url, manga_title=manga_folder)
            else:
                print(f"URL file missing for folder '{manga_folder}'. Please enter the URL.")
                new_url = input(f"Enter the URL for '{manga_folder}': ").strip()
                save_url(manga_folder_path, new_url)
                update_manga(new_url, manga_title=manga_folder)
        else:
            print(f"Invalid selection: {num}. Skipping...")

# Function to update an existing manga folder with new chapters
def update_manga(url, manga_title=None):
    headers['Referer'] = url
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    html_content = response.text

    if not manga_title:
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('div', class_='story-info-right').find('h1')
        manga_title = title_tag.text.strip()

    print(f"Updating Manga: {manga_title}")

    # Sanitize the manga title
    manga_title = sanitize_filename(manga_title)

    manga_dir = os.path.join(base_dir, manga_title)

    soup = BeautifulSoup(html_content, 'html.parser')
    chapter_list = soup.find('ul', class_='row-content-chapter')
    chapter_links = chapter_list.find_all('li', class_='a-h')

    print(f"Number of chapters found: {len(chapter_links)}")

    log_file_path = os.path.join(manga_dir, "download_log.txt")

    existing_log = {}
    if os.path.exists(log_file_path):
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                chapter_url, chapter_title, last_updated = line.strip().split("\t")
                existing_log[chapter_url] = (chapter_title, last_updated)

    total_download_size = 0

    for chapter_item in chapter_links:
        link = chapter_item.find('a', class_='chapter-name text-nowrap')
        chapter_url = urljoin(url, link['href'])  # Ensure the chapter URL is absolute
        chapter_title = link.text.strip()

        if chapter_url in existing_log:
            print(f"Chapter {chapter_title} already downloaded. Skipping...")
            continue

        print(f"Processing Chapter: {chapter_title} | URL: {chapter_url}")

        chapter_response = requests.get(chapter_url, headers=headers)
        chapter_response.raise_for_status()
        chapter_soup = BeautifulSoup(chapter_response.text, 'html.parser')

        image_container = chapter_soup.find('div', class_='container-chapter-reader')
        
        if image_container:
            image_tags = image_container.find_all('img', class_=['reader-content', 'img-content'])
            
            if not image_tags:
                print(f"No images found in chapter: {chapter_title}. Skipping...")
                continue
            
            print(f"Found {len(image_tags)} images in chapter: {chapter_title}")

            # Estimate download size
            chapter_size = 0
            for img_tag in image_tags:
                img_url = img_tag['src']
                img_head = requests.head(img_url, headers=headers)
                if 'Content-Length' in img_head.headers:
                    size = int(img_head.headers['Content-Length'])
                    chapter_size += size

            total_download_size += chapter_size

            print(f"Estimated size for {chapter_title}: {chapter_size / (1024 * 1024):.2f} MB")

            with BytesIO() as img_data:
                with ZipFile(img_data, 'w') as cbz_file:
                    progress = tqdm(total=chapter_size, desc=f"Downloading {chapter_title}", unit="B", unit_scale=True)
                    for i, img_tag in enumerate(image_tags):
                        img_url = img_tag['src']
                        img_response = requests.get(img_url, headers=headers)
                        if img_response.status_code == 200:
                            img_name = f"{i+1:03}.jpg"
                            cbz_file.writestr(img_name, img_response.content)
                            progress.update(len(img_response.content))
                        else:
                            print(f"Failed to download image {img_url}")
                    progress.close()

                # Extract chapter number using regex
                match = re.search(r'Chapter (\d+(\.\d+)?)', chapter_title)
                if match:
                    chapter_number = match.group(1)
                    if '.' in chapter_number:
                        chapter_number = chapter_number.replace('.', 'p')
                    else:
                        chapter_number = f"{int(chapter_number):02}"

                    cbz_filename = f"{manga_title} Chapter {chapter_number}.cbz"
                    cbz_path = os.path.join(manga_dir, cbz_filename)

                    with open(cbz_path, 'wb') as file:
                        file.write(img_data.getvalue())
                    
                    with open(log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"{chapter_url}\t{chapter_title}\t{datetime.now().isoformat()}\n")
                else:
                    print(f"Failed to extract chapter number from title '{chapter_title}'. Skipping...")
        else:
            print(f"Could not find image container for chapter: {chapter_title}. Skipping...")

    print(f"Total estimated download size: {total_download_size / (1024 * 1024):.2f} MB")
    update_combined_log()

# Step 1: Handle user input
user_input = input("Enter the manga page URL or 'update' to select folders for update: ")

if user_input.lower() == 'update':
    select_and_update_folders()
else:
    download_manga(user_input)

print(f"All selected chapters downloaded and saved in their respective directories.")
print(f"Combined log file updated and saved at {os.path.join(base_dir, 'combined_download_log.txt')}")

# Prevent the script from closing immediately
input("Press Enter to exit...") 